"""Vérifie, avant "make installer", que ce Python peut faire tourner le projet.

Écrit sans syntaxe récente, pour pouvoir afficher le message même avec un vieux Python.
"""

import sys

MINIMUM = (3, 9)
MAXIMUM = (3, 13)     # matplotlib 3.9.4 (requirements.txt) n'existe pas encore pour Python 3.14

version = "%d.%d" % sys.version_info[:2]

if sys.version_info < MINIMUM:
    sys.exit("ERREUR : Python %s est trop ancien, il faut Python %d.%d ou plus récent.\n"
             "Installez une version plus récente du système (voir docs/erreurs.md)." % ((version,) + MINIMUM))

if sys.version_info[:2] > MAXIMUM:
    sys.exit("ERREUR : Python %s est plus récent que ce que prévoit requirements.txt (%d.%d au plus).\n"
             "Utilisez Debian 11, 12 ou 13, ou Ubuntu 22.04 ou 24.04 (voir docs/erreurs.md)." % ((version,) + MAXIMUM))

try:
    import ensurepip  # noqa: F401  (absent sur Debian/Ubuntu tant que python3-venv n'est pas installé)
    import venv  # noqa: F401
except ImportError:
    sys.exit("ERREUR : le module venv de Python %s n'est pas installé.\n"
             "Faites : sudo apt install -y python3-venv   puis à nouveau : make installer" % version)

print("Python %s : OK" % version)
