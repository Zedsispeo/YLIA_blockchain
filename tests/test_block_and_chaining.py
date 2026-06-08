"""Tests de la structure de bloc, du hash déterministe et du chaînage.

Couvre le point de démonstration : « Création d'un bloc et vérification du
chaînage (hash précédent cohérent) ».
"""

from ylia import crypto
from ylia.blockchain import Blockchain
from ylia.config import ROOT_PRIVATE_KEY

from helpers import make_signed_tx


def test_genesis_block_exists_and_is_first():
    chain = Blockchain()
    genesis = chain.chain[0]
    assert genesis.index == 0
    assert genesis.previous_hash == "0" * 64
    assert genesis.transactions[0].type == "genesis"


def test_block_hash_is_deterministic():
    chain = Blockchain()
    genesis = chain.chain[0]
    assert genesis.hash == genesis.compute_hash()


def test_genesis_is_identical_across_nodes():
    # Deux nœuds indépendants doivent calculer EXACTEMENT le même genesis.
    assert Blockchain().chain[0].hash == Blockchain().chain[0].hash


def test_chaining_previous_hash_is_consistent():
    chain = Blockchain()
    chain.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAclient", 10))
    block = chain.mine(ROOT_PRIVATE_KEY)
    assert block.index == 1
    assert block.previous_hash == chain.chain[0].hash
    assert chain.is_chain_valid()


def test_block_signature_binds_to_validator():
    chain = Blockchain()
    block = chain.mine(ROOT_PRIVATE_KEY)
    assert block.has_valid_signature()
    # La clé publique du validateur correspond bien à son adresse.
    assert crypto.address_from_public_key(block.validator_pubkey) == block.validator
