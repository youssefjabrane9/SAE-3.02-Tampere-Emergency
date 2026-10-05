"""Protocole réseau de l'application (codé sur des sockets brutes, sans framework).

TCP (port 5050) — poste du régulateur <-> centre de régulation
    Une trame = un objet JSON encodé en UTF-8 terminé par '\\n'.
    Requêtes du client : HELLO, GET_CITY, COMPUTE_ROUTES, MISSION_START,
                         MISSION_RESULT, GET_HISTORY
    Réponses / diffusions du serveur : WELCOME, CITY, ROUTES, MISSION_OK,
                         HISTORY, RSU_EVENT, ERROR

UDP (port 5051) — véhicule (OBU) <-> carrefours connectés (RSU), messages V2I
    Un datagramme = un objet JSON.
    Véhicule -> RSU : CAM (balise de position), PRIORITY_REQUEST, PASSED
    RSU -> véhicule : PRIORITY_GRANT, PRIORITY_DENY, PRIORITY_REVOKED
"""

import json

PORT_TCP = 5050
PORT_UDP = 5051
TAILLE_MAX_UDP = 8192
TAILLE_MAX_TRAME = 1_000_000


def encoder(message):
    """dict -> octets (trame TCP)."""
    return (json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def encoder_datagramme(message):
    return json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def decoder_datagramme(octets):
    msg = json.loads(octets.decode("utf-8"))
    if not isinstance(msg, dict) or "type" not in msg:
        raise ValueError("datagramme invalide")
    return msg


class Deframeur:
    """Reconstitue les trames JSON à partir d'un flux TCP (qui peut arriver morcelé)."""

    def __init__(self):
        self._tampon = b""

    def alimenter(self, octets):
        self._tampon += octets
        if len(self._tampon) > TAILLE_MAX_TRAME:
            raise ValueError("trame trop longue")
        messages = []
        while b"\n" in self._tampon:
            ligne, self._tampon = self._tampon.split(b"\n", 1)
            if ligne.strip():
                msg = json.loads(ligne.decode("utf-8"))
                if not isinstance(msg, dict) or "type" not in msg:
                    raise ValueError("trame invalide")
                messages.append(msg)
        return messages
