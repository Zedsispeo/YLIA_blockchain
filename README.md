# YLIA — Blockchain de points de fidélité

YLIA est une **blockchain de points de fidélité** fonctionnant en **Proof of Authority (PoA)**.
Seuls les **établissements agréés** peuvent émettre des transactions sur la chaîne : ils
créditent (attribution de points) et débitent (consommation de points) les comptes des clients.
Les clients, eux, ne font que **gagner** et **dépenser** leurs points.

L'objectif est de fournir un **registre commun, infalsifiable et auditable** des points de
fidélité, partagé entre plusieurs établissements, sans qu'aucun d'eux ne puisse falsifier le
solde d'un client ou s'attribuer des points qu'il n'a pas le droit d'émettre.

---

## Sommaire

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
