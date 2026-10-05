"""Lance le client.

    python lancer_client.py                    -> serveur sur 127.0.0.1:5050
    python lancer_client.py 192.168.1.20       -> autre machine (ex. la VM ou le conteneur)
"""

import sys

from PyQt6.QtWidgets import QApplication

from client.fenetre import FenetrePrincipale
from client.reseau import ClientReseau
from sae.protocole import PORT_TCP


def main():
    hote = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"

    app = QApplication(sys.argv)
    reseau = ClientReseau(hote, PORT_TCP)
    fenetre = FenetrePrincipale(reseau)
    fenetre.resize(1000, 700)
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
