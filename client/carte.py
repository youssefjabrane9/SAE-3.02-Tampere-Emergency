"""Carte de la ville : rues, lieux et trajets (QGraphicsScene / QGraphicsView).

La carte reçoit directement les messages du protocole :
    charger_ville(message)   avec un message de type "CITY"
    afficher_trajet(message) avec un message de type "ROUTE"
Une unité de la scène = 1 mètre.
"""

from pathlib import Path

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView

# Tailles en mètres : la carte fait 2,6 km de large, il faut voir les éléments en entier
RAYON_LIEU = 20
EPAISSEUR_ROUTE = 5
EPAISSEUR_TRAJET = 14
TAILLE_TEXTE = 34
MARGE = 30                             # mètres autour de la ville
COULEUR_ROUTE = QColor(84, 110, 122, 120)     # gris-bleu transparent : on voit la carte dessous
COULEUR_LIEU = QColor("#c62828")
COULEUR_FOND_TEXTE = QColor(255, 255, 255, 210)
COULEUR_TRAJET = QColor("#1e88e5")
COULEURS_MARQUEUR = {"depart": QColor("#2e7d32"), "arrivee": QColor("#6a1b9a")}  # vert, violet
RAYON_MARQUEUR = 28

# Fond de carte OpenStreetMap : son coin haut-gauche est le point (0, 0) de la ville
IMAGE_FOND = Path(__file__).parent.parent / "assets" / "colmar.png"
LARGEUR_FOND = 2579                    # mètres couverts par l'image, d'ouest en est

# Ordre d'affichage (le plus grand est dessiné par-dessus)
Z_FOND, Z_ROUTE, Z_TRAJET, Z_LIEU, Z_MARQUEUR = -1, 0, 1, 2, 3


class CarteVille(QGraphicsView):
    # Clic sur la carte : (noeud le plus proche, "depart" pour clic gauche / "arrivee" pour clic droit)
    noeud_clique = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.positions = {}        # identifiant du noeud -> (x, y) en mètres
        self.items_trajets = []    # lignes des trajets affichés, pour pouvoir les effacer
        self.marqueurs = {}        # "depart" / "arrivee" -> rond affiché sur la carte

    def charger_ville(self, message):
        """Dessine la ville à partir d'un message "CITY"."""
        scene = self.scene()
        scene.clear()
        self.items_trajets.clear()
        self.marqueurs.clear()
        self.positions = {nom: (x, y) for nom, (x, y) in message["noeuds"].items()}

        fond = scene.addPixmap(QPixmap(str(IMAGE_FOND)))
        fond.setScale(LARGEUR_FOND / fond.pixmap().width())   # pixels -> mètres
        fond.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        fond.setZValue(Z_FOND)

        stylo_route = QPen(COULEUR_ROUTE, EPAISSEUR_ROUTE)
        stylo_route.setCapStyle(Qt.PenCapStyle.RoundCap)    # pas de "trous" dans les virages
        for depart, arrivee, _longueur in message["routes"]:
            x1, y1 = self.positions[depart]
            x2, y2 = self.positions[arrivee]
            ligne = scene.addLine(x1, y1, x2, y2, stylo_route)
            ligne.setZValue(Z_ROUTE)

        # Seuls les lieux ont un marqueur et un nom (pas les milliers de points des rues)
        r = RAYON_LIEU
        police = QFont()
        police.setPixelSize(TAILLE_TEXTE)
        police.setBold(True)
        for nom, noeud in message.get("lieux", {}).items():
            x, y = self.positions[noeud]
            rond = scene.addEllipse(x - r, y - r, 2 * r, 2 * r,
                                    QPen(Qt.GlobalColor.white, 5), QBrush(COULEUR_LIEU))
            rond.setZValue(Z_LIEU)
            texte = scene.addSimpleText(nom, police)
            texte.setPos(x + r, y + r)
            texte.setZValue(Z_LIEU)
            fond_texte = scene.addRect(texte.sceneBoundingRect(),
                                       QPen(Qt.PenStyle.NoPen), QBrush(COULEUR_FOND_TEXTE))
            fond_texte.setZValue(Z_LIEU - 0.5)              # juste sous le texte

        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-MARGE, -MARGE, MARGE, MARGE))
        self.ajuster()

    def afficher_trajet(self, message, couleur=COULEUR_TRAJET):
        """Trace le chemin d'un message "ROUTE" (sans effacer les trajets déjà affichés)."""
        stylo = QPen(couleur, EPAISSEUR_TRAJET)
        stylo.setCapStyle(Qt.PenCapStyle.RoundCap)
        chemin = message["chemin"]
        for a, b in zip(chemin, chemin[1:]):
            x1, y1 = self.positions[a]
            x2, y2 = self.positions[b]
            ligne = self.scene().addLine(x1, y1, x2, y2, stylo)
            ligne.setZValue(Z_TRAJET)
            self.items_trajets.append(ligne)

    def effacer_trajets(self):
        for ligne in self.items_trajets:
            self.scene().removeItem(ligne)
        self.items_trajets.clear()

    def marquer(self, role, noeud):
        """Place (ou déplace) le marqueur "depart" ou "arrivee" sur un noeud."""
        if role in self.marqueurs:
            self.scene().removeItem(self.marqueurs.pop(role))
        if noeud not in self.positions:
            return
        x, y = self.positions[noeud]
        r = RAYON_MARQUEUR
        rond = self.scene().addEllipse(x - r, y - r, 2 * r, 2 * r,
                                       QPen(Qt.GlobalColor.white, 8), QBrush(COULEURS_MARQUEUR[role]))
        rond.setZValue(Z_MARQUEUR)
        self.marqueurs[role] = rond

    def noeud_le_plus_proche(self, x, y):
        return min(self.positions, key=lambda n: math.hypot(self.positions[n][0] - x,
                                                            self.positions[n][1] - y))

    def mousePressEvent(self, event):
        """Clic gauche : départ, clic droit : arrivée (au point de rue le plus proche)."""
        super().mousePressEvent(event)
        if not self.positions:
            return
        point = self.mapToScene(event.position().toPoint())    # pixels de l'écran -> mètres
        role = "arrivee" if event.button() == Qt.MouseButton.RightButton else "depart"
        self.noeud_clique.emit(self.noeud_le_plus_proche(point.x(), point.y()), role)

    def ajuster(self):
        """Fait tenir toute la ville dans la fenêtre."""
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ajuster()
