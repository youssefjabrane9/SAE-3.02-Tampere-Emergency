# Installation sous Windows (un seul PC, pour tester)

Retour au [README](../README.md) (installation sur les VM Linux).

Le projet est prévu pour deux VM Linux. Cette page sert seulement à le tester sur **un PC Windows** :
le serveur et le client tournent sur la même machine, dans deux fenêtres PowerShell.
Toutes les commandes se tapent dans **PowerShell**, depuis le dossier du projet.

## 1. Installer Python 3.9 à 3.13

Il faut **Python 3.13 au plus** : `matplotlib` 3.9.4 (dans `requirements.txt`) n'existe pas pour Python 3.14.
Si on installe la dernière version de python.org, l'installation des paquets échoue, et le client affiche ensuite
`No module named 'PyQt6'`.

Le plus simple, dans PowerShell :

```powershell
winget install Python.Python.3.13
```

Ou sur [python.org](https://www.python.org/downloads/windows/) : **Python 3.13**, « Windows installer (64-bit) », en cochant **Add python.exe to PATH**.

Fermer et rouvrir PowerShell, puis vérifier : `py -3.13 --version` doit afficher `Python 3.13.x`.
Python 3.13 peut être installé à côté d'un Python 3.14 : `py -3.13` choisit la bonne version.

## 2. Télécharger le projet

```powershell
winget install Git.Git        # puis fermer et rouvrir PowerShell
git clone https://github.com/youssefjabrane9/SAE-3.02-LesNouveaux.git
cd SAE-3.02-LesNouveaux
```

Sans git : sur GitHub, **Code → Download ZIP**, puis extraire le ZIP et ouvrir PowerShell dans le dossier `SAE-3.02-LesNouveaux-main`.

## 3. Créer l'environnement Python et installer les paquets

```powershell
py -3.13 -m venv .venv                                        # crée le dossier .venv avec Python 3.13
.venv\Scripts\python -m pip install -r requirements.txt       # installe PyQt6 et matplotlib
```

Si un `.venv` existe déjà (créé avec un autre Python), le supprimer d'abord : `Remove-Item -Recurse -Force .venv`.
Vérifier ensuite : `.venv\Scripts\python --version` doit afficher `Python 3.13.x`.

La deuxième ligne est **obligatoire** : sans elle, le client affiche `No module named 'PyQt6'`.
Elle doit finir par `Successfully installed ... PyQt6 ... matplotlib ...`.

Pour vérifier : `.venv\Scripts\python -c "import PyQt6.QtWidgets, matplotlib"` ne doit rien afficher.

## 4. Lancer

Fenêtre PowerShell 1, le serveur :

```powershell
.venv\Scripts\python lancer_serveur.py
```

Fenêtre PowerShell 2, le client (il se connecte à `127.0.0.1`, le même PC) :

```powershell
.venv\Scripts\python lancer_client.py
```

Lancer **`lancer_serveur.py`**, depuis le dossier du projet. `python serveur\serveur_test.py` donne
`No module named 'commun'` : lancé comme un simple fichier, Python ne cherche les modules que dans `serveur\`.

Pour arrêter : fermer la fenêtre du client, puis `Ctrl+C` dans la fenêtre du serveur.

## 5. Avec make (facultatif)

`make` n'est pas fourni avec Windows. Pour pouvoir taper les mêmes commandes que sous Linux
(`make installer`, `make serveur`, `make client`) :

```powershell
winget install ezwinports.make
```

Ou, si [Chocolatey](https://chocolatey.org/install) est installé : `choco install make` (PowerShell en administrateur).
Ensuite, **fermer et rouvrir PowerShell**, puis vérifier avec `make --version`.

`make installer` utilise la commande `python` : il faut que ce soit Python 3.13 au plus (`python --version`).
Sinon, faire l'étape 3 à la main.

## 6. Erreurs fréquentes sous Windows

| Ce qu'on voit | Cause | Solution |
|---|---|---|
| `make : The term 'make' is not recognized as the name of a cmdlet...` | `make` n'est pas fourni avec Windows. | Lancer les commandes à la main (étapes 3 et 4), ou installer make (étape 5). |
| Toujours `not recognized` juste après une installation avec `winget` | PowerShell a gardé l'ancien PATH. | Fermer **toutes** les fenêtres PowerShell (et VS Code), puis en rouvrir une. |
| `No module named 'PyQt6'` | Les paquets ne sont pas installés dans le `.venv`. | `.venv\Scripts\python -m pip install -r requirements.txt` (étape 3). |
| pip échoue sur `matplotlib` : `Using cached matplotlib-3.9.4.tar.gz`, puis `Installing build dependencies ... error` et `ERROR: Unknown compiler(s)` (ou `Microsoft Visual C++ 14.0 is required`) | Le `.venv` a été créé avec **Python 3.14** ou plus récent (on voit `cp314` dans les noms de fichiers). matplotlib 3.9.4 n'existe pas tout prêt pour cette version : pip essaie de le compiler, et Windows n'a pas de compilateur. Le projet marche avec **Python 3.9 à 3.13**. | `winget install Python.Python.3.13`, rouvrir PowerShell, `Remove-Item -Recurse -Force .venv`, `py -3.13 -m venv .venv`, puis `.venv\Scripts\python -m pip install -r requirements.txt`. |
| `No module named 'commun'` | Le serveur a été lancé comme un fichier (`python serveur\serveur_test.py`). | `.venv\Scripts\python lancer_serveur.py` |
| `.venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled` | PowerShell bloque les scripts. | Inutile d'activer le venv : utiliser `.venv\Scripts\python` comme dans cette page. |
| Pare-feu Windows : « Autoriser l'accès ? » au lancement du serveur | Le serveur écoute sur les ports 5050 et 5051. | Cliquer **Autoriser** (réseaux privés suffit). |
| `Address already in use` / `Only one usage of each socket address` | Un serveur tourne déjà. | `Ctrl+C` dans sa fenêtre, ou fermer `python.exe` dans le Gestionnaire des tâches. |
