
# SAE 3.02 - Tampere Emergency

## 1. Présentation

Projet réalisé en BUT 2 Réseaux et Télécommunications,
parcours Développement Système et Cloud.

Équipe : Les Nouveaux

Membres :
- Youssef Jabrane
- David Duraes Valadares

L'objectif est de développer une application communicante
qui aide les véhicules d'urgence à choisir un itinéraire.

Notre application utilise actuellement une carte de Colmar.
Elle permet de comparer trois stratégies de déplacement.

## 2. Fonctionnalités réalisées

- Affichage de la carte de Colmar.
- Sélection du départ et de l'arrivée.
- Choix de l'heure entre 0 h et 23 h.
- Calcul d'itinéraires avec Dijkstra.
- Prise en compte des sens uniques dans le graphe.
- Simulation du trafic selon l'heure.
- Simulation d'une réduction d'attente aux feux.
- Affichage de trois itinéraires sur la carte.
- Comparaison des distances et des temps.
- Communication TCP entre le client et le serveur.
- Échange de messages au format JSON.

Les calculs de trafic sont simulés.
Ils ne correspondent pas à des données de circulation réelles.

## 3. Les trois stratégies

### Classique

Dijkstra recherche le chemin le plus court en distance.

### Trafic

Dijkstra recherche un itinéraire en utilisant des temps
de parcours simulés selon l'heure et les routes chargées.

### Prioritaire

Dijkstra recherche un itinéraire en supposant que le
véhicule prioritaire attend moins longtemps à certains feux.

La commande réelle des feux n'est pas encore implémentée.

## 4. Technologies utilisées

- Python 3
- PyQt6 pour l'interface graphique
- Socket TCP pour la communication
- JSON pour les messages
- Heapq pour l'algorithme Dijkstra
- OpenStreetMap pour les données cartographiques

## 5. Organisation du projet

assets/
    colmar.json : données des routes et des noeuds
    colmar.png : image de la carte

client/
    carte.py : affichage de la carte
    fenetre.py : interface utilisateur
    reseau.py : communication avec le serveur

serveur/
    serveur_test.py : serveur TCP et calcul des trajets

sae/
    protocole.py : encodage et décodage des messages

lancer_serveur.py : lancement du serveur
lancer_client.py : lancement du client
requirements.txt : dépendances Python
README.md : documentation

## 6. Installation sur Windows

Prérequis :
- Python 3 installé
- Git installé
- Une connexion Internet pour installer les dépendances

Ouvrir un terminal dans le dossier du projet.

Créer un environnement virtuel :

    python -m venv .venv

Activer l'environnement dans PowerShell :

    .\.venv\Scripts\Activate.ps1

Installer les dépendances :

    python -m pip install -r requirements.txt

Si PowerShell bloque l'activation, on peut utiliser
directement le Python de l'environnement :

    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

## 7. Lancer l'application sur Windows

Ouvrir deux terminaux dans le dossier du projet.

Terminal 1 - Serveur :

    python lancer_serveur.py

Terminal 2 - Client :

    python lancer_client.py

Le serveur doit être démarré avant le client.

## 8. Installation sur Linux (Ubuntu/Debian)

Cette procédure est à vérifier sur une machine Linux vierge.

Installer Python et les outils nécessaires :

    sudo apt update
    sudo apt install python3 python3-venv python3-pip git

Récupérer le projet :

    git clone https://github.com/youssefjabrane/SAE-3.02-Tampere-Emergency.git

Entrer dans le dossier :

    cd SAE-3.02-Tampere-Emergency

Récupérer la branche de travail :

    git switch youssef/strategies-colmar

Créer l'environnement virtuel :

    python3 -m venv .venv

Activer l'environnement :

    source .venv/bin/activate

Installer les dépendances :

    python3 -m pip install -r requirements.txt

Lancer le serveur :

    python3 lancer_serveur.py

Dans un deuxième terminal, depuis le dossier du projet :

    .venv/bin/python lancer_client.py

Sur une machine Linux sans environnement graphique,
le client PyQt6 ne pourra pas afficher sa fenêtre.

## 9. Utilisation

1. Démarrer le serveur.
2. Démarrer le client.
3. Attendre l'affichage de la carte.
4. Choisir un point de départ.
5. Choisir un point d'arrivée.
6. Sélectionner une heure.
7. Cliquer sur Calculer.
8. Comparer les trois résultats.

Couleurs :
- Bleu : classique
- Orange : trafic
- Vert : prioritaire

Certains itinéraires peuvent se superposer.

## 10. Communication réseau

Le client communique avec le serveur en TCP.

Adresse utilisée actuellement :
127.0.0.1

Port TCP :
5050

Les messages sont envoyés au format JSON.

Exemple de demande :

    {
        "type": "COMPUTE_ROUTE",
        "depart": "A1",
        "arrivee": "B2",
        "heure": 8
    }

Les identifiants réels des noeuds sont ceux de colmar.json.

Le serveur renvoie les chemins, les distances et les temps.

Le client utilise les résultats pour tracer les itinéraires.

## 11. Algorithme Dijkstra

Dijkstra permet de trouver un chemin de coût minimal
dans un graphe dont les coûts sont positifs.

Dans notre projet :
- Les noeuds représentent les points du réseau routier.
- Les arêtes représentent les routes.
- Les poids représentent les distances ou les temps.
- Une file de priorité permet d'explorer les noeuds.

La stratégie classique minimise la distance.
Les deux autres stratégies minimisent un temps simulé.

## 12. Tests réalisés

Tests manuels effectués sous Windows :

- Démarrage du serveur TCP.
- Connexion du client au serveur.
- Chargement de la carte de Colmar.
- Sélection du départ et de l'arrivée.
- Calcul des trois stratégies.
- Affichage des distances et des temps.
- Tracé des trois itinéraires.

Exemple observé :
Départ : Champ de Mars
Arrivée : Théâtre municipal
Heure : 8 h

Résultats observés :
- Classique : 1458 m, 145,8 s
- Trafic : 1494 m, 256,4 s
- Prioritaire : 1458 m, 198,0 s

Ces résultats sont issus d'une simulation.

## 13. Tests restant à effectuer

- Vérifier les sens uniques sur plusieurs trajets.
- Tester le cas départ égal à arrivée.
- Tester les demandes invalides.
- Tester plusieurs heures.
- Vérifier les temps des trois stratégies.
- Tester le projet sur une machine Linux vierge.
- Vérifier la fermeture du client et du serveur.
- Vérifier le comportement en cas de coupure réseau.

## 14. Limites actuelles

- Le trafic est simulé.
- La priorité aux feux est simulée dans le calcul.
- La communication UDP avec les feux reste à développer.
- Les véhicules ne sont pas encore animés.
- Les tests Linux ne sont pas encore validés.
- La fusion définitive avec le travail de David reste à vérifier.

## 15. GitHub

Dépôt :
https://github.com/youssefjabrane/SAE-3.02-Tampere-Emergency

Branche d'intégration :
youssef/strategies-colmar

## 16. Améliorations prévues

- Tester et stabiliser l'application.
- Simplifier et commenter le code.
- Organiser les modules et les classes.
- Ajouter la gestion des feux prioritaires.
- Améliorer la simulation des véhicules.
- Tester le déploiement sur Linux.
- Compléter les tests et la documentation.

## 17. Conclusion

Cette version permet de comparer trois stratégies
d'itinéraire sur une carte de Colmar.

Elle utilise une architecture client-serveur en Python
et une interface graphique PyQt6.

Les prochaines étapes concernent les tests,
le déploiement Linux et la finalisation du projet.
