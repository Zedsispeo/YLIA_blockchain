"""Tests de la persistance de l'identité d'un nœud (fichier .key)."""

import os

from ylia import crypto, identity


def test_resolve_generates_and_persists_when_absent(tmp_path):
    path = str(tmp_path / "node.key")
    key = identity.resolve_node_key(path)

    # Une clé valide a été générée ET écrite sur disque.
    assert crypto.public_key_from_private(key)  # ne lève pas
    assert os.path.exists(path)
    assert identity.load_node_key(path) == key


def test_resolve_reloads_same_identity_across_restart(tmp_path):
    path = str(tmp_path / "node.key")
    first = identity.resolve_node_key(path)
    # Un "redémarrage" du conteneur retrouve la même identité.
    second = identity.resolve_node_key(path)
    assert first == second


def test_explicit_key_takes_precedence_and_is_not_written(tmp_path):
    path = str(tmp_path / "node.key")
    explicit, _ = crypto.generate_keypair()
    assert identity.resolve_node_key(path, explicit_key=explicit) == explicit
    # Une clé explicite (CLI/env) n'écrase pas le fichier .key.
    assert not os.path.exists(path)


def test_force_new_rotates_and_overwrites(tmp_path):
    path = str(tmp_path / "node.key")
    original = identity.resolve_node_key(path)
    rotated = identity.resolve_node_key(path, force_new=True)
    assert rotated != original
    # La nouvelle identité est persistée et rechargée ensuite.
    assert identity.load_node_key(path) == rotated
    assert identity.resolve_node_key(path) == rotated


def test_load_is_tolerant_to_missing_and_corrupt(tmp_path):
    assert identity.load_node_key(str(tmp_path / "absent.key")) is None

    corrupt = tmp_path / "corrupt.key"
    corrupt.write_text("pas une cle hex valide")
    assert identity.load_node_key(str(corrupt)) is None


def test_saved_key_file_is_not_world_readable(tmp_path):
    path = str(tmp_path / "node.key")
    identity.resolve_node_key(path)
    mode = os.stat(path).st_mode & 0o777
    # La clé privée est un secret : pas de droits pour group/other.
    assert mode == 0o600
