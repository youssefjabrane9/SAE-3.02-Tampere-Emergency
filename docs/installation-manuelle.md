# Installation manuelle, sans make

Les mêmes étapes que dans le [README](../README.md), mais en tapant les commandes Python à la main.
Chaque commande `make` du projet n'est qu'un raccourci vers une des commandes ci-dessous.
C'est la solution si `make` n'est pas installé. Pour Windows, voir la [page Windows](installation-windows.md).

## 1. Prérequis (sur les deux VM)

Si `sudo` répond `... is not in the sudoers file`, voir les [erreurs fréquentes](erreurs.md).

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
python3 --version        # doit afficher une version de 3.9 à 3.13
```

Sur la VM client seulement, les bibliothèques de Qt :

```bash
sudo apt install -y libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1 libxcb-xkb1 \
    libxcb-image0 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
    libgl1 libegl1 libfontconfig1 libdbus-1-3
```

## 2. Télécharger le projet

```bash
git clone https://github.com/youssefjabrane9/SAE-3.02-Tampere-Emergency.git
cd SAE-3.02-Tampere-Emergency
```

## 3. Créer l'environnement Python et installer les dépendances

```bash
python3 -m venv .venv                 # crée le dossier .venv
source .venv/bin/activate             # active le venv : l'invite commence par (.venv)
pip install -r requirements.txt       # installe PyQt6 et matplotlib dans le venv
```

Tant que le venv est activé, `python` désigne le Python du `.venv`.
Il faut refaire `source .venv/bin/activate` dans **chaque nouveau terminal**.

## 4. Lancer

Sur la VM serveur :

```bash
source .venv/bin/activate
hostname -I                           # note l'adresse du serveur
python lancer_serveur.py
```

Attention : il faut lancer **`lancer_serveur.py`**, depuis le dossier du projet.
`python serveur/serveur_test.py` donne `No module named 'commun'` : lancé comme un simple fichier, Python ne cherche
les modules que dans `serveur/`, et ne voit donc pas le dossier `commun/`.

Sur la VM client :

```bash
source .venv/bin/activate
python lancer_client.py 192.168.56.10     # l'adresse du serveur
```

Sans adresse (`python lancer_client.py`), le client se connecte à `127.0.0.1` (la même machine).

## 5. Vérifier l'installation

```bash
python -c "import PyQt6.QtWidgets, matplotlib"     # ne doit rien afficher
```

## 6. Arrêter et nettoyer

```bash
# Ctrl+C dans le terminal du serveur ou du client (ou fermer la fenêtre du client)
deactivate                 # quitte le venv dans ce terminal
rm -rf .venv               # supprime le venv
rm -rf donnees             # supprime l'historique des simulations
```

Si un programme tourne encore en arrière-plan :

```bash
ps -ef | grep lancer_ | grep -v grep     # le voir
pkill -f '[l]ancer_'                     # l'arrêter
```

## Correspondance avec make

| make | Commande équivalente |
|---|---|
| `make installer` | `python3 outils/verifier_python.py`, `python3 -m venv .venv` puis `.venv/bin/python -m pip install -r requirements.txt` |
| `make installer-client` | la commande `sudo apt install` des bibliothèques de Qt (étape 1), puis `make installer` |
| `make serveur` | `.venv/bin/python lancer_serveur.py` |
| `make client HOTE=x` | `.venv/bin/python lancer_client.py x` |
| `make ip` | `hostname -I` |
| `make ville` | `.venv/bin/python -m outils.extraire_osm` |

`make` appelle directement `.venv/bin/python` : c'est pour ça qu'il n'a pas besoin d'activer le venv.
