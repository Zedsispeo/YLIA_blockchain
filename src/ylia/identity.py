"""Persistance de l'identité d'un nœud (sa clé privée).

Chaque nœud possède une identité propre — une clé privée — qui détermine son
adresse on-chain (et donc s'il est, ou non, une autorité agréée). Pour qu'un
conteneur Docker retrouve la **même** identité après un redémarrage, la clé est
stockée dans un fichier `.key`, à côté de la chaîne `.ylia`, dans son volume.

Résolution de l'identité au démarrage (par ordre de priorité) :
  1. clé explicite (``--node-key`` / ``YLIA_NODE_KEY``) → utilisée telle quelle ;
  2. fichier ``.key`` existant → rechargée (identité stable du conteneur) ;
  3. sinon → une nouvelle clé est générée puis écrite dans le fichier ``.key``.

Lecture TOLÉRANTE : fichier absent / illisible / clé invalide → None ; l'appelant
génère alors une nouvelle identité. Écriture avec droits restreints (0600) : la
clé privée est un secret.
"""

from __future__ import annotations

import os
import tempfile

from . import crypto


def load_node_key(path: str) -> str | None:
    """Clé privée hex stockée, ou None si absente / illisible / invalide."""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            key = f.read().strip()
    except OSError:
        return None
    if not key:
        return None
    try:
        crypto.public_key_from_private(key)  # valide la clé (hex + longueur)
    except Exception:
        return None  # contenu corrompu → on régénérera
    return key


def save_node_key(path: str, private_key_hex: str) -> None:
    """Écrit la clé privée du nœud de façon atomique, en droits 0600 (secret)."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)

    # tmp dans le MÊME répertoire → os.replace atomique (même système de fichiers).
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".key-", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(private_key_hex)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def resolve_node_key(
    key_path: str, explicit_key: str | None = None, force_new: bool = False
) -> str:
    """Identité du nœud : clé explicite > fichier ``.key`` existant > nouvelle clé persistée.

    ``explicit_key`` (CLI/env) l'emporte et n'est pas écrite (déjà stable par ailleurs).
    ``force_new`` ignore le fichier et génère une nouvelle identité (rotation), puis la persiste.
    """
    if explicit_key:
        return explicit_key
    if not force_new:
        existing = load_node_key(key_path)
        if existing:
            return existing
    private_key, _ = crypto.generate_keypair()
    save_node_key(key_path, private_key)
    return private_key
