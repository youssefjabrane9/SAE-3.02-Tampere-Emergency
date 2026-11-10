"""Réseau du client, chaque liaison dans un thread à part (QThread) :
- ClientReseau : TCP vers le serveur (ville, trafic, trajets, historique) ;
- ClientV2I : UDP vers les carrefours, pour demander le feu vert (étape 7).

Pourquoi un thread ? recv() attend que des données arrivent : dans le thread de l'IHM,
la fenêtre serait figée pendant ce temps.
Règle : ce thread ne touche JAMAIS à l'IHM. Il émet des signaux, et Qt exécute les
méthodes connectées dans le thread de la fenêtre.
"""

import json
import select
import socket

from PyQt6.QtCore import QThread, pyqtSignal

from sae.protocole import Deframeur, decoder, encoder


class ClientReseau(QThread):
    connecte = pyqtSignal()            # la connexion au serveur est établie
    message_recu = pyqtSignal(dict)    # un message complet est arrivé (déjà décodé)
    erreur = pyqtSignal(str)           # problème réseau, avec une phrase pour l'utilisateur

    def __init__(self, hote, port):
        super().__init__()
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
            self.erreur.emit("pas connecté au serveur")
            return
        try:
            self.sock.sendall(encoder(message))
        except OSError as e:
            self.erreur.emit(f"envoi impossible ({e})")

    def arreter(self):
        """Demande au thread de s'arrêter (il sort de sa boucle en moins de 0,2 s)."""
        self.actif = False


class ClientV2I(QThread):
    """Liaison UDP entre le véhicule prioritaire et les carrefours (V2I, étape 7).

    Même principe que ClientReseau : un thread qui attend les réponses et les émet en signal.
    Mais en UDP il n'y a ni connexion ni Deframeur : un datagramme = un message JSON entier.
    """
    message_recu = pyqtSignal(dict)    # réponse d'un carrefour (PRIORITY_GRANT / PRIORITY_DENY)

    def __init__(self, hote, port):
        super().__init__()
        self.adresse = (hote, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0))        # port choisi par le système (Windows refuse select() sans bind)
        self.actif = True

    def run(self):
        while self.actif:
            lisibles, _, _ = select.select([self.sock], [], [], 0.2)
            if not lisibles:
                continue
            try:
                octets, _expediteur = self.sock.recvfrom(4096)
                self.message_recu.emit(decoder(octets))
            except ConnectionResetError:
                pass    # Windows : notre envoi précédent n'a trouvé personne sur le port UDP
            except ValueError:
                pass    # datagramme qui n'est pas un message valide : ignoré
        self.sock.close()

    def envoyer(self, message):
        """Envoie un datagramme (sans "\n" : UDP garde les frontières des messages)."""
        try:
            self.sock.sendto(json.dumps(message).encode("utf-8"), self.adresse)
        except OSError:
            pass        # UDP ne garantit rien : un datagramme perdu n'arrête pas l'appli

    def arreter(self):
        self.actif = False
