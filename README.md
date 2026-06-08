# UPDATE requirements.txt 

`pip freeze > requirements.txt`

---

Voici le gros récapitulatif de notre discussion. On oublie les cryptomonnaies et on résume comment la blockchain fonctionne pour sécuriser votre dossier médical.

---

## 🏗️ L'Architecture Hybride (On-Chain / Off-Chain)

Pour des raisons de poids et de confidentialité (**RGPD**), on ne met jamais les gros fichiers médicaux directement sur la blockchain. L'architecture est divisée en deux :

* **Le stockage (Off-Chain) :** Vos radios, analyses de sang et ordonnances sont chiffrées (illisibles) et stockées sur des serveurs hospitaliers décentralisés ou un réseau partagé (comme IPFS). Chaque fichier possède un identifiant unique et infalsifiable (un **Hash**).
* **Le registre Blockchain (On-Chain) :** C'est une **grosse blockchain unique et partagée** par tous les hôpitaux et le Ministère de la Santé. Elle ne contient que des lignes de texte très légères : *qui* (via des adresses anonymes) a le droit d'accéder à *quel fichier* (le Hash) et *quand*.

---

## 🔗 Blocs, Validateurs et "Minage" médical

* **Le Bloc :** C'est une boîte numérique contenant une liste d'événements médicaux récents (ex: *"Le labo a déposé un résultat"*, *"Le patient X donne un accès au Dr. Y"*). Chaque bloc est scellé au précédent chronologiquement.
* **Le "Minage" (La Validation) :** Pas de calculs mathématiques polluants ici. Les "mineurs" sont les serveurs des hôpitaux, des cliniques ou de l'Ordre des médecins. Ce sont des **nœuds validateurs** qui vérifient que les règles sont respectées (ex: *"Est-ce que le Dr. Y est un vrai médecin ?"*) avant d'ajouter le bloc à la chaîne.

---

## 🔑 Comment se matérialise un don d'accès ? (Le parcours de soin)

Tout repose sur la **cryptographie asymétrique** (un système de cadenas et de clés) et les **Smart Contracts** (des contrats intelligents autonomes).

[Patient (App Mobile)] --(Scanne le QR Code du médecin)--> [Génère une clé de partage]
                                                                      |
                                                                      v
[Médecin (Lecture)]   <--(Vérifie l'expiration à 17h30)-- [Smart Contract (On-Chain)]

1. **Le Consentement :** Chez le médecin, vous scannez son QR code avec votre smartphone. Vous cliquez sur "Autoriser l'accès pour 3 heures" dans votre application.
2. **Le Chiffrement :** Votre téléphone prend la clé du fichier médical, la verrouille spécifiquement pour le "cadenas" (la clé publique) de ce médecin, et envoie cette règle sur la blockchain.
3. **L'Inscription :** Les serveurs des hôpitaux valident cette transaction et l'inscrivent dans un **bloc**.
4. **La Lecture :** Le logiciel du médecin voit l'autorisation sur la blockchain, télécharge le fichier masqué du stockage Off-Chain, et utilise sa **clé privée** (son code secret) pour le déchiffrer et l'afficher à l'écran.
5. **L'Auto-destruction :** À 17h31, le **Smart Contract** bloque automatiquement l'accès. Le médecin ne peut plus rien lire.

---

> 💡 **En une phrase :** La blockchain en santé, c'est un immense coffre-fort national partagé où tout le monde voit les boîtes s'empiler de manière ultra-sécurisée, mais où **vous seul** possédez les clés pour décider quel médecin a le droit d'ouvrir votre boîte, et pour combien de temps.