"""Tests : ajout de transactions, minage, mise à jour des soldes.

Couvre : « Ajout de transactions puis minage d'un bloc les contenant ».
"""

import pytest

from ylia import crypto
from ylia.blockchain import Blockchain, ChainError
from ylia.config import ROOT_PRIVATE_KEY

from helpers import make_signed_tx, register_establishment


def test_pending_then_mined_into_block():
    chain = Blockchain()
    client = "YLIAclientA"
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, client, 50))
    assert len(chain.pending_transactions) == 1

    block = chain.mine(ROOT_PRIVATE_KEY)
    assert len(block.transactions) == 1
    assert chain.pending_transactions == []  # mempool vidé après minage


def test_credit_increases_balance():
    chain = Blockchain()
    client = "YLIAclientB"
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, client, 120))
    chain.mine(ROOT_PRIVATE_KEY)
    assert chain.balance_of(client) == 120


def test_debit_decreases_balance():
    chain = Blockchain()
    client = "YLIAclientC"
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, client, 100))
    chain.mine(ROOT_PRIVATE_KEY)
    chain.add_transaction(make_signed_tx("debit", ROOT_PRIVATE_KEY, client, 30))
    chain.mine(ROOT_PRIVATE_KEY)
    assert chain.balance_of(client) == 70


def test_debit_rejected_when_insufficient_balance():
    chain = Blockchain()
    client = "YLIAclientD"
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, client, 10))
    chain.mine(ROOT_PRIVATE_KEY)
    with pytest.raises(ChainError):
        chain.add_transaction(make_signed_tx("debit", ROOT_PRIVATE_KEY, client, 999))


def test_duplicate_nonce_is_rejected():
    """Idempotence : un même émetteur ne peut pas réutiliser un nonce."""
    chain = Blockchain()
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAn", 10, nonce="op-1"))
    with pytest.raises(ChainError):
        chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAn", 10, nonce="op-1"))


def test_different_nonces_are_allowed():
    chain = Blockchain()
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAn", 10, nonce="op-1"))
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAn", 10, nonce="op-2"))
    assert len(chain.pending_transactions) == 2


def test_nonce_unique_per_sender_survives_mining():
    chain = Blockchain()
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAn", 10, nonce="op-1"))
    chain.mine(ROOT_PRIVATE_KEY)
    # Le nonce est désormais inscrit dans la chaîne : rejeu refusé.
    with pytest.raises(ChainError):
        chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAn", 10, nonce="op-1"))


def test_points_are_universal_across_establishments():
    # Un client gagne chez A, dépense chez B : solde global partagé.
    chain = Blockchain()
    priv_a, _ = crypto.generate_keypair()
    priv_b, _ = crypto.generate_keypair()
    register_establishment(chain, priv_a)
    register_establishment(chain, priv_b)
    client = "YLIAclientUniv"

    chain.add_transaction(make_signed_tx("credit", priv_a, client, 80))
    chain.mine(ROOT_PRIVATE_KEY)
    chain.add_transaction(make_signed_tx("debit", priv_b, client, 30))
    chain.mine(ROOT_PRIVATE_KEY)
    assert chain.balance_of(client) == 50
