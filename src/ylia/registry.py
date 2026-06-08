"""Liste blanche des autorités PoA.

État dérivé de la chaîne (rejeu des register/revoke depuis le genesis), pas une
structure stockée — esprit "smart contract", auditable et reproductible.
Politique : seule la racine peut agréer/révoquer.
"""

from __future__ import annotations

from .config import ROOT_PRIVATE_KEY
from . import crypto

ROOT_ADDRESS = crypto.address_from_private_key(ROOT_PRIVATE_KEY)
ROOT_PUBLIC_KEY = crypto.public_key_from_private(ROOT_PRIVATE_KEY)


def authorities_from_transactions(transactions) -> set[str]:
    """Autorités après rejeu des transactions, en partant de la racine.
    Seuls les register/revoke émis par la racine comptent."""
    authorities = {ROOT_ADDRESS}
    for tx in transactions:
        if tx.sender != ROOT_ADDRESS:
            continue
        if tx.type == "register":
            authorities.add(tx.recipient)
        elif tx.type == "revoke":
            authorities.discard(tx.recipient)
    authorities.add(ROOT_ADDRESS)  # la racine reste toujours autorité
    return authorities


def authorities_in_chain(chain) -> set[str]:
    all_txs = [tx for block in chain for tx in block.transactions]
    return authorities_from_transactions(all_txs)
