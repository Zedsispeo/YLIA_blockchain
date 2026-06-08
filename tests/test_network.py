"""Tests de la couche réseau (node.py) et des endpoints réseau de l'API.

On simule les appels HTTP (``requests``) avec monkeypatch pour exercer la
logique sans démarrer de vrais serveurs : gestion des pairs injoignables,
filtrage, diffusion best-effort, résolution de conflits, et rejet 403 du
minage par un nœud non agréé.
"""

import pytest
import requests

from ylia import crypto, node
from ylia.api import create_app
from ylia.blockchain import Blockchain
from ylia.config import ROOT_PRIVATE_KEY

from helpers import make_signed_tx


class FakeResponse:
    def __init__(self, json_data, status=200):
        self._json = json_data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


# --- node.py -----------------------------------------------------------------

def test_fetch_peer_chain_success(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse({"chain": [1, 2, 3]}))
    assert node.fetch_peer_chain("http://peer") == [1, 2, 3]


def test_fetch_peer_chain_unreachable_returns_none(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("injoignable")

    monkeypatch.setattr(requests, "get", boom)
    assert node.fetch_peer_chain("http://peer") is None


def test_gather_peer_chains_filters_unreachable(monkeypatch):
    def get(url, **k):
        if "good" in url:
            return FakeResponse({"chain": [{"index": 0}]})
        raise requests.ConnectionError("injoignable")

    monkeypatch.setattr(requests, "get", get)
    chains = node.gather_peer_chains(["http://good", "http://bad"])
    assert chains == [[{"index": 0}]]


def test_broadcast_transaction_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("injoignable")

    monkeypatch.setattr(requests, "post", boom)
    # Ne doit pas lever même si tous les pairs sont injoignables.
    node.broadcast_transaction(["http://a", "http://b"], {"type": "credit"})


# --- API : /mine 403 et /nodes/resolve --------------------------------------

def test_mine_forbidden_for_non_authority_node():
    outsider_key, _ = crypto.generate_keypair()  # identité jamais agréée
    app = create_app(blockchain=Blockchain(), node_private_key=outsider_key)
    resp = app.test_client().get("/mine")
    assert resp.status_code == 403
    assert "error" in resp.get_json()


def test_resolve_adopts_longer_chain_via_endpoint(monkeypatch):
    # Une autre blockchain produit une chaîne plus longue valide.
    other = Blockchain()
    for i in range(3):
        other.add_transaction(make_signed_tx("credit", ROOT_PRIVATE_KEY, f"YLIAc{i}", 10))
        other.mine(ROOT_PRIVATE_KEY)
    longer = [b.to_dict() for b in other.chain]

    app = create_app(blockchain=Blockchain())
    app.blockchain.register_peer("http://peer")
    monkeypatch.setattr(node, "gather_peer_chains", lambda peers, **k: [longer])

    data = app.test_client().get("/nodes/resolve").get_json()
    assert data["replaced"] is True
    assert data["length"] == 4


def test_resolve_keeps_chain_when_no_peer_longer(monkeypatch):
    app = create_app(blockchain=Blockchain())
    monkeypatch.setattr(node, "gather_peer_chains", lambda peers, **k: [])
    data = app.test_client().get("/nodes/resolve").get_json()
    assert data["replaced"] is False
    assert data["length"] == 1
