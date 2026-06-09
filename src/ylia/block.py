"""Bloc structuré selon le schéma de ``src/model/`` (trois « lanes ») :

- ``toplane``  : en-tête — version, timestamp, previous_hash, merkle_root,
  txcount, author (= le validateur), index.
- ``midlane``  : couche de signature — etablissement (= la clé publique du
  validateur), signature et hash du bloc.
- ``botlane``  : les transactions du bloc.

Le hash porte sur l'en-tête (toplane, JSON trié), qui s'engage sur les
transactions via ``merkle_root`` → reproductible et détecte une falsification.

L'interface publique historique (``block.index``, ``block.validator``,
``block.hash``…) est conservée via des propriétés adossées aux trois lanes,
pour rester compatible avec le reste de la chaîne.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from model.botlane import botlane
from model.midlane import midlane
from model.toplane import toplane

from . import crypto
from .transaction import Transaction

BLOCK_VERSION = 1
_EMPTY_HASH = "0" * 64


def _merkle_root(transactions: list[Transaction]) -> str:
    """Racine de Merkle des transactions (s'engage sur leur contenu complet)."""
    if not transactions:
        return _EMPTY_HASH
    layer = [
        hashlib.sha256(
            json.dumps(tx.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for tx in transactions
    ]
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])  # duplique la dernière feuille si nombre impair
        layer = [
            hashlib.sha256((layer[i] + layer[i + 1]).encode("utf-8")).hexdigest()
            for i in range(0, len(layer), 2)
        ]
    return layer[0]


class Block:
    def __init__(
        self,
        index: int,
        timestamp: float,
        transactions: list[Transaction],
        previous_hash: str,
        validator: str,
        validator_pubkey: str,
        signature: str | None = None,
        block_hash: str | None = None,
        version: int = BLOCK_VERSION,
    ) -> None:
        self.top = toplane(
            version=version,
            timestamp=float(timestamp),
            previous_hash=previous_hash,
            merkle_root=_merkle_root(transactions),
            txcount=len(transactions),
            author=validator,
            index=index,
        )
        self.bot = botlane(transactions)
        self.mid = midlane(
            etablissement=validator_pubkey,
            signature=signature,
            hash=None,
        )
        # On garde le hash fourni tel quel : comparé au hash recalculé, il
        # permet de détecter une falsification (cf. has_consistent_hash).
        self.mid.hash = block_hash if block_hash is not None else self.compute_hash()

    # --- propriétés de compatibilité (adossées aux trois lanes) -------------
    @property
    def index(self) -> int:
        return self.top.index

    @index.setter
    def index(self, value: int) -> None:
        self.top.index = value

    @property
    def timestamp(self) -> float:
        return self.top.timestamp

    @timestamp.setter
    def timestamp(self, value: float) -> None:
        self.top.timestamp = float(value)

    @property
    def previous_hash(self) -> str:
        return self.top.previous_hash

    @previous_hash.setter
    def previous_hash(self, value: str) -> None:
        self.top.previous_hash = value

    @property
    def validator(self) -> str:
        return self.top.author

    @validator.setter
    def validator(self, value: str) -> None:
        self.top.author = value

    @property
    def validator_pubkey(self) -> str:
        return self.mid.etablissement

    @validator_pubkey.setter
    def validator_pubkey(self, value: str) -> None:
        self.mid.etablissement = value

    @property
    def transactions(self) -> list[Transaction]:
        return self.bot.transactions

    @transactions.setter
    def transactions(self, value: list[Transaction]) -> None:
        self.bot.transactions = value

    @property
    def signature(self) -> str | None:
        return self.mid.signature

    @signature.setter
    def signature(self, value: str | None) -> None:
        self.mid.signature = value

    @property
    def hash(self) -> str:
        return self.mid.hash

    @hash.setter
    def hash(self, value: str) -> None:
        self.mid.hash = value

    @property
    def merkle_root(self) -> str:
        return self.top.merkle_root

    @property
    def version(self) -> int:
        return self.top.version

    @property
    def txcount(self) -> int:
        return self.top.txcount

    # --- hash / signature ----------------------------------------------------
    def _header(self) -> dict[str, Any]:
        # Recalcule merkle_root/txcount depuis les transactions courantes et
        # met l'en-tête à jour : toute falsification du contenu change le hash.
        self.top.merkle_root = _merkle_root(self.bot.transactions)
        self.top.txcount = len(self.bot.transactions)
        return {
            "version": self.top.version,
            "index": self.top.index,
            "timestamp": self.top.timestamp,
            "previous_hash": self.top.previous_hash,
            "merkle_root": self.top.merkle_root,
            "txcount": self.top.txcount,
            "author": self.top.author,
        }

    def compute_hash(self) -> str:
        raw = json.dumps(self._header(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def signing_bytes(self) -> bytes:
        return self.compute_hash().encode("utf-8")  # le validateur signe le hash

    def sign(self, private_key_hex: str) -> "Block":
        self.mid.signature = crypto.sign(private_key_hex, self.signing_bytes())
        self.mid.hash = self.compute_hash()
        return self

    def has_valid_signature(self) -> bool:
        if not self.signature:
            return False
        if crypto.address_from_public_key(self.validator_pubkey) != self.validator:
            return False
        return crypto.verify(self.validator_pubkey, self.signature, self.signing_bytes())

    def has_consistent_hash(self) -> bool:
        """Hash stocké == hash recalculé ? (détecte un contenu falsifié)."""
        return self.hash == self.compute_hash()

    # --- sérialisation -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "txcount": self.txcount,
            "validator": self.validator,
            "validator_pubkey": self.validator_pubkey,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "signature": self.signature,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Block":
        return cls(
            index=data["index"],
            timestamp=data["timestamp"],
            transactions=[Transaction.from_dict(t) for t in data["transactions"]],
            previous_hash=data["previous_hash"],
            validator=data["validator"],
            validator_pubkey=data["validator_pubkey"],
            signature=data.get("signature"),
            block_hash=data.get("hash"),
            version=data.get("version", BLOCK_VERSION),
        )

    def __repr__(self) -> str:  # pragma: no cover - confort de debug
        return (
            f"Block(index={self.index}, txs={len(self.transactions)}, "
            f"validator={self.validator[:12]}…, hash={self.hash[:12]}…)"
        )
