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

from ylia import crypto, identity  # noqa: E402
from ylia.api import create_app  # noqa: E402
from ylia.blockchain import Blockchain  # noqa: E402
from ylia.config import (  # noqa: E402
    DEFAULT_PORT,
    NODE_PRIVATE_KEY,
    chain_file_for,
    key_file_for,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nœud YLIA (blockchain de points de fidélité, PoA)")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help="port d'écoute")
    parser.add_argument("--host", default="127.0.0.1", help="adresse d'écoute")
    parser.add_argument(
        "--node-key",
        default=None,
        help="clé privée (hex) de l'identité du nœud. Par défaut : l'identité "
        "persistée du nœud (fichier .key), générée au 1er démarrage. "
        "Équivalent : variable d'environnement YLIA_NODE_KEY.",
    )
    parser.add_argument(
        "--new-key",
        action="store_true",
        help="force une NOUVELLE identité d'établissement (rotation) et la persiste "
        "(devra être agréée par la racine avant de pouvoir miner)",
    )
    parser.add_argument(
        "--chain-file",
        default=None,
        help="fichier .ylia de persistance de la chaîne "
        "(par défaut : data/ylia-<port>.ylia ; YLIA_CHAIN_FILE pour forcer)",
    )
    parser.add_argument(
        "--key-file",
        default=None,
        help="fichier .key de persistance de l'identité du nœud "
        "(par défaut : data/ylia-<port>.key ; YLIA_KEY_FILE pour forcer)",
    )
    args = parser.parse_args()

    # Identité du nœud : clé explicite (CLI/env) > fichier .key existant >
    # nouvelle clé générée et persistée. Chaque conteneur retrouve ainsi la même
    # identité d'un redémarrage à l'autre, via le fichier .key de son volume.
    key_file = args.key_file or key_file_for(args.port)
    node_key = identity.resolve_node_key(
        key_file,
        explicit_key=args.node_key or NODE_PRIVATE_KEY,
        force_new=args.new_key,
    )

    chain_file = args.chain_file or chain_file_for(args.port)
    blockchain = Blockchain(storage_path=chain_file)
    app = create_app(blockchain=blockchain, node_private_key=node_key)

    address = crypto.address_from_private_key(node_key)
    is_authority = address in blockchain.current_authorities()
    print("=" * 64)
    print(f"  YLIA — nœud démarré sur http://{args.host}:{args.port}")
    print(f"  Identité du nœud : {address}")
    print(f"  Autorité agréée  : {'oui' if is_authority else 'non (à faire agréer)'}")
    print(f"  Racine du réseau : {blockchain.root_address}")
    print(f"  Identité (.key)  : {key_file}")
    print(f"  Stockage (.ylia) : {chain_file}  (blocs : {len(blockchain.chain)})")
    print(f"  Index de l'API   : http://{args.host}:{args.port}/  (catalogue des routes)")
    print("=" * 64)

    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
