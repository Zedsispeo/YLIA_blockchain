"""Fonctions utilitaires partagées par les tests."""

import time

from ylia import crypto
from ylia.config import ROOT_PRIVATE_KEY
from ylia.transaction import Transaction


def make_signed_tx(tx_type, private_key, recipient, amount=0, timestamp=None, nonce=""):
    """Crée et signe une transaction avec ``private_key``."""
    public_key = crypto.public_key_from_private(private_key)
    sender = crypto.address_from_public_key(public_key)
    tx = Transaction(
        tx_type=tx_type,
        sender=sender,
        recipient=recipient,
        amount=amount,
        public_key=public_key,
        timestamp=timestamp if timestamp is not None else time.time(),
        nonce=nonce,
    )
    tx.sign(private_key)
    return tx


def register_establishment(chain, establishment_private_key):
    """Agrée un établissement via la racine, puis mine le bloc.
    Retourne l'adresse de l'établissement."""
    address = crypto.address_from_private_key(establishment_private_key)
    chain.add_transaction(make_signed_tx("register", ROOT_PRIVATE_KEY, address, 0))
    chain.mine(ROOT_PRIVATE_KEY)
    return address
