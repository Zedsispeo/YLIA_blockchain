"""Tests de la résolution de conflits entre nœuds.

Couvre : « Résolution de conflits : deux nœuds en désaccord convergent vers la
même chaîne ».
"""

from ylia.blockchain import Blockchain
from ylia.config import ROOT_PRIVATE_KEY

from helpers import make_signed_tx


def _raw(chain):
    """Sérialise une chaîne au format brut (comme renvoyé par /chain)."""
    return [b.to_dict() for b in chain.chain]


def test_longer_valid_chain_is_adopted():
    node_a = Blockchain()
    node_b = Blockchain()

    # A mine 3 blocs ; B n'en mine qu'un.
    for i in range(3):
        node_a.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, f"YLIAc{i}", 10))
        node_a.mine(ROOT_PRIVATE_KEY)
    node_b.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIAz", 5))
    node_b.mine(ROOT_PRIVATE_KEY)

    assert len(node_a.chain) == 4 and len(node_b.chain) == 2

    replaced = node_b.resolve_conflicts([_raw(node_a)])
    assert replaced is True
    assert len(node_b.chain) == 4
    # Convergence : même chaîne (mêmes hash).
    assert [b.hash for b in node_b.chain] == [b.hash for b in node_a.chain]


def test_shorter_chain_is_not_adopted():
    node_a = Blockchain()
    node_b = Blockchain()
    for i in range(2):
        node_a.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, f"YLIAa{i}", 10))
        node_a.mine(ROOT_PRIVATE_KEY)
    # B est plus long ; on lui propose la chaîne plus courte de A → ignorée.
    for i in range(4):
        node_b.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, f"YLIAb{i}", 10))
        node_b.mine(ROOT_PRIVATE_KEY)
    replaced = node_b.resolve_conflicts([_raw(node_a)])
    assert replaced is False
    assert len(node_b.chain) == 5


def test_invalid_longer_chain_is_rejected():
    node_a = Blockchain()
    node_b = Blockchain()
    for i in range(3):
        node_a.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, f"YLIAv{i}", 10))
        node_a.mine(ROOT_PRIVATE_KEY)
    # On falsifie la chaîne (plus longue) de A avant de la proposer à B.
    raw = _raw(node_a)
    raw[1]["transactions"][0]["amount"] = 10**9
    replaced = node_b.resolve_conflicts([raw])
    assert replaced is False  # plus longue MAIS invalide → rejetée
    assert len(node_b.chain) == 1


def test_pending_revalidated_after_reorg_unblocks_mining():
    """Régression : après adoption d'une chaîne plus longue, une transaction en
    attente devenue invalide (débit non financé) doit être purgée du mempool,
    sinon le nœud ne pourrait plus miner aucun bloc."""
    node_b = Blockchain()
    node_b.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, "YLIArich", 100))
    node_b.mine(ROOT_PRIVATE_KEY)
    # B met un débit de 80 en attente (financé par le crédit de 100).
    node_b.add_transaction(make_signed_tx("debit", ROOT_PRIVATE_KEY, "YLIArich", 80))
    assert len(node_b.pending_transactions) == 1
    assert node_b.available_balance("YLIArich") == 20

    # A produit une chaîne plus longue où le crédit n'a jamais eu lieu.
    node_a = Blockchain()
    for _ in range(3):
        node_a.mine(ROOT_PRIVATE_KEY)
    assert len(node_a.chain) == 4 and len(node_b.chain) == 2

    assert node_b.resolve_conflicts([_raw(node_a)]) is True
    assert node_b.balance_of("YLIArich") == 0
    # Le débit non financé a été retiré : mempool sain, pas de solde négatif.
    assert node_b.pending_transactions == []
    assert node_b.available_balance("YLIArich") == 0
    # Le minage fonctionne de nouveau (aucune exception).
    node_b.mine(ROOT_PRIVATE_KEY)
    assert len(node_b.chain) == 5
