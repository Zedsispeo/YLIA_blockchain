"""Factory de l'app Flask : attache une blockchain + l'identité du nœud, branche
la gestion d'erreurs et les routes. Chaque test peut créer son app isolée.
"""

from __future__ import annotations

from flask import Flask, render_template, request, jsonify, redirect
from pathlib import Path
from typing import Any

from ..transaction import Transaction

from .. import crypto
from ..blockchain import Blockchain
from ..config import NODE_PRIVATE_KEY
from .errors import register_error_handlers
from .routes import bp

__all__ = ["create_app"]


def create_app(
    blockchain: Blockchain | None = None,
    node_private_key: str | None = None,
) -> Flask:
    # Serve the frontend located in src/flask/templates and src/flask/static
    template_dir = str(Path(__file__).resolve().parents[1].parent / 'flask' / 'templates')
    static_dir = str(Path(__file__).resolve().parents[1].parent / 'flask' / 'static')
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.url_map.strict_slashes = False  # /chain == /chain/

    chain = blockchain if blockchain is not None else Blockchain()
    node_key = node_private_key or NODE_PRIVATE_KEY
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
    # Compatibility: expose the frontend at /ui and simple demo helpers
    app.logs: list[dict[str, Any]] = []

    def _log(msg: str) -> None:
        app.logs.append({"msg": msg})

    @app.get("/ui")
    def ui_index():
        return render_template("index.html")

    # Redirect root to the UI for convenience (keeps existing blueprint routes intact)
    @app.before_request
    def _root_redirect():
        if request.path == "/":
            return redirect('/ui')

    @app.post("/tamper")
    def ui_tamper():
        payload = request.get_json(silent=True) or {}
        idx = payload.get("index")
        new_tx = payload.get("transaction")
        if idx is None or new_tx is None:
            return jsonify({"error": "index and transaction required"}), 400
        chain = app.blockchain
        # find block by index
        try:
            # Block indexes are integers (genesis = 0)
            block = next(b for b in chain.chain if b.index == int(idx))
        except StopIteration:
            return jsonify({"error": "block index not found"}), 400
        # convert transaction dict to Transaction if possible; otherwise wrap dict
        tx_obj = None
        if isinstance(new_tx, dict):
            try:
                tx_obj = Transaction.from_dict(new_tx)
            except Exception:
                # Wrap the raw dict so Block.to_dict() still works
                class _RawTx:
                    def __init__(self, data):
                        self._data = data

                    def to_dict(self):
                        return self._data

                tx_obj = _RawTx(new_tx)
        else:
            return jsonify({"error": "transaction must be an object"}), 400

        # replace transactions with the provided one (may be invalid; that's the demo point)
        block.transactions = [tx_obj]
        _log(f"Tampered block {idx} with {new_tx}")
        return jsonify({"message": f"Block {idx} tampered"}), 200

    @app.post("/reset")
    def ui_reset():
        app.blockchain = Blockchain()
        app.logs.clear()
        _log("Demo reset to genesis state")
        return jsonify({"message": "Demo reset"}), 200

    @app.get("/logs")
    def ui_logs():
        return jsonify({"logs": app.logs}), 200

    app.register_blueprint(bp)
    return app
