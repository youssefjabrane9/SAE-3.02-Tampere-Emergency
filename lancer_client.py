"""Lance le poste du régulateur (interface PyQt6).

    python lancer_client.py [--hote 127.0.0.1] [--port 5050]
"""

import argparse
import sys

from PyQt6.QtWidgets import QApplication

from client.fenetre import FenetrePrincipale
from sae.protocole import PORT_TCP


def main():
    p = argparse.ArgumentParser(description="Poste du régulateur SAE 3.02")
    p.add_argument("--hote", default="127.0.0.1")
    p.add_argument("--port", type=int, default=PORT_TCP)
    p.add_argument("--pas-de-connexion-auto", action="store_true")
    a = p.parse_args()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    fenetre = FenetrePrincipale(a.hote, a.port)
    fenetre.show()
    if not a.pas_de_connexion_auto:
        fenetre.connecter()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
