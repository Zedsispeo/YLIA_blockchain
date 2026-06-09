"""Cœur YLIA : chaîne, mempool, minage PoA, validation, soldes, conflits.

Volontairement sans réseau (testable hors HTTP) ; le P2P vit dans node.py / api/.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

from . import crypto
from .block import Block
from .config import GENESIS_PREVIOUS_HASH, GENESIS_TIMESTAMP, ROOT_PRIVATE_KEY
from .registry import ROOT_ADDRESS, ROOT_PUBLIC_KEY, authorities_from_transactions
from .transaction import REGISTRY_TYPES, VALUE_TYPES, Transaction


class ChainError(ValueError):
    """Transaction, bloc ou chaîne invalide."""


class Blockchain:
    def __init__(self) -> None:
        self.chain: list[Block] = []
        self.pending_transactions: list[Transaction] = []
        self.peers: set[str] = set()
        self._create_genesis_block()

    # --- Genesis ---

    def _create_genesis_block(self) -> None:
        # Déterministe (timestamp figé + signature RFC 6979) → identique partout.
        genesis_tx = Transaction(
            tx_type="genesis",
            sender=ROOT_ADDRESS,
            recipient=ROOT_ADDRESS,
            amount=0,
            public_key=ROOT_PUBLIC_KEY,
            timestamp=GENESIS_TIMESTAMP,
        )
        genesis_tx.sign(ROOT_PRIVATE_KEY)

        block = Block(
            index=0,
            timestamp=GENESIS_TIMESTAMP,
            transactions=[genesis_tx],
            previous_hash=GENESIS_PREVIOUS_HASH,
            validator=ROOT_ADDRESS,
            validator_pubkey=ROOT_PUBLIC_KEY,
        )
        block.sign(ROOT_PRIVATE_KEY)
        self.chain = [block]

    @property
    def root_address(self) -> str:
        return ROOT_ADDRESS

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    # --- Mempool ---

    def add_transaction(self, transaction: Transaction) -> int:
        """Valide et met en attente. Retourne l'index du prochain bloc."""
        error = transaction.structural_error()
        if error:
            raise ChainError(error)

        # Anti-rejeu : signature unique (mempool + chaîne).
        if self._signature_known(transaction.signature):
            raise ChainError("transaction déjà connue (signature déjà vue)")
        # Idempotence : nonce unique par émetteur s'il est fourni.
        if transaction.nonce and self._nonce_known(transaction.sender, transaction.nonce):
            raise ChainError(f"nonce déjà utilisé par cet émetteur : {transaction.nonce!r}")

        # Autorité + affordabilité, en tenant compte du mempool (anti double-dépense).
        err = self._business_validity_error(
            transaction, self.current_authorities(), self._available_balances()
        )
        if err:
            raise ChainError(err)

        self.pending_transactions.append(transaction)
        return self.last_block.index + 1

    def _business_validity_error(
        self, tx: Transaction, authorities: set[str], available_balances: dict[str, int]
    ) -> str | None:
        """Règles métier (autorité, solde) d'une tx déjà bien formée. None si OK."""
        if tx.type in REGISTRY_TYPES:
            if tx.sender != ROOT_ADDRESS:
                return "seule l'autorité racine peut agréer ou révoquer"
        elif tx.type in VALUE_TYPES:
            if tx.sender not in authorities:
                return (
                    "émetteur non agréé : seul un établissement agréé peut "
                    "créditer ou débiter des points"
                )
            if tx.type == "debit":
                available = available_balances.get(tx.recipient, 0)
                if available < tx.amount:
                    return (
                        f"solde insuffisant : {available} point(s) disponible(s), "
                        f"{tx.amount} demandé(s)"
                    )
        else:
            return f"type non autorisé dans le mempool : {tx.type}"
        return None

    def _signature_known(self, signature: str | None) -> bool:
        if signature is None:
            return False
        if any(t.signature == signature for t in self.pending_transactions):
            return True
        return any(t.signature == signature for b in self.chain for t in b.transactions)

    def _nonce_known(self, sender: str, nonce: str) -> bool:
        key = (sender, nonce)
        if any((t.sender, t.nonce) == key for t in self.pending_transactions):
            return True
        return any((t.sender, t.nonce) == key for b in self.chain for t in b.transactions)

    # --- Minage (PoA) ---

    def mine(self, validator_private_key: str) -> Block:
        """Produit et signe un bloc des transactions en attente.
        Le validateur doit être une autorité agréée."""
        validator_pubkey = crypto.public_key_from_private(validator_private_key)
        validator_address = crypto.address_from_public_key(validator_pubkey)

        if validator_address not in self.current_authorities():
            raise ChainError(
                "ce nœud n'est pas une autorité agréée : il ne peut pas miner. "
                "Faites-le agréer par la racine (register) au préalable."
            )

        block = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            transactions=list(self.pending_transactions),
            previous_hash=self.last_block.hash,
            validator=validator_address,
            validator_pubkey=validator_pubkey,
        )
        block.sign(validator_private_key)

        # Garde-fou : le bloc qu'on produit doit être valide vis-à-vis de notre état.
        authorities, balances = self._state_before_tip()
        self._apply_block(block, self.last_block.hash, authorities, balances)

        self.chain.append(block)
        self.pending_transactions = []
        return block

    def add_block(self, block: Block) -> Block:
        """Valide un bloc reçu (d'un pair) et l'ajoute s'il étend la tête de chaîne.

        Lève ChainError si le bloc est invalide : chaînage, hash, **consensus**
        (validateur non agréé / signature de bloc invalide) ou transactions.
        """
        if block.index != self.last_block.index + 1:
            raise ChainError(
                f"bloc #{block.index} : n'étend pas la tête de chaîne "
                f"(attendu #{self.last_block.index + 1})"
            )
        authorities, balances = self._state_before_tip()
        self._apply_block(block, self.last_block.hash, authorities, balances)
        self.chain.append(block)
        self._revalidate_pending()
        return block

    # --- Validation ---

    def _genesis_is_authentic(self, block: Block) -> bool:
        """Même réseau = même racine = même genesis."""
        return (
            block.index == 0
            and block.previous_hash == GENESIS_PREVIOUS_HASH
            and block.validator == ROOT_ADDRESS
            and block.has_consistent_hash()
            and block.hash == self.chain[0].hash
        )

    def _apply_block(
        self,
        block: Block,
        expected_previous_hash: str,
        authorities: set[str],
        balances: dict[str, int],
    ) -> None:
        """Valide un bloc contre l'état qui le précède et applique ses effets
        (mute authorities/balances). Lève ChainError au moindre problème."""
        # Chaînage + intégrité du hash.
        if block.previous_hash != expected_previous_hash:
            raise ChainError(f"bloc #{block.index} : previous_hash incohérent (chaînage rompu)")
        if not block.has_consistent_hash():
            raise ChainError(f"bloc #{block.index} : hash incohérent (contenu falsifié)")
        # Consensus PoA : signature valide + validateur agréé.
        if not block.has_valid_signature():
            raise ChainError(f"bloc #{block.index} : signature de bloc invalide")
        if block.validator not in authorities:
            raise ChainError(
                f"bloc #{block.index} : validateur non agréé "
                f"({block.validator[:16]}…) — consensus rejeté"
            )

        # Transactions validées sur l'état AVANT ce bloc.
        staged_registry: list[Transaction] = []
        for tx in block.transactions:
            err = tx.structural_error()
            if err:
                raise ChainError(f"bloc #{block.index} : transaction invalide ({err})")

            if tx.type in REGISTRY_TYPES:
                if tx.sender != ROOT_ADDRESS:
                    raise ChainError(
                        f"bloc #{block.index} : agrément/révocation par un non-racine — rejeté"
                    )
                staged_registry.append(tx)
            elif tx.type in VALUE_TYPES:
                if tx.sender not in authorities:
                    raise ChainError(f"bloc #{block.index} : émetteur non agréé ({tx.sender[:16]}…)")
                if tx.type == "credit":
                    balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
                else:  # debit
                    current = balances.get(tx.recipient, 0)
                    if current < tx.amount:
                        raise ChainError(
                            f"bloc #{block.index} : solde insuffisant pour un débit "
                            f"({current} < {tx.amount})"
                        )
                    balances[tx.recipient] = current - tx.amount
            else:
                raise ChainError(f"bloc #{block.index} : type interdit dans un bloc ({tx.type})")

        # Les agréments ne prennent effet que pour les blocs suivants.
        for tx in staged_registry:
            if tx.type == "register":
                authorities.add(tx.recipient)
            elif tx.type == "revoke":
                authorities.discard(tx.recipient)
        authorities.add(ROOT_ADDRESS)

    def validate_chain(self, chain: list[Block] | None = None) -> tuple[bool, str | None]:
        """(True, None) si valide, sinon (False, raison)."""
        chain = self.chain if chain is None else chain
        if not chain:
            return False, "chaîne vide"
        if not self._genesis_is_authentic(chain[0]):
            return False, "bloc genesis non authentique (réseau différent ou falsifié)"

        authorities = authorities_from_transactions(chain[0].transactions)
        authorities.add(ROOT_ADDRESS)
        balances: dict[str, int] = {}
        try:
            for i in range(1, len(chain)):
                self._apply_block(chain[i], chain[i - 1].hash, authorities, balances)
        except ChainError as exc:
            return False, str(exc)
        return True, None

    def is_chain_valid(self, chain: list[Block] | None = None) -> bool:
        ok, _ = self.validate_chain(chain)
        return ok

    # --- État dérivé : autorités et soldes ---

    def current_authorities(self) -> set[str]:
        all_txs = [tx for block in self.chain for tx in block.transactions]
        return authorities_from_transactions(all_txs)

    def _state_before_tip(self) -> tuple[set[str], dict[str, int]]:
        return self.current_authorities(), self.compute_balances()

    def compute_balances(self, chain: list[Block] | None = None) -> dict[str, int]:
        """Solde par adresse, par rejeu de la chaîne (suppose une chaîne valide)."""
        chain = self.chain if chain is None else chain
        balances: dict[str, int] = {}
        for block in chain:
            for tx in block.transactions:
                if tx.type == "credit":
                    balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
                elif tx.type == "debit":
                    balances[tx.recipient] = balances.get(tx.recipient, 0) - tx.amount
        return balances

    def balance_of(self, address: str) -> int:
        return self.compute_balances().get(address, 0)

    def _available_balances(self) -> dict[str, int]:
        """Soldes confirmés ajustés du mempool."""
        balances = self.compute_balances()
        for tx in self.pending_transactions:
            if tx.type == "credit":
                balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
            elif tx.type == "debit":
                balances[tx.recipient] = balances.get(tx.recipient, 0) - tx.amount
        return balances

    def available_balance(self, address: str) -> int:
        return self._available_balances().get(address, 0)

    # --- Résolution de conflits ---

    def resolve_conflicts(self, candidate_chains: Iterable[list[dict[str, Any]]]) -> bool:
        """Adopte la plus longue chaîne valide parmi les pairs. True si remplacée."""
        best_chain = self.chain
        replaced = False

        for raw_chain in candidate_chains:
            try:
                candidate = [Block.from_dict(b) for b in raw_chain]
            except (KeyError, TypeError, ValueError):
                continue  # chaîne malformée
            if len(candidate) <= len(best_chain):
                continue
            if self.is_chain_valid(candidate):
                best_chain = candidate
                replaced = True

        if replaced:
            self.chain = best_chain
            self._revalidate_pending()
        return replaced

    def _revalidate_pending(self) -> None:
        """Reconstruit le mempool après adoption d'une chaîne.

        On rejoue chaque tx restante contre le nouvel état et on purge celles
        devenues invalides (débit non financé, émetteur révoqué…). Sinon une
        seule tx invalide bloquerait tout minage.
        """
        confirmed_sigs = {tx.signature for b in self.chain for tx in b.transactions}
        confirmed_nonces = {
            (tx.sender, tx.nonce) for b in self.chain for tx in b.transactions if tx.nonce
        }
        authorities = self.current_authorities()
        balances = self.compute_balances()
        seen_sigs: set[str] = set()
        seen_nonces: set[tuple[str, str]] = set()
        kept: list[Transaction] = []

        for tx in self.pending_transactions:
            if tx.signature in confirmed_sigs or tx.signature in seen_sigs:
                continue
            if tx.nonce and (
                (tx.sender, tx.nonce) in confirmed_nonces
                or (tx.sender, tx.nonce) in seen_nonces
            ):
                continue
            if tx.structural_error():
                continue
            if self._business_validity_error(tx, authorities, balances):
                continue

            # Conservée : appliquer l'effet pour valider les suivantes (soldes cumulés).
            if tx.type == "credit":
                balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
            elif tx.type == "debit":
                balances[tx.recipient] = balances.get(tx.recipient, 0) - tx.amount
            elif tx.type == "register":
                authorities.add(tx.recipient)
            elif tx.type == "revoke":
                authorities.discard(tx.recipient)
            seen_sigs.add(tx.signature)
            if tx.nonce:
                seen_nonces.add((tx.sender, tx.nonce))
            kept.append(tx)

        self.pending_transactions = kept

    def clear_pending(self) -> int:
        """Vide le mempool, renvoie le nombre de tx retirées."""
        count = len(self.pending_transactions)
        self.pending_transactions = []
        return count

    # --- Pairs ---

    def register_peer(self, address: str) -> None:
        self.peers.add(address.rstrip("/"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain": [block.to_dict() for block in self.chain],
            "length": len(self.chain),
        }
