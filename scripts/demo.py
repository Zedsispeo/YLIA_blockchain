#!/usr/bin/env python3
"""Démonstration de bout en bout de la blockchain YLIA.

Lance trois nœuds, puis déroule les cinq points de démonstration du sujet,
dans l'ordre du sujet :

1. Création de blocs et vérification du chaînage.
2. Ajout de transactions puis minage d'un bloc les contenant.
3. Détection d'une chaîne falsifiée (bloc modifié → chaîne invalide).
4. Résolution de conflits : deux nœuds convergent vers la même chaîne.
5. Validité du consensus : transaction ET bloc d'un non-agréé sont rejetés.

Usage :
    python scripts/demo.py
"""

import os
import subprocess
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ylia import crypto  # noqa: E402
from ylia.block import Block  # noqa: E402
from ylia.blockchain import Blockchain  # noqa: E402
from ylia.config import ROOT_PRIVATE_KEY  # noqa: E402
from ylia.transaction import Transaction  # noqa: E402

A = "http://127.0.0.1:5000"
B = "http://127.0.0.1:5001"
C = "http://127.0.0.1:5002"  # nœud à l'identité NON agréée


def title(n, text):
    print(f"\n{'='*70}\n{n}. {text}\n{'='*70}")


def wait_up(url, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(f"{url}/health", timeout=1)
            return True
        except requests.RequestException:
            time.sleep(0.3)
    return False


def signed(tx_type, private_key, recipient, amount=0):
    """Crée et signe une transaction (utilitaire de démo)."""
    pub = crypto.public_key_from_private(private_key)
    tx = Transaction(
        tx_type=tx_type,
        sender=crypto.address_from_public_key(pub),
        recipient=recipient,
        amount=amount,
        public_key=pub,
        timestamp=time.time(),
    )
    return tx.sign(private_key)


def main():
    env = dict(os.environ)
    outsider_key, _ = crypto.generate_keypair()  # identité jamais agréée (nœud C)
    procs = [
        subprocess.Popen([sys.executable, "main.py", "--port", "5000"], cwd=ROOT, env=env),
        subprocess.Popen([sys.executable, "main.py", "--port", "5001"], cwd=ROOT, env=env),
        subprocess.Popen(
            [sys.executable, "main.py", "--port", "5002", "--node-key", outsider_key],
            cwd=ROOT, env=env,
        ),
    ]
    try:
        print("Démarrage des trois nœuds…")
        assert wait_up(A) and wait_up(B) and wait_up(C), "les nœuds n'ont pas démarré"
        time.sleep(0.5)

        # ---------------------------------------------------------------- #
        title(1, "Chaînage : minage de blocs sur le nœud A")
        for _ in range(2):
            r = requests.get(f"{A}/mine").json()
            print(f"   bloc #{r['block']['index']} miné — hash {r['block']['hash'][:16]}…")
        chain = requests.get(f"{A}/chain").json()["chain"]
        for i in range(1, len(chain)):
            assert chain[i]["previous_hash"] == chain[i - 1]["hash"]
        print("   ✓ chaînage cohérent (previous_hash de chaque bloc = hash du précédent)")

        # ---------------------------------------------------------------- #
        title(2, "Transactions : agrément d'un établissement, crédit, débit")
        etab = requests.get(f"{A}/wallet/new").json()
        client = requests.get(f"{A}/wallet/new").json()["address"]
        requests.post(f"{A}/authorities/register", json={"address": etab["address"]})
        requests.get(f"{A}/mine")
        print(f"   établissement agréé : {etab['address'][:24]}…")

        requests.post(f"{A}/transactions/new", json={
            "type": "credit", "recipient": client, "amount": 80, "private_key": etab["private_key"]})
        requests.get(f"{A}/mine")
        requests.post(f"{A}/transactions/new", json={
            "type": "debit", "recipient": client, "amount": 30, "private_key": etab["private_key"]})
        requests.get(f"{A}/mine")
        bal = requests.get(f"{A}/balance/{client}").json()["balance"]
        print(f"   client : +80 puis -30 → solde = {bal} points")
        assert bal == 50, bal
        print("   ✓ transactions intégrées et soldes corrects")

        # ---------------------------------------------------------------- #
        title(3, "Falsification : un bloc modifié rend la chaîne invalide")
        # Démonstration in-process : aucune API n'accepte une chaîne forgée,
        # on construit donc une blockchain locale, on la falsifie et on montre
        # que la validation la rejette.
        local = Blockchain()
        local.add_transaction(signed("credit", ROOT_PRIVATE_KEY, "YLIAcli", 100))
        local.mine(ROOT_PRIVATE_KEY)
        ok_before, _ = local.validate_chain()
        local.chain[-1].transactions[0].amount = 999_999  # falsification
        ok_after, reason = local.validate_chain()
        print(f"   avant falsification : valide = {ok_before}")
        print(f"   après falsification : valide = {ok_after} ({reason})")
        assert ok_before is True and ok_after is False
        print("   ✓ la falsification d'un montant est détectée → chaîne invalide")

        # ---------------------------------------------------------------- #
        title(4, "Résolution de conflits : B adopte la chaîne plus longue de A")
        len_a = requests.get(f"{A}/chain").json()["length"]
        len_b = requests.get(f"{B}/chain").json()["length"]
        print(f"   avant : A = {len_a} blocs, B = {len_b} blocs")
        requests.post(f"{B}/nodes/register", json={"nodes": [A]})
        r = requests.get(f"{B}/nodes/resolve").json()
        len_b2 = requests.get(f"{B}/chain").json()["length"]
        print(f"   après : B = {len_b2} blocs — {r['message']}")
        assert len_b2 == len_a
        ha = [b["hash"] for b in requests.get(f"{A}/chain").json()["chain"]]
        hb = [b["hash"] for b in requests.get(f"{B}/chain").json()["chain"]]
        assert ha == hb
        print("   ✓ les deux nœuds ont convergé vers la même chaîne")

        # ---------------------------------------------------------------- #
        title(5, "Validité du consensus PoA : un non-agréé est rejeté")
        # (a) transaction d'un émetteur non agréé → 400
        outsider = requests.get(f"{A}/wallet/new").json()
        r_tx = requests.post(f"{A}/transactions/new", json={
            "type": "credit", "recipient": client, "amount": 1000, "private_key": outsider["private_key"]})
        print(f"   (a) transaction d'un non-agréé → HTTP {r_tx.status_code} : {r_tx.json().get('error','')[:55]}")
        assert r_tx.status_code == 400

        # (b) le nœud C (identité non agréée) tente de miner → 403
        r_mine = requests.get(f"{C}/mine")
        print(f"   (b) minage par le nœud C non agréé → HTTP {r_mine.status_code} : {r_mine.json().get('error','')[:55]}")
        assert r_mine.status_code == 403

        # (c) bloc signé par un validateur non agréé → chaîne invalide
        local2 = Blockchain()
        opub = crypto.public_key_from_private(outsider["private_key"])
        oaddr = crypto.address_from_public_key(opub)
        forged = Block(index=1, timestamp=time.time(), transactions=[],
                       previous_hash=local2.last_block.hash, validator=oaddr, validator_pubkey=opub)
        forged.sign(outsider["private_key"])
        local2.chain.append(forged)
        ok_c, reason_c = local2.validate_chain()
        print(f"   (c) bloc d'un validateur non agréé → valide = {ok_c} ({reason_c})")
        assert ok_c is False
        print("   ✓ transaction ET bloc d'un non-agréé sont rejetés")

        print(f"\n{'='*70}\n✅ Les 5 points de démonstration du sujet ont été prouvés.\n{'='*70}")
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
