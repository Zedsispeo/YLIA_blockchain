# YLIA — Blockchain de points de fidélité (Proof of Authority)

YLIA est une blockchain minimale servant à gérer un programme de points de fidélité entre des établissements agréés et leurs clients. Elle est écrite en Python (Flask) et utilise un consensus **Proof of Authority (PoA)** plutôt qu'un Proof of Work : pas de minage coûteux en calcul, seuls des nœuds explicitement autorisés peuvent produire des blocs.

## Sommaire

- [Principes du projet](#principes-du-projet)
- [Architecture du réseau](#architecture-du-réseau)
- [Démarrer avec Docker](#démarrer-avec-docker)
- [Scripts](#scripts)
- [Endpoints de l'API](#endpoints-de-lapi)
- [Démonstration : scénarios d'utilisation](#démonstration--scénarios-dutilisation)
- [Variables d'environnement](#variables-denvironnement)

## Principes du projet

### Proof of Authority (PoA)

Contrairement à un Proof of Work (Bitcoin) où n'importe quel nœud peut miner en résolvant un puzzle cryptographique, YLIA repose sur une **liste blanche d'autorités agréées** :

- Une **autorité racine** (`root`) existe dès le bloc genesis. C'est la seule identité de confiance au démarrage du réseau.
- Seule la racine peut **agréer** (`register`) ou **révoquer** (`revoke`) une autre identité comme autorité. Ces agréments sont eux-mêmes des transactions inscrites dans la chaîne.
- Seule une adresse figurant dans la liste des autorités courantes peut :
  - **miner un bloc** (agir comme validateur) ;
  - **créditer/débiter** des points de fidélité (transactions `credit` / `debit`).
- Un agrément inscrit dans un bloc ne prend effet **qu'à partir du bloc suivant** — on ne peut pas s'auto-agréer et miner dans la foulée du même bloc.
- Chaque bloc est signé (ECDSA / SECP256k1) par l'autorité qui l'a produit. Un bloc dont le validateur n'est pas (ou plus) agréé, ou dont la signature est invalide, est rejeté par tous les autres nœuds : c'est le cœur du consensus.

### Ce que garantit la chaîne

- **Intégrité** : chaque bloc référence le hash du précédent (`previous_hash`) ; modifier une transaction passée change le hash du bloc et casse la chaîne — détectable via `/validate` ou `/chain` (champs `is_consistent` / `is_valid_signature`).
- **Consensus PoA** : un bloc produit par un nœud non agréé, ou un solde débité au-delà du disponible, est rejeté à l'ajout (`add_block`) comme à la validation complète de la chaîne.
- **Anti-rejeu** : une transaction ne peut être acceptée deux fois (signature déjà vue) et un nonce n'est utilisable qu'une fois par émetteur.
- **Résolution de conflits** : entre nœuds pairs, la chaîne valide la plus longue l'emporte (`/nodes/resolve`), comme dans le modèle Nakamoto classique.

### Rôles métier

| Rôle | Ce qu'il peut faire |
|---|---|
| **Racine (root)** | Agréer/révoquer des établissements ; miner (elle est autorité par défaut). |
| **Établissement agréé** | Miner des blocs ; créditer/débiter des points à des clients. |
| **Client** | Détenir un solde de points, consulter son solde. Ne signe pas de transaction lui-même dans le flux de démo. |
| **Nœud non agréé** | Peut lire la chaîne et proposer des transactions, mais toute tentative de minage ou d'émission de points est rejetée (403/400). |

## Architecture du réseau

Le `docker-compose.yaml` fourni démarre un réseau à 3 nœuds :

| Service | Port | Identité |
|---|---|---|
| `node_a` | 5000 | **Racine** — clé fixe déterministe, seule autorité au genesis. |
| `node_b` | 5001 | Génère et persiste sa propre identité au premier démarrage (`data/node_b/ylia-5001.key`). Doit être agréée par la racine avant de pouvoir miner. |
| `node_c` | 5002 | Identité d'établissement explicite fournie via `.env` (`NODE_C_KEY`), stable entre redémarrages. |

Chaque nœud persiste sa chaîne dans un fichier `.ylia` (JSON) sous `data/<node>/`, monté en volume Docker afin de survivre aux redémarrages des conteneurs.

## Démarrer avec Docker

### Pré-requis

- Docker et Docker Compose.
- Un fichier `.env` à la racine (copier `.env.example`) :

```bash
cp .env.example .env
```

Le fichier `.env` fournit :
- `NODE_C_KEY` : la clé privée fixe de `node_c`.
- `YLIA_DEMO_KEYS` : trois identités de démo partagées (`customer1`, `customer2`, `responsable`) — utile pour qu'un front-end affiche les mêmes comptes quel que soit le nœud interrogé.

### Lancer le réseau

```bash
docker compose up --build
```

Cela démarre les 3 nœuds (`node_a`, `node_b`, `node_c`) sur les ports 5000/5001/5002, chacun avec son propre volume de données sous `./data/`.

### Initialiser le réseau

Une fois les conteneurs démarrés, le réseau est vierge : les nœuds ne se connaissent pas encore et `node_b`/`node_c` ne sont pas encore des autorités. Le script `scripts/init_network.sh` automatise ce bootstrap (voir section suivante) :

```bash
./scripts/init_network.sh
```

### Vérifier l'état d'un nœud

```bash
curl http://localhost:5000/
curl http://localhost:5000/health
curl http://localhost:5000/chain
```

### Arrêter le réseau

```bash
docker compose down
```

(Les données restent dans `./data/` grâce aux volumes montés ; supprimer ce dossier repart d'une chaîne vierge.)

## Scripts

### `scripts/init_network.sh`

Bootstrap complet d'un réseau à 3 nœuds (pensé pour être lancé après `docker compose up`) :

1. Attend que les 3 nœuds répondent sur `/health`.
2. Enregistre chaque nœud comme pair des deux autres (`/nodes/register`), via les noms d'hôtes Docker (`node_a`, `node_b`, `node_c`).
3. Récupère les adresses de `node_b`, `node_c`, et de l'identité de démo `responsable`.
4. Agrée ces trois adresses comme autorités depuis `node_a` (la racine).
5. Mine un bloc sur `node_a` pour rendre ces agréments effectifs.
6. Fait résoudre les conflits sur `node_b` et `node_c` pour qu'ils synchronisent le nouveau bloc.

Variables d'environnement optionnelles : `HOST`, `A_PORT`, `B_PORT`, `C_PORT`, `TIMEOUT`.

### `scripts/run_two_nodes.sh`

Démarrage rapide en local (hors Docker) de deux nœuds Python pour une démo manuelle : `node A` (racine, port 5000) et `node B` (port 5001). Ctrl-C arrête les deux processus.

```bash
./scripts/run_two_nodes.sh
```

### `scripts/demo.py`

Démonstration de bout en bout, entièrement automatisée (démarre elle-même 3 nœuds locaux) qui prouve successivement :

1. **Chaînage** : minage de blocs et vérification que `previous_hash` de chaque bloc correspond bien au hash du précédent.
2. **Transactions** : agrément d'un établissement, crédit puis débit de points, vérification du solde final.
3. **Falsification** : modification du montant d'une transaction dans un bloc déjà miné → la chaîne devient invalide (`/validate`).
4. **Résolution de conflits** : un nœud en retard adopte la chaîne plus longue et valide d'un pair, et les deux convergent vers les mêmes hashes.
5. **Consensus PoA** : une transaction émise par une identité non agréée est rejetée (400), tout comme un bloc miné par un nœud non agréé (403) ou signé par un validateur non agréé.

```bash
python scripts/demo.py
```

## Endpoints de l'API

Le catalogue complet est aussi consultable en direct via `GET /` sur n'importe quel nœud.

### Index / santé

| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Catalogue des endpoints + informations sur le nœud interrogé. |
| GET | `/health` | Sonde de vivacité (liveness). |
| GET | `/node` | Informations détaillées sur le nœud (adresse, autorité, racine, pairs, longueur de chaîne, mempool). |

### Chaîne et transactions

| Méthode | Route | Description |
|---|---|---|
| GET | `/chain` | La chaîne complète, avec pour chaque bloc les indicateurs `is_consistent` et `is_valid_signature`. |
| POST | `/transactions/new` | Soumettre une transaction (`credit` ou `debit`), signée côté client ou côté serveur. |
| GET | `/mine` | Miner un bloc avec les transactions en attente (réservé aux autorités agréées). |
| GET | `/pending` | Lister les transactions en attente (mempool). |
| DELETE | `/transactions/pending` | Vider le mempool (opération d'exploitation). |
| GET | `/validate` | Indique si la chaîne est valide, avec la raison en cas d'invalidité. |

### Réseau multi-nœuds

| Méthode | Route | Description |
|---|---|---|
| POST | `/nodes/register` | Enregistrer des pairs : `{"nodes": ["http://..."]}`. |
| GET | `/nodes` | Lister les pairs connus. |
| GET | `/nodes/resolve` | Résolution de conflits : adopte la chaîne la plus longue et valide parmi les pairs. |
| POST | `/blocks/receive` | Recevoir un bloc diffusé par un pair (rejeté avec 409 si le consensus est invalide). |

### Autorités (PoA)

| Méthode | Route | Description |
|---|---|---|
| GET | `/authorities` | Liste blanche des autorités agréées + adresse racine. |
| POST | `/authorities/register` | Agréer un établissement : `{"address": "YLIA..."}` (racine uniquement). |
| POST | `/authorities/revoke` | Révoquer un établissement : `{"address": "YLIA..."}` (racine uniquement). |

### Soldes / portefeuille

| Méthode | Route | Description |
|---|---|---|
| GET | `/balance/<address>` | Solde confirmé et disponible (mempool inclus) d'un compte. |
| GET | `/balances` | Tous les soldes connus. |
| GET | `/wallet/new` | Générer une nouvelle paire de clés (clé privée, clé publique, adresse). |

### Démo

| Méthode | Route | Description |
|---|---|---|
| GET | `/demo/roles` | Identités de démo partagées entre nœuds (`customer1`, `customer2`, `responsable`), dérivées de `YLIA_DEMO_KEYS`. |

### Format des transactions (`POST /transactions/new`)

Trois façons de fournir une transaction :

1. **Pré-signée côté client** : fournir `public_key` + `signature` (et optionnellement `sender`).
2. **Signature côté serveur avec une clé fournie** : fournir `private_key` (la clé publique et l'adresse sont recalculées serveur).
3. **Mode démo avec la racine** : `use_root: true` fait signer la transaction avec la clé de la racine.

Champs communs : `type` (`credit` ou `debit`), `recipient`, `amount`, `nonce` (optionnel, anti-rejeu).

## Démonstration : scénarios d'utilisation

Une fois le réseau démarré et initialisé (voir [Démarrer avec Docker](#démarrer-avec-docker)), voici des scénarios concrets pour prendre en main le projet — à la main via `curl`/l'interface `/ui`, ou directement inspirés des tests fonctionnels du projet.

### Préconditions

1. **Copier le fichier d'environnement** (obligatoire — sans cela les identités de démo et la clé de `node_c` ne sont pas définies) :

   ```bash
   cp .env.example .env
   ```

2. **Démarrer les conteneurs :**

   ```bash
   docker compose up --build
   ```

   Trois nœuds sont créés sur le même réseau Docker, joignables entre eux par leur nom d'hôte, et exposés localement :

   | Nœud | URL interne (réseau Docker) | URL locale |
   |---|---|---|
   | A (racine) | `http://node_a:5000` | `http://localhost:5000` |
   | B | `http://node_b:5001` | `http://localhost:5001` |
   | C | `http://node_c:5002` | `http://localhost:5002` |

   Les nœuds ne se désignent entre eux que par leur URL réseau Docker (`node_a`, `node_b`, `node_c`), jamais par `localhost`.

3. **Initialiser le réseau** (enregistre les pairs, agrée les autorités, mine le premier bloc) :

   ```bash
   chmod +x scripts/init_network.sh
   ./scripts/init_network.sh
   ```

L'écosystème est alors prêt.

### 1. Création d'un bloc

**Étapes**

1. Récupérer l'identité de démo `responsable` (agréée comme autorité par `init_network.sh`) :

   ```bash
   curl http://localhost:5000/demo/roles
   ```

2. Ajouter une transaction signée par le `responsable` :

   ```bash
   curl -X POST http://localhost:5000/transactions/new \
     -H 'Content-Type: application/json' \
     -d '{"type":"credit","recipient":"<adresse_client>","amount":50,"private_key":"<clé_privée_responsable>"}'
   ```

3. Miner :

   ```bash
   curl http://localhost:5000/mine
   ```

**Résultat attendu** : ✅ un nouveau bloc est créé et ajouté à la chaîne (visible via `curl http://localhost:5000/chain`).

### 2. Vérification de la détection d'erreurs

**Étapes**

1. Créer un nouveau bloc (scénario 1).
2. Injecter une transaction frauduleuse dans un bloc déjà miné (index ≥ 1), par exemple via l'endpoint de démo `/tamper` de l'interface (`/ui`) :

   ```json
   {
     "index": 1,
     "transaction": { "sender": "attacker", "recipient": "pizzha.se", "amount": 9999 }
   }
   ```

3. Demander la validation de la chaîne :

   ```bash
   curl http://localhost:5000/validate
   curl http://localhost:5000/chain
   ```

**Résultat attendu** : ✅ le système détecte l'altération : `/validate` renvoie `valid: false` avec la raison, et dans `/chain` le bloc concerné (ex. index `1`) a `is_consistent`/`is_valid_signature` à `false`.

### 3. Résolution de conflits — Cas n°1 (le pair a une chaîne plus courte)

**Étapes**

1. Démarrer deux nœuds locaux, ports `5000` et `5001` (`./scripts/run_two_nodes.sh`).
2. Sur le nœud `5000`, enregistrer `5001` comme pair : `POST /nodes/register` avec `{"nodes":["http://127.0.0.1:5001"]}`.
3. Sur le nœud `5000`, miner un bloc (`GET /mine`).
4. Sur le nœud `5001`, miner deux blocs.
5. Depuis le nœud `5001`, lancer la résolution : `GET /nodes/resolve`.

**Résultat attendu** : ✅ la chaîne du nœud `5001` est conservée, car elle est déjà la plus longue et valide.

### 4. Résolution de conflits — Cas n°2 (le pair a une chaîne plus longue)

**Étapes**

1. Démarrer deux nœuds locaux, ports `5000` et `5001`.
2. Sur le nœud `5000`, enregistrer `5001` comme pair.
3. Sur le nœud `5001`, miner un bloc.
4. Sur le nœud `5000`, miner deux blocs.
5. Depuis le nœud `5001`, lancer la résolution : `GET /nodes/resolve`.

**Résultat attendu** : ✅ le nœud `5001` adopte la chaîne du nœud `5000`, celle-ci étant plus longue et valide.

### 5. Envoi d'un bloc à un pair (bloc valide ou corrompu)

**Étapes**

1. Démarrer deux nœuds locaux, ports `5000` et `5001`, et enregistrer `5001` comme pair de `5000`.
2. Sur le nœud `5000`, miner un nouveau bloc et récupérer son JSON (`GET /chain`, dernier élément).
3. Transmettre ce bloc au pair :

   ```bash
   curl -X POST http://127.0.0.1:5001/blocks/receive \
     -H 'Content-Type: application/json' \
     -d '<bloc JSON>'
   ```

**Résultats attendus**

- **Chaînes divergentes** : ❌ si le bloc ne prolonge pas la tête de chaîne du nœud `5001` (ou que son hash/signature a été altéré), la requête renvoie `409` avec `{"accepted": false, "reason": "..."}`.
- **Chaînes synchronisées** : ✅ si le bloc prolonge correctement la tête de chaîne du nœud `5001` (par ex. après une résolution de conflits réussie), il est accepté (`201`, `{"accepted": true, ...}`).

## Variables d'environnement

| Variable | Description |
|---|---|
| `YLIA_PORT` / `PORT` | Port d'écoute du nœud. |
| `YLIA_NODE_KEY` / `NODE_KEY` | Clé privée explicite de l'identité du nœud. Absente → identité persistée/générée automatiquement. |
| `YLIA_ROOT_KEY` | Clé privée de l'autorité racine (par défaut : clé déterministe `0x01`, à changer en production). |
| `YLIA_DEMO_KEYS` | JSON `{role: clé_privée}` pour des identités de démo partagées entre tous les nœuds. |
| `YLIA_DATA_DIR` | Répertoire de persistance (par défaut `data`). |
| `YLIA_CHAIN_FILE` / `YLIA_KEY_FILE` | Force un chemin explicite pour la chaîne / la clé du nœud. |
| `YLIA_PEER_TIMEOUT` | Timeout (secondes) des appels réseau entre pairs (par défaut `3.0`). |
| `NODE_C_KEY` | Clé privée fixe utilisée par `node_c` dans `docker-compose.yaml`. |
