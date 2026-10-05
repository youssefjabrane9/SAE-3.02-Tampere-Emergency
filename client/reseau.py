"""Connexion TCP du client vers le serveur, dans un thread à part (QThread).

Pourquoi un thread ? recv() attend que des données arrivent : dans le thread de l'IHM,
la fenêtre serait figée pendant ce temps.
Règle : ce thread ne touche JAMAIS à l'IHM. Il émet des signaux, et Qt exécute les
méthodes connectées dans le thread de la fenêtre.
"""

import select
import socket

from PyQt6.QtCore import QThread, pyqtSignal

from sae.protocole import Deframeur, encoder


class ClientReseau(QThread):
    connecte = pyqtSignal()            # la connexion au serveur est établie
    message_recu = pyqtSignal(dict)    # un message complet est arrivé (déjà décodé)
    erreur = pyqtSignal(str)           # problème réseau, avec une phrase pour l'utilisateur

    def __init__(self, hote, port, parent=None):
        super().__init__(parent)
        self.hote = hote
        self.port = port
        self.sock = None
        self.actif = True

    def run(self):
        """Code exécuté dans le thread (lancé par start())."""
        try:
            self.sock = socket.create_connection((self.hote, self.port), timeout=5)
        except OSError as e:
            self.erreur.emit(f"connexion impossible à {self.hote}:{self.port} ({e})")
            return

        self.connecte.emit()
        deframeur = Deframeur()
        try:
            while self.actif:
                # On attend au plus 0,2 s qu'il y ait quelque chose à lire,
                # pour revérifier self.actif régulièrement (arrêt propre).
                lisibles, _, _ = select.select([self.sock], [], [], 0.2)
                if not lisibles:
                    continue
                octets = self.sock.recv(4096)
                if not octets:                 # b"" : le serveur a fermé la connexion
                    self.erreur.emit("le serveur a fermé la connexion")
                    break
                for message in deframeur.alimenter(octets):
                    self.message_recu.emit(message)
        except (OSError, ValueError) as e:     # ValueError : message JSON invalide
            self.erreur.emit(f"erreur réseau ({e})")
        finally:
            self.sock.close()

    def envoyer(self, message):
        """Appelée depuis la fenêtre. Un seul thread écrit, un seul lit : sendall() est sûr ici."""
        if self.sock is None:
            self.erreur.emit("pas encore connecté au serveur")
            return
        try:
            self.sock.sendall(encoder(message))
        except OSError as e:
            self.erreur.emit(f"envoi impossible ({e})")

    def arreter(self):
        """Demande au thread de s'arrêter (il sort de sa boucle en moins de 0,2 s)."""
        self.actif = False
