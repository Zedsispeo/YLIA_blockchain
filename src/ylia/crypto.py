"""Crypto YLIA : clés, signatures ECDSA (SECP256k1) et adresses.

Signatures déterministes (RFC 6979) pour que le genesis soit identique partout.
Adresse = SHA-256(clé publique), préfixée "YLIA".
"""

from __future__ import annotations

import hashlib

from ecdsa import SECP256k1, BadSignatureError, SigningKey, VerifyingKey

CURVE = SECP256k1
ADDRESS_PREFIX = "YLIA"
_ADDRESS_HEX_LEN = 40  # 160 bits


def generate_keypair() -> tuple[str, str]:
    """Nouvelle paire (clé privée hex, clé publique hex)."""
    sk = SigningKey.generate(curve=CURVE)
    return sk.to_string().hex(), sk.get_verifying_key().to_string().hex()


def _signing_key(private_key_hex: str) -> SigningKey:
    return SigningKey.from_string(bytes.fromhex(private_key_hex), curve=CURVE)


def _verifying_key(public_key_hex: str) -> VerifyingKey:
    return VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=CURVE)


def public_key_from_private(private_key_hex: str) -> str:
    return _signing_key(private_key_hex).get_verifying_key().to_string().hex()


def address_from_public_key(public_key_hex: str) -> str:
    digest = hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()
    return ADDRESS_PREFIX + digest[:_ADDRESS_HEX_LEN]


def address_from_private_key(private_key_hex: str) -> str:
    return address_from_public_key(public_key_from_private(private_key_hex))


def sign(private_key_hex: str, message: bytes) -> str:
    sig = _signing_key(private_key_hex).sign_deterministic(message, hashfunc=hashlib.sha256)
    return sig.hex()


def verify(public_key_hex: str, signature_hex: str, message: bytes) -> bool:
    """Vérifie une signature. Ne lève jamais : False si entrée invalide."""
    try:
        vk = _verifying_key(public_key_hex)
        return vk.verify(bytes.fromhex(signature_hex), message, hashfunc=hashlib.sha256)
    except (BadSignatureError, ValueError, AssertionError):
        return False
    except Exception:
        # hex invalide, mauvaise longueur de clé, etc. → signature invalide
        return False
