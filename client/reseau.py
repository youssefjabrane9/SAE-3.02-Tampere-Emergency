"""Réseau du client, chaque liaison dans un thread à part (QThread) :
- ClientReseau : TCP vers le serveur (ville, trafic, trajets, historique) ;
- ClientV2I : UDP vers les carrefours, pour demander le feu vert.

Pourquoi un thread ? recv() attend que des données arrivent : dans le thread de l'IHM,
la fenêtre serait figée pendant ce temps.
Règle : ce thread ne touche JAMAIS à l'IHM. Il émet des signaux, et Qt exécute les
méthodes connectées dans le thread de la fenêtre.
"""

import json
import select
import socket

from PyQt6.QtCore import QThread, pyqtSignal

from commun.protocole import Deframeur, decoder, encoder


class ClientReseau(QThread):
    """Liaison TCP entre le client et le serveur, dans un thread à part (QThread).

    Le thread ne touche jamais à l'IHM : il émet des signaux, que Qt exécute dans le thread
    de la fenêtre.

    Attributes:
        connecte (pyqtSignal): émis quand la connexion au serveur est établie.
        message_recu (pyqtSignal(dict)): émis pour chaque message complet reçu, déjà décodé.
        erreur (pyqtSignal(str)): émis en cas de problème réseau, avec une phrase pour l'utilisateur.
        hote (str): adresse IP ou nom du serveur.
        port (int): port TCP du serveur.
    """
    connecte = pyqtSignal()            # la connexion au serveur est établie
    message_recu = pyqtSignal(dict)    # un message complet est arrivé (déjà décodé)
    erreur = pyqtSignal(str)           # problème réseau, avec une phrase pour l'utilisateur

    def __init__(self, hote, port):
        """Prépare la liaison, sans se connecter (la connexion se fait dans run()).

        Args:
            hote (str): adresse IP ou nom du serveur, par exemple "192.168.56.10".
            port (int): port TCP du serveur (PORT_TCP).
        """
        super().__init__()
        self.hote = hote
        self.port = port
        self.sock = None
        self.actif = True

    def run(self):
        """Code du thread, lancé par start() : se connecte puis lit les messages jusqu'à l'arrêt.

        select() attend au plus 0,2 s, pour revérifier régulièrement si arreter() a été appelée.
        """
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
        """Envoie un message au serveur (appelée depuis la fenêtre).

        Un seul thread écrit et un seul lit : sendall() est sûr ici.

        Args:
            message (dict): message du protocole, par exemple {"type": "GET_CITY"}.
        """
        if self.sock is None:
            self.erreur.emit("pas connecté au serveur")
            return
        try:
            self.sock.sendall(encoder(message))
        except OSError as e:
            self.erreur.emit(f"envoi impossible ({e})")

    def arreter(self):
        """Demande au thread de s'arrêter : il sort de sa boucle en moins de 0,2 s."""
        self.actif = False


class ClientV2I(QThread):
    """Liaison UDP entre le véhicule prioritaire et les carrefours (V2I).

    Même principe que ClientReseau : un thread attend les réponses et les émet en signal.
    En UDP, il n'y a ni connexion ni Deframeur : un datagramme = un message JSON entier.

    Attributes:
        message_recu (pyqtSignal(dict)): réponse d'un carrefour (PRIORITY_GRANT ou PRIORITY_DENY).
        adresse (tuple[str, int]): adresse et port UDP des carrefours.
    """
    message_recu = pyqtSignal(dict)    # réponse d'un carrefour (PRIORITY_GRANT / PRIORITY_DENY)

    def __init__(self, hote, port):
        """Crée la socket UDP, liée à un port choisi par le système.

        Args:
            hote (str): adresse des carrefours (la machine du serveur).
            port (int): port UDP des carrefours (PORT_UDP).
        """
        super().__init__()
        self.adresse = (hote, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0))        # port choisi par le système (Windows refuse select() sans bind)
        self.actif = True

    def run(self):
        """Code du thread : attend les réponses des carrefours et les émet, jusqu'à l'arrêt."""
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
        """Envoie un datagramme aux carrefours (sans '\\n' : UDP garde les frontières des messages).

        Un datagramme perdu n'arrête pas l'application : UDP ne garantit rien.

        Args:
            message (dict): par exemple {"type": "PRIORITY_REQUEST", "feu": "123"}.
        """
        try:
            self.sock.sendto(json.dumps(message).encode("utf-8"), self.adresse)
        except OSError:
            pass        # UDP ne garantit rien : un datagramme perdu n'arrête pas l'appli

    def arreter(self):
        """Demande au thread de s'arrêter : il sort de sa boucle en moins de 0,2 s."""
        self.actif = False
