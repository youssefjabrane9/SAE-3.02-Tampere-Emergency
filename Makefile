# Raccourcis pour le projet. Utilisation : make <cible>   (ex. make client)

# Adresse IP de la machine qui fait tourner le serveur (voir le README, étape 4).
# Changez-la ici une fois, ou donnez-la au lancement : make client HOTE=192.168.56.10
HOTE = 127.0.0.1

# Ce qui diffère entre Windows et Linux : le chemin du Python du venv
# et la commande qui affiche l'adresse IP
ifeq ($(OS),Windows_NT)
    PYTHON_SYSTEME = python
    PYTHON = .venv/Scripts/python.exe
    AFFICHER_IP = ipconfig
else
    PYTHON_SYSTEME = python3
    PYTHON = .venv/bin/python
    AFFICHER_IP = hostname -I
endif

# "make" tout seul affiche l'aide
.DEFAULT_GOAL := help

# Ces cibles ne sont pas des fichiers à fabriquer, juste des noms de commandes
.PHONY: help installer installer-client client serveur ip ville

help:
	@echo Commandes disponibles :
	@echo   make installer      cree le .venv et installe requirements.txt
	@echo   make installer-client  pareil, plus les bibliotheques de Qt, pour la VM client
	@echo   make serveur        lance le serveur, serveur/serveur_test.py
	@echo   make client         lance le client vers le serveur $(HOTE)
	@echo   make client HOTE=x  lance le client vers le serveur x
	@echo   make ip             affiche les adresses IP de cette machine
	@echo   make ville          regenere assets/colmar.json depuis assets/colmar_osm.json

installer:
	@$(PYTHON_SYSTEME) outils/verifier_python.py
	$(PYTHON_SYSTEME) -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

# VM client (Linux) : les bibliothèques dont Qt a besoin pour ouvrir une fenêtre, puis make installer
installer-client:
	sudo apt install -y libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1 libxcb-xkb1 \
	    libxcb-image0 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
	    libgl1 libegl1 libfontconfig1 libdbus-1-3
	$(MAKE) installer

client:
	$(PYTHON) lancer_client.py $(HOTE)

serveur:
	$(PYTHON) lancer_serveur.py

ip:
	@$(AFFICHER_IP)

ville:
	$(PYTHON) -m outils.extraire_osm
