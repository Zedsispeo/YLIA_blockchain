"""Tests du consensus Proof of Authority.

Couvre : « Validité du consensus (un bloc/transaction au consensus invalide
est rejeté) » et la gouvernance des agréments (register / revoke).
"""

import time

import pytest

from ylia import crypto
from ylia.block import Block
from ylia.blockchain import Blockchain, ChainError
from ylia.config import ROOT_PRIVATE_KEY

from helpers import make_signed_tx, register_establishment


def test_non_authority_cannot_emit_transaction():
    chain = Blockchain()
    outsider_priv, _ = crypto.generate_keypair()  # jamais agréé
    with pytest.raises(ChainError):
        chain.add_transaction(make_signed_tx("credit", outsider_priv, "YLIAclient", 10))


def test_non_authority_cannot_mine():
    chain = Blockchain()
    outsider_priv, _ = crypto.generate_keypair()
    with pytest.raises(ChainError):
        chain.mine(outsider_priv)


def test_register_grants_authority():
    chain = Blockchain()
    priv, _ = crypto.generate_keypair()
    address = register_establishment(chain, priv)
    assert address in chain.current_authorities()
    # Désormais il peut émettre.
    chain.add_transaction(make_signed_tx("credit", priv, "YLIAclientX", 5))
    chain.mine(ROOT_PRIVATE_KEY)
    assert chain.balance_of("YLIAclientX") == 5


def test_revoke_removes_authority():
    chain = Blockchain()
    priv, _ = crypto.generate_keypair()
    address = register_establishment(chain, priv)
    chain.add_transaction(make_signed_tx("revoke", ROOT_PRIVATE_KEY, address, 0))
    chain.mine(ROOT_PRIVATE_KEY)
    assert address not in chain.current_authorities()
    with pytest.raises(ChainError):
        chain.add_transaction(make_signed_tx("credit", priv, "YLIAclientY", 5))


def test_non_root_cannot_register():
    chain = Blockchain()
    priv, _ = crypto.generate_keypair()
    register_establishment(chain, priv)  # priv devient autorité (mais pas racine)
    victim_priv, _ = crypto.generate_keypair()
    victim_addr = crypto.address_from_private_key(victim_priv)
    # Une autorité non-racine tente d'agréer quelqu'un : refusé.
    with pytest.raises(ChainError):
        chain.add_transaction(make_signed_tx("register", priv, victim_addr, 0))


def test_block_signed_by_non_authority_is_rejected_by_validation():
    chain = Blockchain()
    outsider_priv = "00" * 31 + "07"  # clé déterministe, non agréée
    outsider_pub = crypto.public_key_from_private(outsider_priv)
    outsider_addr = crypto.address_from_public_key(outsider_pub)

    forged = Block(
        index=1,
        timestamp=time.time(),
        transactions=[],
        previous_hash=chain.last_block.hash,
        validator=outsider_addr,
        validator_pubkey=outsider_pub,
    )
    forged.sign(outsider_priv)
    chain.chain.append(forged)  # on force l'ajout sans passer par mine()

    ok, reason = chain.validate_chain()
    assert ok is False
    assert "non agréé" in reason
