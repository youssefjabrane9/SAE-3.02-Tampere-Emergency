"""Lance le client.

    python lancer_client.py                    -> serveur sur 127.0.0.1:5050
    python lancer_client.py 192.168.1.20       -> serveur sur une autre machine (ex. la VM serveur)
"""

import sys

from PyQt6.QtWidgets import QApplication

from client.fenetre import FenetrePrincipale
from client.reseau import ClientReseau
from commun.protocole import PORT_TCP


def main():
    """Lance le client : lit l'adresse du serveur, crée la fenêtre et démarre Qt.

    L'adresse est le premier argument de la ligne de commande (127.0.0.1 par défaut).
    """
    hote = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"

    app = QApplication(sys.argv)
    reseau = ClientReseau(hote, PORT_TCP)
    fenetre = FenetrePrincipale(reseau)
    fenetre.showMaximized()            # plein écran : la carte est plus lisible
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
