# Raccourcis pour le projet. Utilisation : make <cible>   (ex. make client)

# Adresse IP de la machine qui fait tourner le serveur (voir docs/installation.md).
# Changez-la ici une fois, ou donnez-la au lancement : make client HOTE=192.168.56.10
HOTE = 127.0.0.1

# Ce qui diffère entre Windows et Linux : le chemin du Python du venv
# et les commandes qui affichent l'adresse IP et les processus du projet
ifeq ($(OS),Windows_NT)
    PYTHON_SYSTEME = python
    PYTHON = .venv/Scripts/python.exe
    AFFICHER_IP = ipconfig
    LISTER_PROCESSUS = powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object Name -eq python.exe | Where-Object CommandLine -match 'lancer_|faux_serveur' | Select-Object ProcessId, CommandLine | Format-List"
    ARRETER_PROCESSUS = powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object Name -eq python.exe | Where-Object CommandLine -match 'lancer_|faux_serveur' | Invoke-CimMethod -MethodName Terminate | Out-Null"
else
    PYTHON_SYSTEME = python3
    PYTHON = .venv/bin/python
    AFFICHER_IP = hostname -I
    LISTER_PROCESSUS = ps -ef | grep -E 'lancer_|faux_serveur' | grep -v grep
    # [l] et [f] : sinon pkill trouverait aussi sa propre commande (qui contient ces mots)
    ARRETER_PROCESSUS = pkill -f '[l]ancer_|[f]aux_serveur'
endif

# "make" tout seul affiche l'aide
.DEFAULT_GOAL := help

# Ces cibles ne sont pas des fichiers à fabriquer, juste des noms de commandes
.PHONY: help installer client serveur faux-serveur tests ip processus arreter commit ville

help:
	@echo Commandes disponibles :
	@echo   make installer      cree le .venv et installe requirements.txt
	@echo   make faux-serveur   lance le faux serveur, pour tester le client
	@echo   make serveur        lance le vrai serveur
	@echo   make client         lance le client vers le serveur $(HOTE)
	@echo   make client HOTE=x  lance le client vers le serveur x
	@echo   make ip             affiche les adresses IP de cette machine
	@echo   make tests          lance les tests unittest
	@echo   make processus      affiche les serveurs et clients en cours
	@echo   make arreter        arrete tous les serveurs et clients du projet
	@echo   make ville          regenere assets/colmar.json depuis assets/colmar_osm.json
	@echo   make commit        demande un message puis fait git add + commit + push

installer:
	$(PYTHON_SYSTEME) -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

client:
	$(PYTHON) lancer_client.py $(HOTE)

serveur:
	$(PYTHON) lancer_serveur.py

faux-serveur:
	$(PYTHON) -m outils.faux_serveur

tests:
	$(PYTHON) -m unittest discover tests

ip:
	@$(AFFICHER_IP)

processus:
	@$(LISTER_PROCESSUS) || echo Aucun serveur ni client du projet en cours.

# Le "-" devant : pas d'erreur si aucun processus n'était lancé
arreter:
	-@$(ARRETER_PROCESSUS)
	@echo Processus du projet arretes.

commit:
	@$(PYTHON) outils/commit.py

ville:
	$(PYTHON) -m outils.extraire_osm
