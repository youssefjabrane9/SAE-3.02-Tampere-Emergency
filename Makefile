# Raccourcis pour le projet. Utilisation : make <cible>   (ex. make client)

# Ce qui diffère entre Windows et Linux : le chemin du Python du venv
# et la commande qui liste les processus du projet
ifeq ($(OS),Windows_NT)
    PYTHON_SYSTEME = python
    PYTHON = .venv/Scripts/python.exe
    LISTER_PROCESSUS = powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object Name -eq python.exe | Where-Object CommandLine -match 'lancer_|faux_serveur' | Select-Object ProcessId, CommandLine | Format-List"
    ARRETER_PROCESSUS = powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object Name -eq python.exe | Where-Object CommandLine -match 'lancer_|faux_serveur' | Invoke-CimMethod -MethodName Terminate | Out-Null"
else
    PYTHON_SYSTEME = python3
    PYTHON = .venv/bin/python
    LISTER_PROCESSUS = ps -ef | grep -E 'lancer_|faux_serveur' | grep -v grep
    # [l] et [f] : sinon pkill trouverait aussi sa propre commande (qui contient ces mots)
    ARRETER_PROCESSUS = pkill -f '[l]ancer_|[f]aux_serveur'
endif

# "make" tout seul affiche l'aide
.DEFAULT_GOAL := help

# Ces cibles ne sont pas des fichiers à fabriquer, juste des noms de commandes
.PHONY: help installer client serveur faux-serveur tests processus arreter commit ville

help:
	@echo Commandes disponibles :
	@echo   make installer      cree le .venv et installe requirements.txt
	@echo   make faux-serveur   lance le faux serveur (tests du client)
	@echo   make serveur        lance le vrai serveur
	@echo   make client         lance le client sur 127.0.0.1
	@echo   make client HOTE=x  lance le client vers la machine x
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

processus:
	@$(LISTER_PROCESSUS)

# Le "-" devant : pas d'erreur si aucun processus n'était lancé
arreter:
	-@$(ARRETER_PROCESSUS)
	@echo Processus du projet arretes.

commit:
	@$(PYTHON) outils/commit.py

ville:
	$(PYTHON) -m outils.extraire_osm
