"""Tests de la cryptographie réelle (ECDSA / SECP256k1)."""

from ylia import crypto


def test_keypair_and_address_are_consistent():
    priv, pub = crypto.generate_keypair()
    assert crypto.public_key_from_private(priv) == pub
    addr = crypto.address_from_public_key(pub)
    assert addr == crypto.address_from_private_key(priv)
    assert addr.startswith("YLIA")


def test_sign_and_verify_roundtrip():
    priv, pub = crypto.generate_keypair()
    msg = b"bonjour YLIA"
    sig = crypto.sign(priv, msg)
    assert crypto.verify(pub, sig, msg) is True


def test_signature_is_deterministic():
    priv, _ = crypto.generate_keypair()
    msg = b"meme message"
    assert crypto.sign(priv, msg) == crypto.sign(priv, msg)


def test_verify_rejects_tampered_message():
    priv, pub = crypto.generate_keypair()
    sig = crypto.sign(priv, b"montant: 50")
    assert crypto.verify(pub, sig, b"montant: 5000") is False


def test_verify_rejects_wrong_key():
    priv, _ = crypto.generate_keypair()
    _, other_pub = crypto.generate_keypair()
    sig = crypto.sign(priv, b"data")
    assert crypto.verify(other_pub, sig, b"data") is False


def test_verify_never_crashes_on_garbage():
    assert crypto.verify("zz", "zz", b"x") is False
