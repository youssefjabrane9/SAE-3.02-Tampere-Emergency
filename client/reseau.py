"""Communications du client, chacune dans son QThread.

ClientTcp : dialogue avec le centre de régulation (trames JSON sur TCP).
LienV2I   : unité embarquée (OBU) du véhicule connecté, messages V2I en UDP.

Aucune de ces classes ne touche à l'IHM : elles émettent des signaux, que la
fenêtre principale reçoit dans le thread graphique (Signals / Slots de Qt).
"""

import itertools
import queue
import select
import socket

from PyQt6.QtCore import QThread, pyqtSignal

from sae.protocole import TAILLE_MAX_UDP, Deframeur, decoder_datagramme, encoder, encoder_datagramme


class ClientTcp(QThread):
    recu = pyqtSignal(dict)
    connecte = pyqtSignal()
    deconnecte = pyqtSignal(str)

    def __init__(self, hote, port, parent=None):
        super().__init__(parent)
        self.hote = hote
        self.port = port
        self._sortie = queue.Queue()
        self._actif = True

    def envoyer(self, message):
        """Appelable depuis n'importe quel thread."""
        self._sortie.put(message)

    def arreter(self):
        self._actif = False

    def run(self):
        try:
            sock = socket.create_connection((self.hote, self.port), timeout=3)
        except OSError as e:
            self.deconnecte.emit(f"connexion impossible : {e}")
            return
        sock.settimeout(None)
        self.connecte.emit()
        deframeur = Deframeur()
        raison = "déconnexion demandée"
        try:
            while self._actif:
                while not self._sortie.empty():
                    sock.sendall(encoder(self._sortie.get_nowait()))
                prets, _, _ = select.select([sock], [], [], 0.05)
                if prets:
                    donnees = sock.recv(65536)
                    if not donnees:
                        raison = "le serveur a fermé la connexion"
                        break
                    for msg in deframeur.alimenter(donnees):
                        self.recu.emit(msg)
        except (OSError, ValueError) as e:
            raison = str(e)
        finally:
            sock.close()
        self.deconnecte.emit(raison)


class LienV2I(QThread):
    """OBU réseau : envoie CAM / PRIORITY_REQUEST / PASSED et reçoit les réponses des RSU.

    Les méthodes demander / liberer / cam sont appelées par le thread de simulation ;
    les accords reçus sont déposés dans `accords` (file thread-safe) que la simulation lit.
    """

    journal = pyqtSignal(str, dict)     # sens ("->" ou "<-"), message

    def __init__(self, hote, port_udp, parent=None):
        super().__init__(parent)
        self.adresse = (hote, port_udp)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0))
        self.accords = queue.Queue()
        self.mission = None
        self.niveau = 1
        self.nb_envoyes = 0
        self.nb_recus = 0
        self._ids = itertools.count(1)
        self._actif = True

    def arreter(self):
        self._actif = False

    def _envoyer(self, message, journaliser=True):
        message["mission"] = self.mission
        try:
            self.sock.sendto(encoder_datagramme(message), self.adresse)
            self.nb_envoyes += 1
        except OSError as e:
            self.journal.emit("!!", {"type": "ERREUR", "message": str(e)})
            return
        if journaliser:
            self.journal.emit("->", message)

    # --- interface OBU utilisée par sae.simulation.Vehicule
    def demander(self, vehicule, noeud, axe, eta, t):
        self._envoyer({"type": "PRIORITY_REQUEST", "id": next(self._ids), "vehicule": vehicule,
                       "niveau": self.niveau, "noeud": noeud, "axe": axe, "eta": eta, "t": round(t, 2)})

    def liberer(self, vehicule, noeud, t):
        self._envoyer({"type": "PASSED", "vehicule": vehicule, "noeud": noeud, "t": round(t, 2)})

    def cam(self, vehicule, x, y, v, t):
        self._envoyer({"type": "CAM", "vehicule": vehicule, "x": round(x, 1), "y": round(y, 1),
                       "v": round(v, 1), "t": round(t, 2)}, journaliser=False)

    def run(self):
        while self._actif:
            prets, _, _ = select.select([self.sock], [], [], 0.1)
            if not prets:
                continue
            try:
                donnees, _ = self.sock.recvfrom(TAILLE_MAX_UDP)
                msg = decoder_datagramme(donnees)
            except (OSError, ValueError):
                continue
            if msg.get("mission") not in (None, self.mission):
                continue          # réponse d'une mission précédente
            self.nb_recus += 1
            if msg["type"] in ("PRIORITY_GRANT", "PRIORITY_REVOKED"):
                self.accords.put(msg)
            self.journal.emit("<-", msg)
        self.sock.close()
