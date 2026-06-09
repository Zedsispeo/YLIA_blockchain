# YLIA — Blockchain de points de fidélité

YLIA est une **blockchain de points de fidélité** fonctionnant en **Proof of Authority (PoA)**.
Seuls les **établissements agréés** peuvent émettre des transactions sur la chaîne : ils
créditent (attribution de points) et débitent (consommation de points) les comptes des clients.
Les clients, eux, ne font que **gagner** et **dépenser** leurs points.

L'objectif est de fournir un **registre commun, infalsifiable et auditable** des points de
fidélité, partagé entre plusieurs établissements, sans qu'aucun d'eux ne puisse falsifier le
solde d'un client ou s'attribuer des points qu'il n'a pas le droit d'émettre.

---

## 🚀 Démarrage rapide

```bash
# 1. Environnement virtuel + dépendances
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt

# 2. Lancer un nœud (API REST)
python main.py --port 5000
# → l'index auto-documenté des routes : curl http://127.0.0.1:5000/

# 3. (Optionnel) lancer la démonstration complète à 3 nœuds
python scripts/demo.py

# 4. Lancer les tests
pytest -q
```

> Le projet est une **API REST en Python pur** : aucune base de données, aucune
> compilation. La cryptographie (ECDSA / SECP256k1) est réelle, via `ecdsa`. La
> chaîne est **persistée sur disque** dans un fichier `.ylia` (un par nœud), donc
> un nœud relancé **repart de son dernier état** et non du genesis.
> *(Ce dépôt couvre le **backend / l'API** ; un client web le consomme séparément.)*

---

## Sommaire

- [Démarrage rapide](#-démarrage-rapide)
- [Principe général](#principe-général)
- [Concepts clés](#concepts-clés)
- [Le consensus Proof of Authority](#le-consensus-proof-of-authority)
- [Modèle des points](#modèle-des-points)
- [Acteurs et rôles](#acteurs-et-rôles)
- [Gouvernance des agréments](#gouvernance-des-agréments)
- [Cycle de vie d'une transaction](#cycle-de-vie-dune-transaction)
- [Architecture on-chain / off-chain](#architecture-on-chain--off-chain)
- [Garanties de sécurité](#garanties-de-sécurité)
- [Glossaire](#glossaire)
- [Structure du projet](#structure-du-projet)
- [API REST](#api-rest)
- [Démonstration des exigences du sujet](#démonstration-des-exigences-du-sujet)
- [Choix techniques](#choix-techniques)
- [Difficultés rencontrées](#difficultés-rencontrées)
- [Limitations connues](#limitations-connues)

---

## Principe général

Dans un programme de fidélité classique, chaque enseigne gère ses points dans sa propre base
de données privée. Le client doit faire confiance à l'enseigne sur son solde, et les points ne
circulent pas d'une enseigne à l'autre.

YLIA remplace ces bases isolées par **un seul registre partagé** : la blockchain. Tous les
établissements agréés lisent et écrivent dans ce même registre. Chaque opération (attribution
ou consommation de points) est une **transaction signée**, inscrite dans un bloc, et vérifiable
par tous.

La particularité de YLIA est qu'il ne s'agit **pas** d'une blockchain publique ouverte à tous :
c'est un réseau **à permission**. On ne peut pas devenir émetteur sans avoir été explicitement
agréé. C'est le rôle du **Proof of Authority**.

---

## Concepts clés

| Concept | Description |
|---|---|
| **Point** | Unité de fidélité. Monnaie **universelle** partagée par tout le réseau. |
| **Client** | Bénéficiaire des points. Possède un solde et un compte (adresse) sur la chaîne. |
| **Établissement agréé** | Acteur autorisé à émettre des transactions (créditer/débiter les clients). C'est aussi une **autorité** du consensus. |
| **Autorité (validateur)** | Nœud habilité à produire et valider les blocs. Dans YLIA, les établissements agréés sont les autorités. |
| **Transaction** | Opération signée : attribution (`+points`) ou consommation (`-points`) sur le compte d'un client. |
| **Bloc** | Lot de transactions validé et chaîné au précédent. |
| **Registre d'agréments** | Smart contract qui tient la liste blanche des établissements autorisés. |

---

## Le consensus Proof of Authority

Le **Proof of Authority (PoA)** est un mécanisme de consensus où la confiance ne repose pas sur
la puissance de calcul (comme le Proof of Work / minage) ni sur la mise de jetons (comme le
Proof of Stake), mais sur **l'identité connue et approuvée** des validateurs.

Dans YLIA :

- **Seuls les établissements agréés sont des autorités.** Ce sont eux, et eux seuls, qui
  produisent les blocs et émettent les transactions.
- Chaque autorité possède une **identité on-chain** (une paire de clés cryptographiques) qui
  a été **explicitement enregistrée** dans le registre d'agréments.
- Un acteur non agréé ne peut **ni émettre une transaction valide, ni produire un bloc** : ses
  messages sont rejetés par le réseau car son adresse n'est pas dans la liste blanche.

### Pourquoi le PoA pour ce projet ?

- **Pas de minage** : inutile de gaspiller de l'énergie, les validateurs sont déjà identifiés
  et de confiance.
- **Transactions rapides et quasi gratuites** : adapté à un usage commercial fréquent
  (passage en caisse, attribution de points en temps réel).
- **Responsabilité** : chaque bloc et chaque transaction est signé par un acteur **nommément
  identifié**. En cas d'abus, on sait précisément qui en est l'auteur.
- **Contrôle d'accès natif** : il est impossible de créer ou détruire des points sans être un
  établissement agréé.

---

## Modèle des points

YLIA utilise un **point universel partagé** :

- Il existe **une seule monnaie de points** commune à l'ensemble du réseau.
- Un client qui gagne des points chez l'établissement **A** peut les dépenser chez
  l'établissement **B**, dès lors que B est lui aussi agréé.
- Le solde d'un client est **global** : il n'est pas cloisonné par établissement.

### Création et destruction des points

- **Attribution (crédit)** : un établissement agréé attribue des points à un client (ex. après
  un achat). C'est l'équivalent d'une *création* (mint) de points sur le compte du client.
- **Consommation (débit)** : un établissement agréé débite des points du compte d'un client
  lorsqu'il les échange contre une récompense. C'est l'équivalent d'une *destruction* (burn).

### Ce que les clients **peuvent** faire

- ✅ **Gagner** des points (crédités par un établissement agréé).
- ✅ **Dépenser** des points (débités par un établissement agréé).

### Ce que les clients **ne peuvent pas** faire

- ❌ Émettre eux-mêmes des transactions (seuls les établissements le peuvent).
- ❌ Se transférer des points entre clients (pas de transfert peer-to-peer).
- ❌ Créer des points de leur propre initiative.

> Toute variation du solde d'un client résulte donc **obligatoirement** d'une transaction
> signée par un établissement agréé.

---

## Acteurs et rôles

| Acteur | Peut émettre une transaction ? | Peut valider un bloc ? | Détient un solde de points ? |
|---|:---:|:---:|:---:|
| **Établissement agréé** | ✅ Oui | ✅ Oui (autorité) | — |
| **Client** | ❌ Non | ❌ Non | ✅ Oui |
| **Autorité racine / gouvernance** | ✅ (gestion des agréments) | ✅ | — |
| **Acteur non agréé** | ❌ Non | ❌ Non | — |

---

## Gouvernance des agréments

La liste des établissements autorisés est gérée **on-chain** par un **smart contract de
registre** (liste blanche).

Ce contrat est la source de vérité du réseau : avant d'accepter une transaction ou un bloc, les
nœuds vérifient que son émetteur figure bien dans le registre **avec un statut actif**.

Le registre prend en charge :

- **L'ajout** d'un établissement (octroi de l'agrément) → son adresse devient émettrice/validatrice valide.
- **La révocation** d'un établissement (retrait de l'agrément) → ses futures transactions et blocs
  sont rejetés par le réseau.
- **La consultation** de l'état d'un établissement (agréé / révoqué) par n'importe quel nœud.

Les opérations sur le registre sont elles-mêmes des transactions on-chain : l'historique des
agréments et des révocations est donc **traçable et auditable** comme le reste de la chaîne.

> **À préciser ultérieurement :** la politique d'administration du registre (autorité racine
> unique, vote de consortium, multi-signatures…). Le présent document décrit le *mécanisme* de
> liste blanche, indépendamment de la politique retenue pour la modifier.

---

## Cycle de vie d'une transaction

Exemple : un client gagne 50 points lors d'un achat.

```
1. L'établissement agréé prépare une transaction :
   { type: "credit", client: <adresse_client>, montant: 50, etablissement: <adresse_etab> }

2. L'établissement SIGNE la transaction avec sa clé privée.

3. La transaction est diffusée sur le réseau.

4. Les autorités VÉRIFIENT :
     - la signature est valide ;
     - l'émetteur est bien dans le registre d'agréments (statut actif) ;
     - (pour un débit) le client dispose d'un solde suffisant.

5. La transaction valide est intégrée dans un BLOC par une autorité.

6. Le bloc est chaîné au registre. Le solde du client est mis à jour.
```

Une transaction invalide (signature incorrecte, émetteur non agréé, solde insuffisant) est
**rejetée** et n'est jamais inscrite dans la chaîne.

---

## Architecture on-chain / off-chain

YLIA répartit l'information en deux couches, selon une règle simple :

> **Les autorisations et les mouvements de points vivent sur la blockchain.
> Les identités nominatives et les métadonnées vivent dans une base de données off-chain.**

### Couche on-chain (la blockchain)

- Les **soldes** de points (rattachés à des **adresses pseudonymes**).
- Les **transactions** (attributions / consommations de points).
- Le **registre d'agréments** des établissements.
- Les **blocs** et le chaînage.

### Couche off-chain (base de données)

- Le **lien entre une identité réelle et son adresse pseudonyme** on-chain.
- Les **métadonnées** non essentielles au consensus.

Cette séparation permet de garder la chaîne **légère, pseudonyme et durable**, tout en gérant
les données sensibles ou volumineuses dans un système classique mieux adapté (et plus facile à
mettre en conformité, par ex. droit à l'effacement).

---

## Garanties de sécurité

- **Émission contrôlée** — Aucun point ne peut être créé ou détruit en dehors d'une transaction
  signée par un établissement agréé.
- **Non-falsifiabilité** — Une fois un bloc chaîné, modifier une transaction passée invaliderait
  toute la chaîne suivante.
- **Imputabilité** — Chaque transaction et chaque bloc est signé par une autorité identifiée :
  toute opération est attribuable à son auteur.
- **Révocabilité** — Un établissement qui perd son agrément est immédiatement écarté du réseau
  via le registre, sans interrompre la chaîne.
- **Transparence auditable** — L'intégralité des mouvements de points et des agréments est
  consultable et vérifiable par les participants.

---

## Glossaire

- **PoA (Proof of Authority)** — Consensus fondé sur l'identité approuvée des validateurs plutôt
  que sur le calcul ou la mise.
- **Autorité / Validateur** — Nœud habilité à produire et valider les blocs. Ici : un
  établissement agréé.
- **Liste blanche** — Ensemble des adresses autorisées, tenu par le registre d'agréments.
- **Crédit / Débit** — Attribution / consommation de points sur le compte d'un client.
- **On-chain / Off-chain** — Données stockées sur la blockchain / dans une base externe.
- **Adresse pseudonyme** — Clé publique identifiant un compte sur la chaîne, sans révéler
  l'identité réelle.

---

## Structure du projet

```
YLIA_blockchain/
├── main.py                 # point d'entrée d'un nœud (CLI : --port, --node-key, --new-key, --chain-file)
├── requirements.txt        # dépendances (Flask, ecdsa, requests, pytest)
├── README.md
├── src/ylia/
│   ├── crypto.py           # cryptographie réelle : clés, signatures ECDSA, adresses
│   ├── transaction.py      # transaction signée (credit / debit / register / revoke)
│   ├── block.py            # bloc en 3 lanes (toplane/midlane/botlane) + hash SHA-256 déterministe
│   ├── registry.py         # registre d'agréments (liste blanche des autorités PoA)
│   ├── blockchain.py       # chaîne, minage, validation, soldes, résolution de conflits, persistance
│   ├── storage.py          # sauvegarde/chargement de la chaîne dans un fichier .ylia (écriture atomique)
│   ├── node.py             # communication réseau entre nœuds (pairs, diffusion)
│   ├── config.py           # racine, genesis, ports, chemin du fichier .ylia
│   └── api/                # couche HTTP (séparée du cœur, donc testable)
│       ├── __init__.py     #   factory create_app()
│       ├── routes.py       #   Blueprint : toutes les routes
│       └── errors.py       #   gestion d'erreurs JSON cohérente
├── src/model/              # schéma du bloc : toplane (en-tête), midlane (signature), botlane (transactions)
├── scripts/
│   ├── demo.py             # démonstration automatisée à 3 nœuds (les 5 points du sujet)
│   └── run_two_nodes.sh    # lance 2 nœuds pour des essais manuels
└── tests/                  # 58 tests pytest (cœur, consensus, réorg, réseau, API)
```

La **séparation cœur / transport** est volontaire : le domaine (`blockchain.py`,
`crypto.py`, …) ne dépend pas de Flask et se teste sans serveur ; la couche `api/`
ne fait que traduire HTTP ↔ domaine. La factory `create_app(blockchain=…)` permet
à chaque test de partir d'une blockchain neuve.

### Structure d'un bloc (exigence du sujet)

Le bloc suit le schéma de `src/model/`, organisé en **trois « lanes »** :

- **`toplane`** (en-tête) : `version`, `index`, `timestamp`, `previous_hash`, `merkle_root`, `txcount`, `author`.
- **`midlane`** (couche de signature) : `validator_pubkey`, `signature`, `hash`.
- **`botlane`** (corps) : `transactions`.

| Champ | Lane | Rôle |
|---|---|---|
| `version` | top | version du format de bloc |
| `index` | top | position dans la chaîne (0 = genesis) |
| `timestamp` | top | horodatage de production |
| `previous_hash` | top | hash du bloc précédent (chaînage) |
| `merkle_root` | top | racine de Merkle des transactions (l'en-tête s'engage sur le corps) |
| `txcount` | top | nombre de transactions du bloc |
| `author` (= `validator`) | top | adresse de l'autorité qui a produit le bloc |
| `validator_pubkey` | mid | clé publique du validateur (liée à `author`) |
| `signature` | mid | signature ECDSA du `hash` par le validateur |
| `hash` | mid | **SHA-256 déterministe** de l'en-tête (`toplane`, JSON trié) |
| `transactions` | bot | liste des transactions incluses |

> Le `hash` porte sur le `toplane`, qui s'engage sur les transactions via `merkle_root` :
> toute modification d'une transaction change la racine, donc le hash → falsification détectée.
> `author`, `validator_pubkey` et `signature` forment le **champ de consensus PoA**.

---

## API REST

### Endpoints exigés par le sujet

| Méthode | Route | Description |
|---|---|---|
| `GET`  | `/chain` | la chaîne complète + sa longueur |
| `POST` | `/transactions/new` | soumettre une transaction signée |
| `GET`  | `/mine` | miner un bloc contenant les transactions en attente |

### Réseau multi-nœuds

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/nodes/register` | enregistrer des pairs (`{"nodes": ["http://…:5001"]}`) |
| `GET`  | `/nodes` | lister les pairs |
| `GET`  | `/nodes/resolve` | **résolution de conflits** (plus longue chaîne valide) |

### Spécifique YLIA (points de fidélité / PoA)

| Méthode | Route | Description |
|---|---|---|
| `GET`  | `/authorities` | liste blanche des autorités agréées |
| `POST` | `/authorities/register` | agréer un établissement (`{"address": "YLIA…"}`) |
| `POST` | `/authorities/revoke` | révoquer un établissement |
| `GET`  | `/balance/<address>` | solde d'un compte |
| `GET`  | `/balances` | tous les soldes |
| `GET`    | `/pending` | transactions en attente |
| `DELETE` | `/transactions/pending` | vider le mempool (exploitation) |
| `GET`    | `/validate` | la chaîne est-elle valide ? (+ raison si non) |
| `GET`    | `/wallet/new` | générer une paire de clés |
| `GET`    | `/node` | informations sur le nœud courant |

### Utilitaires

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | index auto-documenté (catalogue des routes + état du nœud) |
| `GET` | `/health` | sonde de vivacité |

Toutes les erreurs sont renvoyées en JSON : `{"error": "<message>"}` avec le bon
code HTTP (400 validation, 403 nœud non agréé au minage, 404, 405, 500).

### Format d'une transaction

Les champs du sujet (`sender`, `recipient`, `amount`) sont présents et complétés
par le modèle métier YLIA :

```jsonc
{
  "type": "credit",            // credit | debit | register | revoke
  "sender": "YLIA…",           // adresse de l'émetteur (autorité signataire)
  "recipient": "YLIA…",        // client (credit/debit) ou établissement (register/revoke)
  "amount": 50,                 // points (0 pour register/revoke)
  "public_key": "…",           // clé publique de l'émetteur
  "timestamp": 1718000000.0,
  "nonce": "facture-42",        // optionnel : identifiant d'opération (idempotence)
  "signature": "…"             // signature ECDSA de tout ce qui précède
}
```

Pour faciliter les essais, `POST /transactions/new` accepte aussi `{"private_key": "…"}`
(signature côté serveur) ou `{"use_root": true}` (signé par la racine). En production,
la signature se ferait **côté client** : le serveur ne verrait jamais de clé privée.
La **vérification** des signatures reste rigoureuse dans tous les cas — c'est elle qui
fait respecter le PoA.

Le champ **`nonce`** est facultatif : s'il est fourni, deux transactions du même
émetteur ne peuvent pas partager le même nonce (anti-rejeu / idempotence). Utile
pour qu'une re-soumission accidentelle (ou une double diffusion) ne crédite/débite
pas deux fois.

#### Exemples cURL

```bash
# Créditer un client (signé par la racine, pour la démo) puis miner
curl -X POST localhost:5000/transactions/new \
     -H 'Content-Type: application/json' \
     -d '{"type":"credit","recipient":"YLIAalice","amount":50,"use_root":true}'
curl localhost:5000/mine
curl localhost:5000/balance/YLIAalice      # -> 50

# Agréer un établissement
curl -X POST localhost:5000/authorities/register \
     -H 'Content-Type: application/json' -d '{"address":"YLIAetab1"}'
```

---

## Démonstration des exigences du sujet

Le script `python scripts/demo.py` lance trois nœuds et **prouve les cinq points
de bout en bout** (y compris la détection de falsification et le rejet d'un nœud
non agréé). Chaque point est aussi couvert par des tests :

| Exigence du sujet | Démo | Tests |
|---|---|---|
| Création d'un bloc + chaînage cohérent | §1 | `test_block_and_chaining.py` |
| Ajout de transactions puis minage | §2 | `test_transactions_and_mining.py` |
| Détection d'une chaîne falsifiée | §3 | `test_falsification.py` |
| Résolution de conflits (convergence) | §4 | `test_conflict_resolution.py` |
| Validité du consensus (tx ET bloc non agréé rejetés) | §5 | `test_consensus_poa.py`, `test_network.py` |

Essais manuels : `scripts/run_two_nodes.sh` lance deux nœuds (ports 5000/5001) ;
on peut alors miner sur l'un (`curl localhost:5000/mine`), enregistrer l'autre
comme pair, puis déclencher `curl localhost:5001/nodes/resolve`.

---

## Choix techniques

- **Consensus : Proof of Authority** — justifié en détail plus haut. En une phrase :
  un registre de fidélité est un réseau *à permission* (seuls des établissements
  agréés écrivent), donc le PoA — fondé sur l'identité approuvée des validateurs —
  est le choix naturel : pas de minage coûteux, transactions instantanées, et chaque
  bloc est imputable à une autorité nommée.
- **Cryptographie réelle (ECDSA / SECP256k1)** — chaque transaction et chaque bloc est
  signé ; la vérification lie la clé publique à l'adresse de l'émetteur, ce qui empêche
  l'usurpation. Signatures déterministes (RFC 6979) pour un genesis reproductible.
- **Pas de base de données** — l'état (soldes, autorités) n'est jamais stocké : il est
  intégralement *dérivé* en rejouant les transactions de la chaîne, à la manière d'un
  smart contract. Seule la **chaîne** est persistée.
- **Persistance fichier (`.ylia`)** — la chaîne est sauvegardée dans un fichier `.ylia`
  (JSON, un fichier par nœud : `data/ylia-<port>.ylia`) après chaque bloc miné, reçu ou
  adopté lors d'une résolution de conflits. L'écriture est **atomique** (fichier temporaire
  + `fsync` + `os.replace`) : un crash en cours d'écriture ne corrompt jamais le fichier.
  Au démarrage, la chaîne stockée n'est rechargée que si elle est **intégralement valide**
  (genesis authentique, chaînage, hash, signatures, agréments, soldes) ; sinon le nœud
  repart du genesis.
- **Résolution de conflits** — règle de la *plus longue chaîne valide* : un nœud n'adopte
  une chaîne pair que si elle est plus longue **et** entièrement valide (chaînage, hash,
  signatures, agréments, soldes). Une chaîne plus longue mais falsifiée est rejetée.

---

## Difficultés rencontrées

- **Genesis identique sur tous les nœuds.** La résolution de conflits compare des chaînes :
  il faut donc que le bloc genesis soit *bit-à-bit* identique partout. Résolu en figeant
  l'horodatage du genesis et en utilisant des signatures déterministes (RFC 6979) et une
  racine dérivée d'une graine partagée.
- **Hash déterministe.** Un `dict` Python n'a pas d'ordre de sérialisation garanti d'une
  exécution à l'autre. Le hash est calculé sur du JSON **trié** (`sort_keys=True`,
  séparateurs compacts) pour être strictement reproductible.
- **Falsification « réparée ».** Recalculer le hash d'un bloc modifié ne suffit pas à
  tromper la chaîne : la signature de la transaction ne correspond plus à son contenu et
  le `previous_hash` du bloc suivant est rompu. La validation vérifie les trois (hash,
  signatures, chaînage).
- **Lier identité et autorisation.** Un attaquant pourrait signer une transaction avec sa
  propre clé en se déclarant émetteur d'un autre. On vérifie donc systématiquement que
  `adresse(clé_publique) == sender` avant d'accepter une signature.
- **Bootstrap des autorités.** Pour pouvoir agréer le premier établissement, il faut une
  autorité initiale : la *racine*, présente dès le genesis. Pour une démo locale sans
  échange de secret, sa clé est déterministe (à remplacer par une vraie clé en production).
- **Double-dépense dans le mempool.** Un débit est validé non seulement sur le solde
  confirmé mais aussi en tenant compte des transactions déjà en attente, pour éviter de
  débiter deux fois le même solde avant minage.
- **Mempool après réorganisation.** Quand un nœud adopte une chaîne plus longue, une
  transaction restée en attente peut être devenue invalide (débit qui n'est plus
  financé, émetteur révoqué). Une première version se contentait de retirer les
  transactions déjà inscrites ; résultat : une transaction devenue invalide bloquait
  tout minage. Désormais, après adoption d'une chaîne, le mempool est **entièrement
  revalidé** contre le nouvel état (`_revalidate_pending`) et les transactions devenues
  invalides sont purgées.

---

## Limitations connues

Ce projet est un **TP pédagogique** ; certains aspects sont volontairement simplifiés :

- **Clé racine de démo.** La clé de l'autorité racine est déterministe (graine fixe)
  pour que tous les nœuds partagent le même genesis sans échange de secret. En
  production, elle serait générée aléatoirement et protégée (HSM, multi-signature).
- **Signature côté serveur.** `private_key` / `use_root` permettent de signer côté
  serveur pour faciliter les essais. Un déploiement réel signerait côté client ; seule
  la *vérification* compte pour le consensus, et elle reste stricte.
- **Idempotence applicative.** Deux transactions d'intention identique mais signées
  séparément (donc de signatures différentes) restent deux opérations distinctes. Pour
  une vraie protection « une seule fois », fournir un `nonce` stable par opération.
- **Réseau best-effort.** La diffusion aux pairs est synchrone et tolérante aux pannes ;
  la cohérence est rétablie à la demande via `/nodes/resolve` (plus longue chaîne valide),
  pas par un protocole de consensus temps réel.
- **Persistance partielle.** La **chaîne** est persistée sur disque (fichier `.ylia`),
  donc un nœud relancé repart de son dernier état. En revanche, le **mempool**
  (transactions en attente) et la **liste des pairs** restent en mémoire : ils sont perdus
  au redémarrage (les pairs se réenregistrent via `/nodes/register`, le mempool se
  reconstitue par diffusion ou nouvelles soumissions).

