"""Transaction signée.

credit/debit = l'établissement attribue/consomme des points d'un client.
register/revoke = la racine agrée/révoque un établissement.
Champs sender/recipient/amount + public_key, timestamp, nonce (idempotence), signature.
"""

from __future__ import annotations

import json
from typing import Any

from . import crypto

VALUE_TYPES = {"credit", "debit"}           # déplacent des points
REGISTRY_TYPES = {"register", "revoke"}     # gouvernance
TX_TYPES = VALUE_TYPES | REGISTRY_TYPES | {"genesis"}


class Transaction:
    def __init__(
        self,
        tx_type: str,
        sender: str,
        recipient: str,
        amount: int,
        public_key: str,
        timestamp: float,
        nonce: str = "",
        signature: str | None = None,
    ) -> None:
        self.type = tx_type
        self.sender = sender
        self.recipient = recipient
        self.amount = int(amount)
        self.public_key = public_key
        self.timestamp = float(timestamp)
        self.nonce = nonce or ""
        self.signature = signature

    def _payload(self) -> dict[str, Any]:
        """Données signées (tout sauf la signature)."""
        return {
            "type": self.type,
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "public_key": self.public_key,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }

    def signing_bytes(self) -> bytes:
        """JSON canonique (trié) servant à signer/vérifier."""
        return json.dumps(
            self._payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        data = self._payload()
        data["signature"] = self.signature
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transaction":
        return cls(
            tx_type=data["type"],
            sender=data["sender"],
            recipient=data["recipient"],
            amount=data["amount"],
            public_key=data["public_key"],
            timestamp=data["timestamp"],
            nonce=data.get("nonce", ""),
            signature=data.get("signature"),
        )

    def sign(self, private_key_hex: str) -> "Transaction":
        self.signature = crypto.sign(private_key_hex, self.signing_bytes())
        return self

    def has_valid_signature(self) -> bool:
        # On vérifie aussi que adresse(public_key) == sender : sinon on pourrait
        # signer avec sa propre clé en se faisant passer pour un autre.
        if not self.signature:
            return False
        if crypto.address_from_public_key(self.public_key) != self.sender:
            return False
        return crypto.verify(self.public_key, self.signature, self.signing_bytes())

    def structural_error(self) -> str | None:
        """Message d'erreur si mal formée, sinon None. Ne regarde pas l'état
        (soldes/agréments) : c'est le rôle de la blockchain."""
        if self.type not in TX_TYPES:
            return f"type de transaction inconnu : {self.type!r}"
        if not self.sender or not self.recipient:
            return "sender et recipient sont obligatoires"
        if self.amount < 0:
            return "le montant ne peut pas être négatif"
        if self.type in VALUE_TYPES and self.amount <= 0:
            return "un crédit/débit doit porter sur un montant strictement positif"
        if self.type in REGISTRY_TYPES and self.amount != 0:
            return "une transaction de registre doit avoir un montant nul"
        if not self.has_valid_signature():
            return "signature invalide ou clé publique ne correspondant pas à l'émetteur"
        return None

    def __repr__(self) -> str:  # pragma: no cover - confort de debug
        return (
            f"Transaction(type={self.type!r}, sender={self.sender[:12]}…, "
            f"recipient={self.recipient[:12]}…, amount={self.amount})"
        )
