"""Constantes du réseau, partagées par tous les nœuds (→ même genesis)."""

import os

# Autorité racine : seule autorité au genesis, gère les agréments.
# Clé déterministe pour la démo (tous les nœuds partagent la même racine sans
# échange de secret). En prod : clé aléatoire conservée hors ligne.
ROOT_PRIVATE_KEY = os.environ.get("YLIA_ROOT_KEY", "00" * 31 + "01")  # = 1, clé SECP256k1 valide

# Genesis : horodatage figé (pas time.time()) pour un bloc identique partout.
GENESIS_TIMESTAMP = 0.0
GENESIS_PREVIOUS_HASH = "0" * 64

DEFAULT_PORT = int(os.environ.get("YLIA_PORT", "5000"))
PEER_TIMEOUT = float(os.environ.get("YLIA_PEER_TIMEOUT", "3.0"))

# Identité du nœud : par défaut la racine (pour que /mine marche d'emblée).
# Définir YLIA_NODE_KEY pour simuler un établissement distinct.
NODE_PRIVATE_KEY = os.environ.get("YLIA_NODE_KEY", ROOT_PRIVATE_KEY)

# Persistance : fichier de stockage de la chaîne (extension .ylia, JSON interne).
# Un fichier par nœud (par port) pour que plusieurs nœuds locaux ne s'écrasent pas.
DATA_DIR = os.environ.get("YLIA_DATA_DIR", "data")


def chain_file_for(port: int) -> str:
    """Chemin du fichier .ylia du nœud. YLIA_CHAIN_FILE force un chemin explicite."""
    return os.environ.get("YLIA_CHAIN_FILE") or os.path.join(DATA_DIR, f"ylia-{port}.ylia")
