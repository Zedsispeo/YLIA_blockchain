"""Factory de l'app Flask : attache une blockchain + l'identité du nœud, branche
la gestion d'erreurs et les routes. Chaque test peut créer son app isolée.
"""

from __future__ import annotations

from flask import Flask

from .. import crypto
from ..blockchain import Blockchain
from ..config import ROOT_PRIVATE_KEY
from .errors import register_error_handlers
from .routes import bp

__all__ = ["create_app"]


def create_app(
    blockchain: Blockchain | None = None,
    node_private_key: str | None = None,
) -> Flask:
    app = Flask(__name__)
    app.url_map.strict_slashes = False  # /chain == /chain/

    chain = blockchain if blockchain is not None else Blockchain()
    # Sans identité fournie, on retombe sur la racine : create_app reste utilisable
    # en mémoire (tests/lib). L'identité propre et persistée d'un nœud est résolue
    # en amont, au démarrage (main.py → identity.resolve_node_key).
    node_key = node_private_key or ROOT_PRIVATE_KEY
    public_key = crypto.public_key_from_private(node_key)
    address = crypto.address_from_public_key(public_key)

    # Partagé avec les routes via current_app.
    app.blockchain = chain  # type: ignore[attr-defined]
    app.node_identity = {  # type: ignore[attr-defined]
        "private_key": node_key,
        "public_key": public_key,
        "address": address,
    }

    register_error_handlers(app)
    app.register_blueprint(bp)
    return app
