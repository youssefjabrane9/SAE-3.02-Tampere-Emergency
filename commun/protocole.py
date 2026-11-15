"""Protocole réseau commun au client (poste du régulateur) et au serveur (centre de régulation).

CE FICHIER EST LE CONTRAT ENTRE LES DEUX MOITIÉS DU PROJET.
Personne ne le modifie seul : tout changement passe par une pull request relue par l'autre.

Règles de transport
-------------------
TCP (PORT_TCP) : client <-> serveur.
    Une trame = un objet JSON (un dict) encodé en UTF-8, suivi de '\\n'.
    Pourquoi le '\\n' ? TCP est un flux d'octets : un recv() peut renvoyer
    un demi-message, ou deux messages collés. Le '\\n' marque la fin de chaque message.

UDP (PORT_UDP) : véhicule (OBU) <-> carrefour connecté (RSU).
    Un datagramme = un objet JSON. Pas besoin de '\\n' : UDP garde les frontières des messages.

Tout message est un dict qui contient au moins la clé "type".
"""

import json

PORT_TCP = 5050
PORT_UDP = 5051


# ---------------------------------------------------------------------------
# Catalogue des messages (un exemple réel par message).
# Si vous ajoutez un champ, ajoutez-le ici D'ABORD, puis dans le code.
# ---------------------------------------------------------------------------

# Les premiers messages du contrat : la carte et un itinéraire ---------------

EXEMPLE_GET_CITY = {"type": "GET_CITY"}                          # client -> serveur

EXEMPLE_CITY = {                                                  # serveur -> client
    "type": "CITY",
    "noeuds": {"A1": [0, 0], "A2": [0, 100], "B1": [100, 0], "B2": [100, 100]},  # nom -> [x, y] en mètres
    "routes": [["A1", "A2", 100], ["A1", "B1", 100], ["A2", "B2", 100], ["B1", "B2", 100]],  # [départ, arrivée, longueur]
}

EXEMPLE_COMPUTE_ROUTE = {                                         # client -> serveur
    "type": "COMPUTE_ROUTE",
    "depart": "A1",
    "arrivee": "B2",
    "heure": 8,              # 0 à 23
}

EXEMPLE_ROUTE = {                                                 # serveur -> client (premier prototype)
    "type": "ROUTE",
    "chemin": ["A1", "A2", "B2"],
    "distance": 200,         # mètres
    "temps": 24.0,           # secondes estimées
}

EXEMPLE_ERROR = {"type": "ERROR", "raison": "noeud inconnu : Z9"}  # serveur -> client

# Messages ajoutés ensuite (utilisés par le code, pas encore dans TYPES_CONNUS) :
#   TCP : ROUTES remplace ROUTE : {"type": "ROUTES", "classique": {...}, "trafic": {...}, "priorite": {...}}
#         GET_TRAFFIC / TRAFFIC (densité de chaque route à une heure), GET_HISTORY / HISTORY (historique SQLite)
#   UDP : PRIORITY_REQUEST (véhicule -> carrefour), PRIORITY_GRANT / PRIORITY_DENY (carrefour -> véhicule)

TYPES_CONNUS = {"GET_CITY", "CITY", "COMPUTE_ROUTE", "ROUTE", "ERROR"}


# ---------------------------------------------------------------------------
# Encodage, décodage et découpage des trames.
# ---------------------------------------------------------------------------

def encoder(message):
    """Transforme un message en octets prêts à envoyer en TCP.

    Le message est écrit en JSON, suivi de '\\n' (fin de trame), puis encodé en UTF-8.

    Args:
        message (dict): message du protocole, avec au moins la clé "type".

    Returns:
        bytes: la trame à passer à sendall().
    """
    return (json.dumps(message) + "\n").encode("utf-8")


def decoder(ligne):
    """Transforme UNE trame reçue (sans son '\\n') en message.

    Args:
        ligne (bytes): les octets d'une trame, ou d'un datagramme UDP.

    Returns:
        dict: le message décodé.

    Raises:
        ValueError: si ce n'est pas du JSON, pas un dict, ou s'il manque la clé "type".
    """
    message = json.loads(ligne.decode("utf-8"))
    if not isinstance(message, dict) or "type" not in message:
        raise ValueError("message invalide : il faut un dict avec une clé \"type\"")
    return message


class Deframeur:
    """Reconstitue les messages à partir des morceaux reçus par recv().

    TCP est un flux : un recv() peut renvoyer un demi-message ou deux messages collés.
    On garde donc un tampon, et on ne rend que les messages complets (finis par '\\n').
    Un Deframeur par connexion, côté client comme côté serveur::

        d = Deframeur()
        for msg in d.alimenter(sock.recv(4096)):
            traiter(msg)

    Attributes:
        tampon (bytes): octets reçus qui ne forment pas encore un message complet.
    """

    def __init__(self):
        """Crée un déframeur avec un tampon vide."""
        self.tampon = b""

    def alimenter(self, octets):
        """Ajoute les octets reçus au tampon et renvoie les messages complets.

        Ce qui reste après le dernier '\\n' (un message pas encore fini) reste dans le tampon
        pour le prochain appel.

        Args:
            octets (bytes): ce que recv() vient de renvoyer.

        Returns:
            list[dict]: les messages complets, dans l'ordre d'arrivée (liste vide s'il n'y en a pas).

        Raises:
            ValueError: si une trame complète n'est pas un message valide (voir decoder()).
        """
        self.tampon += octets
        messages = []
        while b"\n" in self.tampon:
            ligne, self.tampon = self.tampon.split(b"\n", 1)
            messages.append(decoder(ligne))
        return messages
