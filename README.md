# SAÉ 3.02 : optimisation du trajet des véhicules prioritaires

Application client / serveur en Python (PyQt6, sockets TCP et UDP) sur le vrai réseau de rues de Colmar.
Pour un véhicule d'urgence, à une heure donnée, elle compare 3 trajets :

- **classique** : le plus court en distance ;
- **trafic** : le plus rapide compte tenu du trafic ;
- **priorité** : comme trafic, mais le véhicule demande le feu vert aux carrefours (V2I, en UDP).

| | |
|---|---|
| **Groupe** | Les Nouveaux |
| **Formation** | BUT 2 Réseaux & Télécommunications, SAÉ 3.02 (Développer une application communicante) |
| **Étudiant 1** | JABRANE Youssef : ville, calcul des trajets et serveur |
| **Étudiant 2** | DURAES VALADARES David : client (interface, carte, réseau) et déploiement |

Documents du rendu : [Bilan_Projet.pdf](Bilan_Projet.pdf) et [IAGraphie.pdf](IAGraphie.pdf).

![Comment marche l'application](docs/vue-ensemble.png)

---

## 1. Ce qu'il faut

- Deux VM Linux (Debian 11 à 13 ou Ubuntu 22.04 / 24.04) : une **serveur**, une **client**.
- La VM client a besoin d'un **bureau graphique** (le client ouvre une fenêtre).
- Les deux VM sur le **même réseau** (voir l'étape 2).
- Pour tester sur un PC Windows : [Installation sous Windows](docs/installation-windows.md).

## 2. Préparer le réseau des deux VM

Le client doit joindre le serveur sur le port **TCP 5050** (client ↔ serveur) et le port **UDP 5051** (véhicule ↔ carrefours).

Dans VirtualBox (Configuration de la VM → Réseau), deux possibilités :

| Mode | Quand le choisir | Remarque |
|---|---|---|
| **Accès par pont** (bridge) | À la maison, sur un réseau que vous contrôlez | Les VM prennent une adresse sur votre box (ex. `192.168.1.x`) et ont Internet. Sur le réseau de l'école, le pont est souvent bloqué ou ne donne pas d'adresse. |
| **Réseau privé hôte** (host-only) en carte 2, et **NAT** en carte 1 | Partout, et surtout à l'école | La carte NAT donne Internet, la carte host-only relie les VM entre elles (adresses `192.168.56.x`). C'est le choix le plus sûr. |

Le **pont n'est donc pas obligatoire** : il faut seulement que les deux VM se voient.
Pour vérifier, sur chaque VM : `hostname -I` affiche ses adresses. Depuis le client :

```bash
ping -c 3 <ip du serveur>
```

Si le ping répond, le réseau est bon.

## 3. Installer (sur les deux VM)

### Avoir le droit d'utiliser sudo (Debian)

Sur Debian, si vous avez donné un **mot de passe à root** pendant l'installation, votre compte n'a pas le droit
d'utiliser `sudo` (message `client is not in the sudoers file`). À faire une fois, sur chaque VM concernée :

```bash
su -                      # devient root : tapez le mot de passe de root (pas le vôtre)
apt install -y sudo       # au cas où sudo ne serait pas installé
usermod -aG sudo client   # remplacez "client" par votre nom d'utilisateur (commande : whoami)
exit
```

Puis **déconnectez-vous et reconnectez-vous** (ou redémarrez la VM). Pour vérifier : `groups` doit afficher `sudo`.
Sur Ubuntu, le premier compte a déjà ce droit : rien à faire.

### Installer le projet

```bash
sudo apt update && sudo apt install -y git make python3 python3-venv python3-pip
git clone https://github.com/youssefjabrane9/SAE-3.02-Tampere-Emergency.git
cd SAE-3.02-Tampere-Emergency
```

Puis, **sur la VM serveur** :

```bash
make installer
```

**Sur la VM client** (installe aussi les bibliothèques dont Qt a besoin pour ouvrir une fenêtre) :

```bash
make installer-client
```

Si `sudo` répond `not in the sudoers file` ou `command not found`, voir [Erreurs fréquentes](docs/erreurs.md).

## 4. Lancer

**VM serveur :**

```bash
make ip          # notez l'adresse, par exemple 192.168.56.10
make serveur     # laissez ce terminal ouvert
```

Si le pare-feu est actif (`sudo ufw status` affiche `active`) : `sudo ufw allow 5050/tcp` et `sudo ufw allow 5051/udp`.

**VM client**, avec l'adresse notée :

```bash
make client HOTE=192.168.56.10
```

Ça marche si la barre en bas de la fenêtre affiche « Connecté à 192.168.56.10:5050 » et que la carte apparaît.
Si ce n'est pas le cas, testez d'abord le réseau : `ping -c 3 192.168.56.10`.

**Tout sur une seule machine :** `make serveur` dans un terminal, `make client` dans un autre.

## 5. Utiliser

1. Choisir le **départ** (Hôpital Pasteur ou Commissariat de police).
2. Choisir l'**arrivée** dans la liste, ou **cliquer sur la carte**.
3. Choisir l'**heure** (8 h ou 18 h : heures de pointe).
4. **Calculer** : les 3 trajets s'affichent, 3 véhicules roulent, les temps et le graphique sont à gauche.
5. **Historique** : les dernières simulations.

Exemple : Commissariat de police → Gare de Colmar, à 8 h :

```
Classique : 2102 m, 10 min 46 s
Trafic : 2366 m, 8 min 41 s
Priorité feux : 2120 m, 6 min 30 s
Gain de la priorité : 4 min 16 s
```

Chaque feu que le véhicule prioritaire approche prend un **halo bleu** : la priorité lui est accordée en UDP.

## 6. Arrêter

- Le client : fermer la fenêtre.
- Le serveur : `Ctrl+C` dans son terminal.
- Effacer l'historique : `rm -rf donnees`.

## Commandes make

| Commande | Ce qu'elle fait |
|---|---|
| `make` ou `make help` | affiche la liste des commandes |
| `make installer` | crée le `.venv` et installe `requirements.txt` |
| `make installer-client` | pareil, plus les bibliothèques de Qt (VM client) |
| `make serveur` | lance le serveur |
| `make client HOTE=x` | lance le client vers le serveur `x` (sans `HOTE` : `127.0.0.1`) |
| `make ip` | affiche les adresses IP de la machine |
| `make ville` | regénère `assets/colmar.json` depuis `assets/colmar_osm.json` |

## Pour aller plus loin

- [Installation sans make](docs/installation-manuelle.md)
- [Tester sur Windows](docs/installation-windows.md)
- [Erreurs fréquentes](docs/erreurs.md)
- [Schémas du projet](docs/schemas.md)

Organisation du dépôt :

```
SAE-3.02-Tampere-Emergency/
├── lancer_client.py  lancer_serveur.py   points d'entrée (make client / make serveur)
├── client/     interface : fenêtre, carte, graphique, réseau TCP et UDP
├── serveur/    serveur_test.py : ville, calcul des trajets, carrefours UDP, historique
├── commun/     protocole.py : le contrat entre le client et le serveur
├── outils/     scripts annexes : vérification de Python, préparation de la carte
├── assets/     carte de Colmar
└── docs/       installation sans make, Windows, erreurs, schémas
```
