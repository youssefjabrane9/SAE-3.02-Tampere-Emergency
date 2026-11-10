# Installer et lancer le projet sur Linux

Ce guide part de **deux machines Linux vierges** (Ubuntu ou Debian), sur le même réseau :

- **VM 1 : le serveur** (calcule les trajets, joue les carrefours) ;
- **VM 2 : le client** (la fenêtre avec la carte). Elle a besoin d'un bureau graphique.

Les deux programmes communiquent par le port **TCP 5050** (client ↔ serveur) et le port **UDP 5051** (véhicule ↔ carrefours).

Toutes les commandes se tapent dans un terminal.

---

## 1. Sur les deux VM : installer le projet (une seule fois)

```bash
sudo apt update
sudo apt install -y git make python3 python3-venv python3-pip
git clone https://github.com/youssefjabrane9/SAE-3.02-Tampere-Emergency.git
cd SAE-3.02-Tampere-Emergency
make installer
```

`make installer` crée un environnement Python (`.venv`) et y installe les versions exactes de `requirements.txt` (PyQt6, matplotlib).

**Sur la VM client seulement**, il faut aussi les bibliothèques dont Qt a besoin pour ouvrir une fenêtre :

```bash
sudo apt install -y libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1 libxcb-xkb1
```

Pour vérifier l'installation : `make tests` doit finir par `OK`.

---

## 2. Sur la VM serveur : lancer le serveur

```bash
make ip
```

Note l'adresse affichée (par exemple `192.168.56.10`) : le client en a besoin.

```bash
make serveur
```

Laisse ce terminal ouvert pendant toute la démo. `Ctrl+C` pour arrêter le serveur.

---

## 3. Sur la VM client : lancer le client

```bash
make client HOTE=192.168.56.10
```

(remplace par l'adresse notée à l'étape 2)

Pour ne pas retaper l'adresse à chaque fois : ouvre le `Makefile` et change la ligne `HOTE = 127.0.0.1` tout en haut. Ensuite, `make client` suffit.

**Ça marche si** la barre en bas de la fenêtre affiche « Connecté à 192.168.56.10:5050 » et que la carte de Colmar apparaît, avec les rues colorées selon le trafic.

---

## 4. Faire une simulation

1. **Départ** : l'Hôpital Pasteur ou le Commissariat de police.
2. **Arrivée** : tape une adresse (« bruat » propose « Rue Bruat ») ou clique sur la carte.
3. **Heure** : de 0 à 23 h (8 h ou 18 h pour les heures de pointe).
4. **Calculer** : les 3 trajets s'affichent et 3 véhicules roulent. Le temps de chaque trajet et le graphique apparaissent à gauche.
5. **Effacer** remet la carte à zéro. **Historique** montre les dernières simulations.

---

## Tout sur une seule machine

C'est possible aussi (pour tester) : `make serveur` dans un terminal, `make client` dans un autre. Sans `HOTE=`, le client se connecte à `127.0.0.1`, c'est-à-dire la même machine.

---

## Si ça ne marche pas

| Ce qu'on voit | Ce qu'il faut faire |
|---|---|
| `connexion impossible à ... (timed out)` | Mauvaise adresse, ou les VM ne se voient pas. Depuis le client : `ping 192.168.56.10`. Si un pare-feu est actif sur le serveur : `sudo ufw allow 5050/tcp` puis `sudo ufw allow 5051/udp`. |
| `connexion impossible à ... (Connection refused)` | Le serveur n'est pas lancé (étape 2). |
| `Could not load the Qt platform plugin "xcb"` | Il manque les bibliothèques de la VM client (fin de l'étape 1). |
| `ensurepip is not available` pendant `make installer` | `sudo apt install -y python3-venv`, puis `rm -rf .venv` et à nouveau `make installer`. |
| `Address already in use` au lancement du serveur | Un serveur tourne déjà : `make processus` pour le voir, `make arreter` pour l'arrêter. |
| `make: command not found` | `sudo apt install -y make` |

---

## Les commandes du projet

`make` tout seul affiche la liste :

| Commande | Ce qu'elle fait |
|---|---|
| `make installer` | crée le `.venv` et installe `requirements.txt` |
| `make serveur` | lance le serveur |
| `make faux-serveur` | lance le faux serveur (pour tester le client sans le vrai serveur) |
| `make client` | lance le client vers l'adresse `HOTE` du Makefile |
| `make client HOTE=x` | lance le client vers le serveur `x` |
| `make ip` | affiche les adresses IP de cette machine |
| `make tests` | lance les tests |
| `make processus` | affiche les serveurs et clients du projet en cours |
| `make arreter` | arrête tous les serveurs et clients du projet |
