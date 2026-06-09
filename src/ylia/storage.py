"""Persistance de la chaîne sur disque (JSON).

But : qu'un nœud survive à un redémarrage et reparte de son dernier état au lieu
du seul genesis.

- Écriture ATOMIQUE (fichier temporaire dans le même répertoire + os.replace) :
  un crash en cours d'écriture ne corrompt jamais le fichier existant.
- Lecture TOLÉRANTE : fichier absent, illisible ou malformé → None ; l'appelant
  (Blockchain) retombe alors proprement sur le genesis.

Ce module ne connaît pas Blockchain : il reçoit un objet exposant `to_dict()` et
`peers` (duck typing), ce qui évite tout import circulaire.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any


def save_chain(path: str, blockchain) -> None:
    """Sauvegarde la chaîne et la liste des pairs ({"chain": [...], "peers": [...]})."""
    payload = blockchain.to_dict()
    payload["peers"] = sorted(blockchain.peers)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)

    # tmp dans le MÊME répertoire → os.replace est atomique (même système de fichiers).
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".chain-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_payload(path: str) -> dict[str, Any] | None:
    """Contenu JSON du fichier, ou None si absent / illisible / malformé."""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def load_chain(path: str) -> list[dict[str, Any]] | None:
    """Liste brute des blocs stockés, ou None si absent / illisible / malformé."""
    data = _load_payload(path)
    if data is None:
        return None
    chain = data.get("chain")
    if not isinstance(chain, list):
        return None
    return chain


def load_peers(path: str) -> list[str] | None:
    """Liste des pairs stockés, ou None si absent / illisible / malformé."""
    data = _load_payload(path)
    if data is None:
        return None
    peers = data.get("peers")
    if not isinstance(peers, list):
        return None
    return [p for p in peers if isinstance(p, str)]
