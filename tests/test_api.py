"""Tests de l'API Flask (endpoints du sujet + endpoints YLIA)."""

import pytest

from ylia.api import create_app
from ylia.blockchain import Blockchain


@pytest.fixture
def app():
    return create_app(blockchain=Blockchain())


@pytest.fixture
def client(app):
    return app.test_client()


def test_get_chain(client):
    resp = client.get("/chain")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["length"] == 1
    assert data["chain"][0]["index"] == 0


def test_post_transaction_with_root_signing(client):
    resp = client.post(
        "/transactions/new",
        json={"type": "credit", "recipient": "YLIAclient", "amount": 25, "use_root": True},
    )
    assert resp.status_code == 201
    assert resp.get_json()["block_index"] == 1


def test_unsigned_transaction_is_rejected(client):
    resp = client.post(
        "/transactions/new",
        json={"type": "credit", "recipient": "YLIAclient", "amount": 25},
    )
    assert resp.status_code == 400


def test_mine_then_balance(client):
    client.post(
        "/transactions/new",
        json={"recipient": "YLIArich", "amount": 200, "use_root": True},
    )
    mine = client.get("/mine")
    assert mine.status_code == 200
    assert mine.get_json()["block"]["index"] == 1

    bal = client.get("/balance/YLIArich").get_json()
    assert bal["balance"] == 200


def test_validate_endpoint(client):
    resp = client.get("/validate")
    assert resp.get_json()["valid"] is True


def test_authority_register_flow(client):
    wallet = client.get("/wallet/new").get_json()
    resp = client.post("/authorities/register", json={"address": wallet["address"]})
    assert resp.status_code == 201
    client.get("/mine")
    auth = client.get("/authorities").get_json()
    assert wallet["address"] in auth["authorities"]


def test_nodes_register_and_list(client):
    resp = client.post("/nodes/register", json={"nodes": ["http://127.0.0.1:5001"]})
    assert resp.status_code == 201
    listed = client.get("/nodes").get_json()
    assert "http://127.0.0.1:5001" in listed["peers"]


def test_node_info(client):
    info = client.get("/node").get_json()
    assert info["is_authority"] is True  # le nœud opère en tant que racine
    assert info["is_root"] is True


def test_client_signed_transaction_is_accepted(client):
    # Transaction pré-signée côté client (mode "production").
    from ylia import crypto
    from ylia.transaction import Transaction
    from ylia.config import ROOT_PRIVATE_KEY

    pub = crypto.public_key_from_private(ROOT_PRIVATE_KEY)
    tx = Transaction("credit", crypto.address_from_public_key(pub), "YLIApresigned", 12, pub, 1234.0)
    tx.sign(ROOT_PRIVATE_KEY)
    resp = client.post("/transactions/new", json=tx.to_dict())
    assert resp.status_code == 201


def test_index_is_self_documenting(client):
    data = client.get("/").get_json()
    assert data["name"] == "YLIA"
    assert "GET /chain" in data["endpoints"]
    assert data["node"]["is_root"] is True


def test_health(client):
    data = client.get("/health").get_json()
    assert data["status"] == "ok"
    assert data["chain_length"] == 1


def test_unknown_route_returns_json_404(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_method_not_allowed_returns_json_405(client):
    resp = client.post("/chain")  # /chain est en GET uniquement
    assert resp.status_code == 405
    assert "error" in resp.get_json()


def test_clear_pending_endpoint(client):
    client.post("/transactions/new", json={"recipient": "YLIAx", "amount": 5, "use_root": True})
    assert client.get("/pending").get_json()["count"] == 1
    client.delete("/transactions/pending")
    assert client.get("/pending").get_json()["count"] == 0


def test_malformed_body_is_rejected(client):
    resp = client.post("/transactions/new", data="ceci n'est pas du json",
                       content_type="application/json")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_idempotent_transaction_via_nonce(client):
    body = {"recipient": "YLIAdup", "amount": 5, "use_root": True, "nonce": "facture-42"}
    assert client.post("/transactions/new", json=body).status_code == 201
    # Même nonce → rejet (anti double-comptage).
    assert client.post("/transactions/new", json=body).status_code == 400
