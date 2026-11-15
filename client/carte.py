"""Carte de la ville : rues, lieux, trajets et véhicules (QGraphicsScene / QGraphicsView).

La fenêtre appelle :
    dessiner_ville(message)      avec un message de type "CITY"
    colorer_trafic(densites)     avec les "densites" d'un message "TRAFFIC"
    dessiner_chemin(chemin, mode)
    animer(trajets)              pour faire rouler les véhicules sur leurs chemins
    accorder_priorite(feu)       quand un carrefour accorde la priorité
Une horloge (QTimer) tourne en permanence : les feux suivent leur cycle vert / rouge.
La carte prévient la fenêtre avec le signal feu_proche quand le véhicule prioritaire
approche d'un feu : c'est la fenêtre qui envoie la demande en UDP.
Une unité de la scène = 1 mètre.
"""

import math
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView

# Fond de carte OpenStreetMap : son coin haut-gauche est le point (0, 0) de la ville
IMAGE_FOND = Path(__file__).parent.parent / "assets" / "colmar.png"
LARGEUR_FOND = 2579                    # mètres couverts par l'image, d'ouest en est

# Tailles en mètres : la carte fait 2,6 km de large, il faut voir les éléments en entier
EPAISSEUR_ROUTE = 9
RAYON_LIEU = 20
RAYON_MARQUEUR = 28
RAYON_VEHICULE = 24
RAYON_FEU = 13
TAILLE_TEXTE = 34

# Les lieux dont le nom est écrit sur la carte (les autres ont seulement leur rond).
# Le théâtre n'y est pas : il est collé au musée Unterlinden, les deux noms se chevaucheraient.
NOMS_SUR_CARTE = ["Hôpital Pasteur", "Commissariat de police", "Gare de Colmar",
                  "Musée Unterlinden", "Petite Venise", "Champ de Mars"]

# Les 3 stratégies : nom affiché, couleur ("#rrggbb", compris par Qt ET par matplotlib)
# et épaisseur du trait (de plus en plus fin : quand les chemins se superposent, on voit les 3).
# Pas de vert, orange ni rouge : ces couleurs servent au trafic.
MODES = ["classique", "trafic", "priorite"]
NOMS_MODE = {"classique": "Classique", "trafic": "Trafic", "priorite": "Priorité feux"}
COULEURS_MODE = {"classique": "#212121", "trafic": "#8e24aa", "priorite": "#1e88e5"}
EPAISSEURS_MODE = {"classique": 26, "trafic": 16, "priorite": 7}
COULEURS_MARQUEUR = {"depart": "#2e7d32", "arrivee": "#d81b60"}       # vert, rose

# Animation : toutes les 40 ms, on avance de 40 ms x 20 = 0,8 s de temps simulé
PERIODE_MS = 40
ACCELERATION = 20
ANTICIPATION = 10      # le véhicule prioritaire demande le feu vert 10 s (simulées) avant d'y être

# Feux : chaque feu fait 30 s vert puis 30 s rouge (affichage de la carte)
CYCLE_FEU = 60
DUREE_VERT = 30

# Ordre d'affichage : le plus grand est dessiné par-dessus
Z_FOND, Z_ROUTE, Z_TRAJET, Z_FEU, Z_LIEU, Z_MARQUEUR, Z_VEHICULE = -1, 0, 1, 2, 3, 4, 5


def en_minutes(secondes):
    """Écrit une durée en minutes et secondes, par exemple 336.7 -> "5 min 37 s".

    Args:
        secondes (float): la durée en secondes (unité du protocole).

    Returns:
        str: la durée lisible.
    """
    minutes, reste = divmod(round(secondes), 60)
    return f"{minutes} min {reste:02d} s"


def feu_vert(feu, t):
    """Dit si un feu est vert à un instant donné.

    Le cycle est décalé selon l'identifiant du feu, pour que les feux ne changent pas tous
    en même temps. Ce cycle sert seulement à l'affichage : le serveur, lui, compte une attente
    fixe à chaque feu (20 s, ou 3 s pour le véhicule prioritaire).

    Args:
        feu (str): identifiant du noeud du feu.
        t (float): instant en secondes simulées.

    Returns:
        bool: True si le feu est vert.
    """
    return (t + int(feu)) % CYCLE_FEU < DUREE_VERT


def stylo(couleur, epaisseur):
    """Crée un crayon pour tracer une ligne aux bouts arrondis (pas de "trous" dans les virages).

    Args:
        couleur (str | QColor): couleur du trait.
        epaisseur (float): épaisseur du trait, en mètres.

    Returns:
        QPen: le crayon.
    """
    crayon = QPen(QColor(couleur), epaisseur)
    crayon.setCapStyle(Qt.PenCapStyle.RoundCap)
    return crayon


class Carte(QGraphicsView):
    """Vue de la ville : rues, lieux, feux, trajets et véhicules animés.

    Une unité de la scène = 1 mètre. Une horloge (QTimer) fait tourner les feux et avancer
    les véhicules.

    Attributes:
        noeud_clique (pyqtSignal(str)): émis au clic, avec le noeud le plus proche du clic.
        feu_proche (pyqtSignal(str)): émis quand le véhicule prioritaire approche d'un feu.
        positions (dict[str, list[float]]): noeud -> [x, y] en mètres.
        t (float): horloge de la ville, en secondes simulées.
    """
    noeud_clique = pyqtSignal(str)     # clic sur la carte : le noeud le plus proche
    feu_proche = pyqtSignal(str)       # le véhicule prioritaire approche de ce feu

    def __init__(self):
        """Crée une scène vide et l'horloge des feux (démarrée par dessiner_ville())."""
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.positions = {}        # identifiant du noeud -> (x, y) en mètres
        self.lignes_routes = {}    # (noeud a, noeud b) -> ligne de la route, pour le trafic
        self.lignes_trajets = []   # lignes des trajets affichés, pour pouvoir les effacer
        self.marqueurs = {}        # "depart" / "arrivee" -> rond affiché sur la carte
        self.vehicules = []        # (mode, rond, chemin, temps_noeuds) pour l'animation
        self.feux = {}             # identifiant du noeud -> rond du feu sur la carte
        self.feux_demandes = set() # feux pour lesquels on a déjà demandé la priorité
        self.feux_forces = set()   # feux ouverts pour le véhicule prioritaire (halo bleu)
        self.t = 0                 # horloge de la ville (temps simulé, en secondes)
        self.minuterie = QTimer(self)
        self.minuterie.timeout.connect(self.avancer)

    def rond(self, x, y, rayon, couleur, z):
        """Ajoute un rond coloré à bord blanc, centré sur (x, y).

        Args:
            x (float): abscisse du centre, en mètres.
            y (float): ordonnée du centre, en mètres.
            rayon (float): rayon en mètres.
            couleur (str): couleur de remplissage.
            z (int): ordre d'affichage (le plus grand est dessiné par-dessus).

        Returns:
            QGraphicsEllipseItem: le rond ajouté à la scène.
        """
        item = self.scene().addEllipse(x - rayon, y - rayon, 2 * rayon, 2 * rayon,
                                       QPen(Qt.GlobalColor.white, 6), QBrush(QColor(couleur)))
        item.setZValue(z)
        return item

    def ligne(self, a, b, crayon, z):
        """Ajoute une ligne entre deux noeuds.

        Args:
            a (str): noeud de départ.
            b (str): noeud d'arrivée.
            crayon (QPen): couleur et épaisseur du trait.
            z (int): ordre d'affichage.

        Returns:
            QGraphicsLineItem: la ligne ajoutée à la scène.
        """
        x1, y1 = self.positions[a]
        x2, y2 = self.positions[b]
        item = self.scene().addLine(x1, y1, x2, y2, crayon)
        item.setZValue(z)
        return item

    # --- La ville ---

    def dessiner_ville(self, message):
        """Dessine la ville (fond de carte, rues, feux, lieux) et démarre l'horloge des feux.

        Args:
            message (dict): message "CITY" du serveur, avec "noeuds", "routes", "lieux" et "feux".
        """
        self.positions = message["noeuds"]

        fond = self.scene().addPixmap(QPixmap(str(IMAGE_FOND)))
        fond.setScale(LARGEUR_FOND / fond.pixmap().width())       # pixels -> mètres
        fond.setZValue(Z_FOND)

        gris = QColor(84, 110, 122, 120)       # gris-bleu transparent : on voit la carte dessous
        for a, b, _longueur in message["routes"]:
            self.lignes_routes[(a, b)] = self.ligne(a, b, stylo(gris, EPAISSEUR_ROUTE), Z_ROUTE)

        # Les vrais feux de Colmar
        for noeud in message["feux"]:
            x, y = self.positions[noeud]
            self.feux[noeud] = self.rond(x, y, RAYON_FEU, "red", Z_FEU)
        self.minuterie.start(PERIODE_MS)       # l'horloge tourne : les feux changent de couleur

        # Seuls les lieux ont un rond (pas les milliers de points des rues)
        police = QFont()
        police.setPixelSize(TAILLE_TEXTE)
        police.setBold(True)
        for nom, noeud in message["lieux"].items():
            x, y = self.positions[noeud]
            self.rond(x, y, RAYON_LIEU, "#c62828", Z_LIEU)
            if nom in NOMS_SUR_CARTE:
                texte = self.scene().addSimpleText(nom, police)
                texte.setPos(x + RAYON_LIEU, y + RAYON_LIEU)
                texte.setZValue(Z_LIEU)

        self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def colorer_trafic(self, densites):
        """Colore chaque route selon son trafic : vert (fluide), orange (chargé), rouge (bouché).

        Args:
            densites (list[list]): [[a, b, densité de 0 à 1], ...], champ "densites" du message "TRAFFIC".
        """
        for a, b, densite in densites:
            if densite < 0.3:
                couleur = QColor(46, 125, 50, 170)     # vert : fluide
            elif densite < 0.6:
                couleur = QColor(245, 124, 0, 190)     # orange : chargé
            else:
                couleur = QColor(211, 47, 47, 210)     # rouge : bouché
            self.lignes_routes[(a, b)].setPen(stylo(couleur, EPAISSEUR_ROUTE))

    def resizeEvent(self, event):
        """Refait tenir toute la ville dans la vue quand la fenêtre change de taille.

        Args:
            event (QResizeEvent): événement envoyé par Qt.
        """
        super().resizeEvent(event)
        self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # --- Trajets et véhicules ---

    def dessiner_chemin(self, chemin, mode):
        """Trace un chemin avec la couleur et l'épaisseur de sa stratégie.

        Args:
            chemin (list[str]): les noeuds du trajet, dans l'ordre.
            mode (str): "classique", "trafic" ou "priorite".
        """
        crayon = stylo(COULEURS_MODE[mode], EPAISSEURS_MODE[mode])
        for a, b in zip(chemin, chemin[1:]):
            self.lignes_trajets.append(self.ligne(a, b, crayon, Z_TRAJET))

    def effacer_trajets(self):
        """Enlève les chemins et les véhicules ; les feux reprennent leur cycle normal."""
        for ligne in self.lignes_trajets:
            self.scene().removeItem(ligne)
        for mode, rond, chemin, temps_noeuds in self.vehicules:
            self.scene().removeItem(rond)
        self.lignes_trajets.clear()
        self.vehicules.clear()
        self.feux_demandes.clear()
        self.feux_forces.clear()

    def accorder_priorite(self, feu):
        """Ouvre un feu pour le véhicule prioritaire seulement, jusqu'à son passage (halo bleu).

        Args:
            feu (str): identifiant du feu, reçu dans PRIORITY_GRANT.
        """
        if feu in self.feux:
            self.feux_forces.add(feu)

    def animer(self, trajets):
        """Fait rouler un véhicule par trajet, en repartant de l'instant 0.

        Args:
            trajets (dict[str, tuple]): {mode: (chemin, temps_noeuds)}. temps_noeuds[i] vaut
                [arrivée, départ] au noeud chemin[i], en secondes ; les deux diffèrent seulement
                à un feu rouge.
        """
        for mode, (chemin, temps_noeuds) in trajets.items():
            # Rond dessiné autour de (0, 0) : setPos(x, y) le déplace ensuite en (x, y)
            rond = self.rond(0, 0, RAYON_VEHICULE, COULEURS_MODE[mode], Z_VEHICULE)
            x, y = self.positions[chemin[0]]
            rond.setPos(x, y)
            self.vehicules.append((mode, rond, chemin, temps_noeuds))
        self.t = 0

    def position(self, chemin, temps_noeuds, t):
        """Calcule où se trouve un véhicule à l'instant t.

        En route vers le noeud i, il est placé sur le segment à la bonne proportion ;
        entre l'arrivée et le départ du noeud i, il attend au feu rouge.

        Args:
            chemin (list[str]): les noeuds du trajet.
            temps_noeuds (list[list[float]]): [arrivée, départ] pour chaque noeud.
            t (float): instant en secondes simulées.

        Returns:
            tuple[float, float]: la position (x, y) en mètres.
        """
        for i in range(1, len(chemin)):
            t1 = temps_noeuds[i - 1][1]                 # départ du noeud précédent
            arrivee, depart = temps_noeuds[i]
            if t < arrivee:
                x1, y1 = self.positions[chemin[i - 1]]
                x2, y2 = self.positions[chemin[i]]
                k = (t - t1) / (arrivee - t1)
                return x1 + k * (x2 - x1), y1 + k * (y2 - y1)
            if t < depart:
                return self.positions[chemin[i]]        # arrêté au feu rouge
        return self.positions[chemin[-1]]               # t dépasse la fin : il est arrivé

    def chercher_feux(self, chemin, temps_noeuds):
        """Gère les feux du véhicule prioritaire.

        Émet feu_proche quand il arrive à un feu dans moins de ANTICIPATION secondes
        (une seule demande par feu), et rend le feu à son cycle normal une fois passé.

        Args:
            chemin (list[str]): les noeuds du trajet prioritaire.
            temps_noeuds (list[list[float]]): [arrivée, départ] pour chaque noeud.
        """
        for noeud, (arrivee, depart) in zip(chemin, temps_noeuds):
            if noeud not in self.feux:
                continue
            if noeud not in self.feux_demandes and 0 <= arrivee - self.t <= ANTICIPATION:
                self.feux_demandes.add(noeud)           # une seule demande par feu
                self.feu_proche.emit(noeud)
            if depart < self.t:
                self.feux_forces.discard(noeud)         # véhicule passé : cycle normal

    def avancer(self):
        """Appelée par l'horloge : avance le temps, colore les feux et déplace les véhicules."""
        self.t += PERIODE_MS / 1000 * ACCELERATION
        for feu, rond in self.feux.items():
            # Couleur = cycle normal, pour TOUS les véhicules (même pendant la priorité)
            rond.setBrush(QColor("#00c853" if feu_vert(feu, self.t) else "red"))
            # Priorité accordée : halo bleu (couleur du prioritaire) = ouvert pour LUI seulement
            if feu in self.feux_forces:
                rond.setPen(QPen(QColor(COULEURS_MODE["priorite"]), 12))
            else:
                rond.setPen(QPen(Qt.GlobalColor.white, 6))
        # Un véhicule arrivé reste à la fin de son chemin (position() le place là)
        for mode, rond, chemin, temps_noeuds in self.vehicules:
            x, y = self.position(chemin, temps_noeuds, self.t)
            rond.setPos(x, y)
            if mode == "priorite":
                self.chercher_feux(chemin, temps_noeuds)

    # --- Départ / arrivée ---

    def marquer(self, role, noeud):
        """Place, déplace ou enlève le marqueur de départ ou d'arrivée.

        Args:
            role (str): "depart" ou "arrivee".
            noeud (str | None): noeud où placer le marqueur ; None l'enlève.
        """
        if role in self.marqueurs:
            self.scene().removeItem(self.marqueurs.pop(role))
        if noeud is not None:
            x, y = self.positions[noeud]
            self.marqueurs[role] = self.rond(x, y, RAYON_MARQUEUR, COULEURS_MARQUEUR[role], Z_MARQUEUR)

    def mousePressEvent(self, event):
        """Clic sur la carte : émet noeud_clique avec le noeud le plus proche du clic.

        Args:
            event (QMouseEvent): événement envoyé par Qt (position en pixels de l'écran).
        """
        if not self.positions:
            return                                  # la ville n'est pas encore chargée
        point = self.mapToScene(event.position().toPoint())    # pixels de l'écran -> mètres
        plus_proche = None
        distance_min = None
        for noeud, (x, y) in self.positions.items():
            distance = math.dist((x, y), (point.x(), point.y()))
            if distance_min is None or distance < distance_min:
                plus_proche = noeud
                distance_min = distance
        self.noeud_clique.emit(plus_proche)
