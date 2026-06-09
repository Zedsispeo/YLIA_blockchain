"""Routes HTTP (Blueprint). État du nœud lu via current_app.blockchain et
current_app.node_identity ({private_key, public_key, address})."""

from __future__ import annotations

import time
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from .. import crypto, node
from ..block import Block
from ..blockchain import ChainError
from ..config import ROOT_PRIVATE_KEY
from ..transaction import Transaction
from .errors import ApiError

bp = Blueprint("ylia", __name__)


# Exposé par l'index / pour auto-documenter l'API.
ENDPOINTS: dict[str, str] = {
    "GET /": "ce catalogue + informations sur le nœud",
    "GET /health": "sonde de vivacité",
    "GET /chain": "la chaîne complète et sa longueur",
    "POST /transactions/new": "soumettre une transaction signée",
    "GET /mine": "miner un bloc avec les transactions en attente",
    "GET /pending": "transactions en attente",
    "DELETE /transactions/pending": "vider le mempool (exploitation)",
    "POST /nodes/register": "enregistrer des pairs : {\"nodes\": [\"http://…\"]}",
    "GET /nodes": "lister les pairs",
    "GET /nodes/resolve": "résolution de conflits (plus longue chaîne valide)",
    "POST /blocks/receive": "recevoir un bloc d'un pair (rejeté si consensus invalide)",
    "GET /authorities": "liste blanche des autorités agréées",
    "POST /authorities/register": "agréer un établissement : {\"address\": \"YLIA…\"}",
    "POST /authorities/revoke": "révoquer un établissement : {\"address\": \"YLIA…\"}",
    "GET /balance/<address>": "solde confirmé et disponible d'un compte",
    "GET /balances": "tous les soldes",
    "GET /validate": "la chaîne est-elle valide ? (+ raison)",
    "GET /wallet/new": "générer une paire de clés",
    "GET /node": "informations sur ce nœud",
}


# --------------------------------------------------------------------------- #
# Aides
# --------------------------------------------------------------------------- #
def _chain():
    return current_app.blockchain


def _identity() -> dict[str, str]:
    return current_app.node_identity


def _json_body() -> dict[str, Any]:
    body = request.get_json(silent=True)
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise ApiError("le corps de la requête doit être un objet JSON")
    return body


def _build_transaction(payload: dict[str, Any]) -> Transaction:
    """Transaction depuis le corps de requête. 3 modes : pré-signée
    (public_key+signature), private_key, ou use_root (signature serveur, démo)."""
    tx_type = payload.get("type", "credit")
    recipient = payload.get("recipient")
    amount = int(payload.get("amount", 0) or 0)
    nonce = str(payload.get("nonce", "") or "")

    if not recipient:
        raise ApiError("le champ 'recipient' est obligatoire")

    # Mode 1 : transaction déjà signée côté client.
    if payload.get("signature") and payload.get("public_key"):
        return Transaction(
            tx_type=tx_type,
            sender=payload.get("sender")
            or crypto.address_from_public_key(payload["public_key"]),
            recipient=recipient,
            amount=amount,
            public_key=payload["public_key"],
            timestamp=float(payload.get("timestamp", time.time())),
            nonce=nonce,
            signature=payload["signature"],
        )

    # Modes 2 & 3 : signature côté serveur.
    private_key = ROOT_PRIVATE_KEY if payload.get("use_root") else payload.get("private_key")
    if not private_key:
        raise ApiError(
            "transaction non signée : fournissez 'private_key', 'use_root', "
            "ou une transaction pré-signée ('public_key' + 'signature')"
        )
    public_key = crypto.public_key_from_private(private_key)
    tx = Transaction(
        tx_type=tx_type,
        sender=crypto.address_from_public_key(public_key),
        recipient=recipient,
        amount=amount,
        public_key=public_key,
        timestamp=time.time(),
        nonce=nonce,
    )
    tx.sign(private_key)
    return tx


def _registry_transaction(tx_type: str):
    payload = _json_body()
    address = payload.get("address")
    if not address:
        raise ApiError("champ 'address' obligatoire")
    chain = _chain()
    tx = Transaction(
        tx_type=tx_type,
        sender=chain.root_address,
        recipient=address,
        amount=0,
        public_key=crypto.public_key_from_private(ROOT_PRIVATE_KEY),
        timestamp=time.time(),
        nonce=str(payload.get("nonce", "") or ""),
    ).sign(ROOT_PRIVATE_KEY)
    block_index = chain.add_transaction(tx)  # peut lever ChainError → 400
    if chain.peers:
        node.broadcast_transaction(chain.peers, tx.to_dict())
    verb = "agréé" if tx_type == "register" else "révoqué"
    return (
        jsonify(
            {
                "message": f"Établissement {verb} (effectif après minage du bloc #{block_index})",
                "transaction": tx.to_dict(),
            }
        ),
        201,
    )


# --------------------------------------------------------------------------- #
# Index / santé
# --------------------------------------------------------------------------- #
@bp.get("/")
def index():
    chain = _chain()
    ident = _identity()
    return jsonify(
        {
            "name": "YLIA",
            "description": "Blockchain de points de fidélité (Proof of Authority)",
            "node": {
                "address": ident["address"],
                "is_authority": ident["address"] in chain.current_authorities(),
                "is_root": ident["address"] == chain.root_address,
            },
            "chain_length": len(chain.chain),
            "endpoints": ENDPOINTS,
        }
    )


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "chain_length": len(_chain().chain)})


# --------------------------------------------------------------------------- #
# Endpoints du sujet
# --------------------------------------------------------------------------- #
@bp.get("/chain")
def get_chain():
    return jsonify(_chain().to_dict())


@bp.post("/transactions/new")
def new_transaction():
    chain = _chain()
    tx = _build_transaction(_json_body())
    block_index = chain.add_transaction(tx)  # ChainError → 400
    if request.args.get("broadcast", "true").lower() != "false" and chain.peers:
        node.broadcast_transaction(chain.peers, tx.to_dict())
    return (
        jsonify(
            {
                "message": f"Transaction ajoutée — sera incluse dans le bloc #{block_index}",
                "transaction": tx.to_dict(),
                "block_index": block_index,
            }
        ),
        201,
    )


@bp.get("/mine")
def mine():
    chain = _chain()
    try:
        block = chain.mine(_identity()["private_key"])
    except ChainError as exc:
        # Un nœud non agréé ne peut pas produire de bloc → 403 Forbidden.
        raise ApiError(str(exc), 403) from exc
    if chain.peers:
        node.broadcast_block(chain.peers)
    return jsonify(
        {
            "message": f"Nouveau bloc #{block.index} miné par {_identity()['address']}",
            "block": block.to_dict(),
        }
    )


# --------------------------------------------------------------------------- #
# Mempool
# --------------------------------------------------------------------------- #
@bp.get("/pending")
def pending():
    chain = _chain()
    return jsonify(
        {
            "pending_transactions": [t.to_dict() for t in chain.pending_transactions],
            "count": len(chain.pending_transactions),
        }
    )


@bp.delete("/transactions/pending")
def clear_pending():
    removed = _chain().clear_pending()
    return jsonify({"message": f"{removed} transaction(s) retirée(s) du mempool"})


# --------------------------------------------------------------------------- #
# Réseau multi-nœuds
# --------------------------------------------------------------------------- #
@bp.post("/nodes/register")
def register_nodes():
    payload = _json_body()
    nodes = payload.get("nodes")
    if not nodes or not isinstance(nodes, list):
        raise ApiError("fournir une liste 'nodes' d'URLs")
    chain = _chain()
    for url in nodes:
        chain.register_peer(url)
    return jsonify({"message": f"{len(nodes)} pair(s) enregistré(s)", "total_peers": sorted(chain.peers)}), 201


@bp.get("/nodes")
def list_nodes():
    return jsonify({"peers": sorted(_chain().peers)})


@bp.get("/nodes/resolve")
def resolve():
    chain = _chain()
    candidate_chains = node.gather_peer_chains(chain.peers)
    replaced = chain.resolve_conflicts(candidate_chains)
    return jsonify(
        {
            "replaced": replaced,
            "message": (
                "Notre chaîne a été remplacée par une plus longue chaîne valide"
                if replaced
                else "Notre chaîne fait autorité (aucune chaîne plus longue valide)"
            ),
            "length": len(chain.chain),
        }
    )


@bp.post("/blocks/receive")
def receive_block():
    """Reçoit un bloc diffusé par un pair. Le bloc est REJETÉ (409) si son
    consensus est invalide (validateur non agréé / signature de bloc invalide)
    ou s'il ne chaîne pas correctement ; accepté (201) sinon."""
    try:
        block = Block.from_dict(_json_body())
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(f"bloc malformé : {exc}")
    try:
        _chain().add_block(block)
    except ChainError as exc:
        return jsonify({"accepted": False, "reason": str(exc)}), 409
    return (
        jsonify({"accepted": True, "message": f"bloc #{block.index} accepté", "block": block.to_dict()}),
        201,
    )


# --------------------------------------------------------------------------- #
# Registre d'agréments
# --------------------------------------------------------------------------- #
@bp.get("/authorities")
def authorities():
    chain = _chain()
    return jsonify({"root": chain.root_address, "authorities": sorted(chain.current_authorities())})


@bp.post("/authorities/register")
def authority_register():
    return _registry_transaction("register")


@bp.post("/authorities/revoke")
def authority_revoke():
    return _registry_transaction("revoke")


# --------------------------------------------------------------------------- #
# Soldes / validation / portefeuille / infos
# --------------------------------------------------------------------------- #
@bp.get("/balance/<address>")
def balance(address: str):
    chain = _chain()
    return jsonify(
        {
            "address": address,
            "balance": chain.balance_of(address),
            "available": chain.available_balance(address),
        }
    )


@bp.get("/balances")
def balances():
    return jsonify({"balances": _chain().compute_balances()})


@bp.get("/validate")
def validate():
    ok, reason = _chain().validate_chain()
    return jsonify({"valid": ok, "reason": reason, "length": len(_chain().chain)})


@bp.get("/wallet/new")
def wallet_new():
    private_key, public_key = crypto.generate_keypair()
    return jsonify(
        {
            "private_key": private_key,
            "public_key": public_key,
            "address": crypto.address_from_public_key(public_key),
            "note": "Conservez la clé privée : elle ne sera pas régénérée.",
        }
    )


@bp.get("/node")
def node_info():
    chain = _chain()
    ident = _identity()
    return jsonify(
        {
            "address": ident["address"],
            "public_key": ident["public_key"],
            "is_authority": ident["address"] in chain.current_authorities(),
            "root_address": chain.root_address,
            "is_root": ident["address"] == chain.root_address,
            "peers": sorted(chain.peers),
            "chain_length": len(chain.chain),
            "pending": len(chain.pending_transactions),
        }
    )
