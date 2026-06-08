"""Tests de détection de falsification.

Couvre : « Détection d'une chaîne falsifiée (bloc modifié → chaîne invalide) ».
"""

from ylia.blockchain import Blockchain
from ylia.config import ROOT_PRIVATE_KEY

from helpers import make_signed_tx


def _chain_with_history():
    chain = Blockchain()
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAvictime", 100))
    chain.mine(ROOT_PRIVATE_KEY)
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAautre", 40))
    chain.mine(ROOT_PRIVATE_KEY)
    return chain


def test_valid_chain_is_valid():
    assert _chain_with_history().is_chain_valid() is True


def test_tampering_amount_invalidates_chain():
    chain = _chain_with_history()
    # Un attaquant gonfle un montant déjà inscrit.
    chain.chain[1].transactions[0].amount = 1_000_000
    ok, reason = chain.validate_chain()
    assert ok is False
    # Soit le hash ne colle plus, soit la signature de la transaction casse.
    assert reason is not None


def test_tampering_transaction_is_caught_even_if_block_is_resigned():
    # Même en re-signant le bloc (hash + signature de bloc cohérents), la
    # signature de la TRANSACTION ne colle plus → détecté. On falsifie le
    # dernier bloc pour isoler cette défense (sinon le chaînage casse avant).
    chain = Blockchain()
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAvictime", 100))
    chain.mine(ROOT_PRIVATE_KEY)

    block = chain.chain[-1]
    block.transactions[0].amount = 999      # falsification du montant
    block.sign(ROOT_PRIVATE_KEY)            # re-signe le bloc + recalcule son hash

    assert block.has_consistent_hash()      # hash de bloc cohérent…
    assert block.has_valid_signature()      # …et signature de bloc valide…
    ok, reason = chain.validate_chain()     # …mais la chaîne reste invalide
    assert ok is False
    assert "transaction invalide" in reason


def test_breaking_previous_hash_link_invalidates_chain():
    chain = _chain_with_history()
    chain.chain[2].previous_hash = "f" * 64
    ok, reason = chain.validate_chain()
    assert ok is False
    assert "chaînage" in reason or "previous_hash" in reason
