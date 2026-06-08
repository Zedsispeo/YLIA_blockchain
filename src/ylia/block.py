"""Bloc : index, timestamp, transactions, previous_hash, hash SHA-256, et le
champ de consensus PoA (validator + validator_pubkey + signature).

Le hash porte sur l'en-tête (JSON trié), hors hash et signature → reproductible.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from . import crypto
from .transaction import Transaction


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
    ) -> None:
        self.index = index
        self.timestamp = float(timestamp)
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.validator = validator
        self.validator_pubkey = validator_pubkey
        self.signature = signature
        # On garde le hash fourni tel quel : comparé au hash recalculé, il
        # permet de détecter une falsification (cf. has_consistent_hash).
        self.hash = block_hash if block_hash is not None else self.compute_hash()

    def _header(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "validator": self.validator,
            "validator_pubkey": self.validator_pubkey,
        }

    def compute_hash(self) -> str:
        raw = json.dumps(self._header(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def signing_bytes(self) -> bytes:
        return self.compute_hash().encode("utf-8")  # le validateur signe le hash

    def sign(self, private_key_hex: str) -> "Block":
        self.signature = crypto.sign(private_key_hex, self.signing_bytes())
        self.hash = self.compute_hash()
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "validator": self.validator,
            "validator_pubkey": self.validator_pubkey,
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
        )

    def __repr__(self) -> str:  # pragma: no cover - confort de debug
        return (
            f"Block(index={self.index}, txs={len(self.transactions)}, "
            f"validator={self.validator[:12]}…, hash={self.hash[:12]}…)"
        )
