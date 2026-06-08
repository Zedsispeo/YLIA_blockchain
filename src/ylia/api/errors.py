"""Erreurs renvoyées en JSON cohérent : {"error": "..."} avec le bon code HTTP.

ChainError → 400, ApiError → code choisi, HTTPException (404/405…) → JSON,
le reste → 500 sans fuite de trace.
"""

from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from ..blockchain import ChainError


class ApiError(Exception):
    """Erreur de la couche HTTP (entrée malformée, etc.)."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ChainError)
    def _handle_chain_error(exc: ChainError):
        return jsonify({"error": str(exc)}), 400

    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        return jsonify({"error": exc.message}), exc.status

    @app.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException):
        return jsonify({"error": exc.description, "status": exc.code}), exc.code or 500

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):  # pragma: no cover - filet de sécurité
        app.logger.exception("Erreur non gérée")
        return jsonify({"error": "erreur interne du serveur"}), 500
