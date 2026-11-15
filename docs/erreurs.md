# Erreurs fréquentes : causes et solutions

Retour au [README](../README.md). Erreurs propres à Windows : [page Windows](installation-windows.md#6-erreurs-fréquentes-sous-windows).

## Pendant l'installation

| Ce qu'on voit | Cause | Solution |
|---|---|---|
| `client is not in the sudoers file. This incident will be reported.` | Sur Debian, quand on donne un mot de passe à root à l'installation, le premier compte n'a pas le droit d'utiliser `sudo`. | `su -` (mot de passe de root), `apt install -y sudo`, `usermod -aG sudo client` (votre nom, voir `whoami`), `exit`, puis **se déconnecter et se reconnecter**. |
| `sudo: command not found` | Debian installé avec un mot de passe root : `sudo` n'est pas installé. | Même solution que la ligne du dessus (`su -` puis `apt install -y sudo`). |
| Toujours `not in the sudoers file` après `usermod` | Le groupe n'est pris en compte qu'à la connexion suivante. | Se déconnecter et se reconnecter, ou redémarrer la VM. `groups` doit afficher `sudo`. |
| `git: command not found` ou `make: command not found` | La VM est vierge, ces outils ne sont pas installés. | `sudo apt install -y git make` |
| `ensurepip is not available` ou `The virtual environment was not created successfully` | Le paquet `python3-venv` manque. | `sudo apt install -y python3-venv`, puis `rm -rf .venv` et à nouveau `make installer`. |
| `ERREUR : Python 3.x est trop ancien` au début de `make installer` | Le système a un Python plus ancien que 3.9 (Debian 10, Ubuntu 20.04 ou plus vieux). | Installer la VM avec un système plus récent : Debian 12 ou 13, Ubuntu 24.04. |
| `ERREUR : Python 3.14 est plus récent que ce que prévoit requirements.txt` | Système très récent : matplotlib 3.9.4 n'existe pas encore pour cette version. Le projet marche avec **Python 3.9 à 3.13**. | Utiliser Debian 11, 12 ou 13, ou Ubuntu 22.04 ou 24.04. |
| pip install échoue sur `matplotlib-3.9.4.tar.gz` (`Installing build dependencies ... error`, `Unknown compiler(s)`) | Le `.venv` utilise Python 3.14 ou plus récent : pip essaie de compiler matplotlib et numpy. | Recréer le `.venv` avec Python 3.9 à 3.13 (`rm -rf .venv` puis `make installer`). Sous Windows : voir la [page Windows](installation-windows.md#6-erreurs-fréquentes-sous-windows). |
| `ERREUR : le module venv de Python ... n'est pas installé` | Le paquet `python3-venv` manque. | `sudo apt install -y python3-venv`, puis `make installer`. |
| `No matching distribution found for PyQt6` | Système trop ancien pour les paquets de PyQt6 (il faut glibc 2.28, donc Debian 10 ou Ubuntu 18.04 au minimum), ou processeur non x86-64/ARM64. | Prendre Debian 12 ou 13, ou Ubuntu 24.04, en 64 bits. |
| `Temporary failure in name resolution` ou pip qui n'arrive pas à télécharger | La VM n'a pas Internet. | Vérifier que la carte réseau 1 de la VM est en **NAT** (ou en pont), puis `ping -c 3 pypi.org`. |
| `Permission denied` sur `.venv` | Le projet a été cloné avec `sudo`. | Recloner sans `sudo` dans votre dossier personnel. |

## Au lancement du client

| Ce qu'on voit | Cause | Solution |
|---|---|---|
| `Could not load the Qt platform plugin "xcb"` | Il manque des bibliothèques de Qt sur la VM client. | `make installer-client` sur la VM client (ou la liste de l'[installation sans make](installation-manuelle.md)). |
| `qt.qpa.xcb: could not connect to display` | Pas de bureau graphique, ou lancé depuis une connexion SSH. | Lancer le client depuis un terminal **du bureau** de la VM client. |
| `connexion impossible à ... (timed out)` | Mauvaise adresse, ou les VM ne se voient pas. | Vérifier l'adresse avec `make ip` sur le serveur, puis `ping <ip du serveur>` depuis le client. Revoir la [section 2 du README](../README.md#2-préparer-le-réseau-des-deux-vm). |
| `connexion impossible à ... (Connection refused)` | Le serveur n'est pas lancé, ou le pare-feu bloque. | Lancer `make serveur` sur la VM serveur. Si `ufw` est actif : `sudo ufw allow 5050/tcp` et `sudo ufw allow 5051/udp`. |
| La fenêtre s'ouvre mais les véhicules ne demandent pas le feu vert | Le port UDP 5051 est bloqué. | `sudo ufw allow 5051/udp` sur le serveur. |

## Au lancement du serveur

| Ce qu'on voit | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'commun'` | Le serveur a été lancé comme un fichier : `python serveur/serveur_test.py`. Python ne cherche alors les modules que dans `serveur/`. | Depuis le dossier du projet : `make serveur`, ou `python lancer_serveur.py`. |
| `Address already in use` | Un serveur tourne déjà sur ce port. | Faire `Ctrl+C` dans le terminal de l'ancien serveur. Si ce terminal est fermé : `pkill -f lancer_serveur`. |

## Réseau des VM

| Ce qu'on voit | Cause | Solution |
|---|---|---|
| Les deux VM ont la même adresse (`10.0.2.15`) | Elles sont seulement en **NAT** : chacune est isolée. | Ajouter une carte 2 en **Réseau privé hôte** (host-only) sur les deux VM, ou passer en **pont**. |
| En pont, la VM n'a pas d'adresse ou pas d'Internet | Le réseau (école, wifi public) refuse les machines en pont. | Utiliser NAT (carte 1) + Réseau privé hôte (carte 2). |
| `hostname -I` n'affiche pas d'adresse `192.168.56.x` | La carte host-only n'a pas reçu d'adresse. | `sudo dhclient` ou redémarrer la VM ; vérifier dans VirtualBox (Fichier → Gestionnaire de réseau hôte) que le DHCP est actif. |
