"""Lance le client.

    python lancer_client.py                    -> serveur sur 127.0.0.1:5050
    python lancer_client.py 192.168.1.20       -> autre machine (ex. la VM ou le conteneur)
    python lancer_client.py 127.0.0.1 6000     -> autre port
    python lancer_client.py --hors-ligne       -> prototype sans réseau (étape 4)
"""

import sys

from PyQt6.QtWidgets import QApplication

from client.fenetre import FenetrePrincipale
from client.reseau import ClientReseau
from sae.protocole import PORT_TCP


def main():
    arguments = sys.argv[1:]
    hors_ligne = "--hors-ligne" in arguments
    if hors_ligne:
        arguments.remove("--hors-ligne")
    hote = arguments[0] if len(arguments) > 0 else "127.0.0.1"
    port = int(arguments[1]) if len(arguments) > 1 else PORT_TCP

    app = QApplication(sys.argv)
    reseau = None if hors_ligne else ClientReseau(hote, port)
    fenetre = FenetrePrincipale(reseau)
    fenetre.resize(1000, 700)
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
