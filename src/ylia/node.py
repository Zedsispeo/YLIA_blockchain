"""Appels HTTP vers les pairs. Gardé hors de Blockchain, qui reste testable
sans réseau. Tout est best-effort : un pair injoignable est ignoré."""

from __future__ import annotations

from typing import Any

import requests

from .config import PEER_TIMEOUT


def fetch_peer_chain(peer_url: str, timeout: float = PEER_TIMEOUT) -> list[dict[str, Any]] | None:
    """Chaîne d'un pair, ou None si injoignable / réponse invalide."""
    try:
        resp = requests.get(f"{peer_url}/chain", timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("chain")
    except (requests.RequestException, ValueError):
        return None


def gather_peer_chains(peers, timeout: float = PEER_TIMEOUT) -> list[list[dict[str, Any]]]:
    chains = []
    for peer in peers:
        chain = fetch_peer_chain(peer, timeout=timeout)
        if chain is not None:
            chains.append(chain)
    return chains


def broadcast_transaction(peers, tx_dict: dict[str, Any], timeout: float = PEER_TIMEOUT) -> None:
    # broadcast=false : le pair ne re-diffuse pas → pas de boucle.
    for peer in peers:
        try:
            requests.post(f"{peer}/transactions/new?broadcast=false", json=tx_dict, timeout=timeout)
        except requests.RequestException:
            pass


def broadcast_block(peers, timeout: float = PEER_TIMEOUT) -> None:
    # On pousse les pairs à relancer leur résolution de conflits.
    for peer in peers:
        try:
            requests.get(f"{peer}/nodes/resolve", timeout=timeout)
        except requests.RequestException:
            pass
