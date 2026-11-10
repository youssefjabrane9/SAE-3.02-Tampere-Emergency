# SAÉ 3.02 : optimisation du trajet des véhicules prioritaires

Application client / serveur en Python (PyQt6, sockets TCP et UDP) sur le vrai réseau de rues du centre de Colmar.
Pour un trajet d'un véhicule d'urgence à une heure donnée, elle compare 3 itinéraires :

- **classique** : le plus court en distance ;
- **trafic** : le plus rapide compte tenu du trafic à cette heure ;
- **priorité** : comme trafic, mais le véhicule demande le feu vert aux carrefours (V2I, en UDP).

## Démarrage rapide (Linux)

```bash
sudo apt install -y git make python3 python3-venv python3-pip
git clone https://github.com/youssefjabrane9/SAE-3.02-Tampere-Emergency.git
cd SAE-3.02-Tampere-Emergency
make installer
make serveur                      # sur la machine serveur
make client HOTE=<ip du serveur>  # sur la machine client
```

Le guide complet (deux VM, bibliothèques de la VM client, problèmes fréquents) est dans
[docs/installation.md](docs/installation.md).

Auteurs : Youssef Jabrane (ville et serveur), David Duraes Valadares (client et déploiement).
