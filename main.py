"""Point d'entrée d'un nœud YLIA.

Usage :
    python main.py                      # nœud sur le port 5000 (identité = racine)
    python main.py --port 5001          # un second nœud
    python main.py --port 5002 --new-key  # nœud avec une identité d'établissement dédiée

Variables d'environnement équivalentes : YLIA_PORT, YLIA_NODE_KEY, YLIA_ROOT_KEY.
"""

import argparse
import sys

sys.path.insert(0, "src")

from ylia import crypto  # noqa: E402
from ylia.api import create_app  # noqa: E402
from ylia.blockchain import Blockchain  # noqa: E402
from ylia.config import DEFAULT_PORT, NODE_PRIVATE_KEY  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Nœud YLIA (blockchain de points de fidélité, PoA)")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help="port d'écoute")
    parser.add_argument("--host", default="127.0.0.1", help="adresse d'écoute")
    parser.add_argument(
        "--node-key",
        default=NODE_PRIVATE_KEY,
        help="clé privée (hex) de l'identité du nœud — par défaut : l'autorité racine",
    )
    parser.add_argument(
        "--new-key",
        action="store_true",
        help="génère une identité d'établissement aléatoire pour ce nœud "
        "(devra être agréée par la racine avant de pouvoir miner)",
    )
    args = parser.parse_args()

    node_key = args.node_key
    if args.new_key:
        node_key, _ = crypto.generate_keypair()

    blockchain = Blockchain()
    app = create_app(blockchain=blockchain, node_private_key=node_key)

    address = crypto.address_from_private_key(node_key)
    is_authority = address in blockchain.current_authorities()
    print("=" * 64)
    print(f"  YLIA — nœud démarré sur http://{args.host}:{args.port}")
    print(f"  Identité du nœud : {address}")
    print(f"  Autorité agréée  : {'oui' if is_authority else 'non (à faire agréer)'}")
    print(f"  Racine du réseau : {blockchain.root_address}")
    print(f"  Index de l'API   : http://{args.host}:{args.port}/  (catalogue des routes)")
    print("=" * 64)

    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
