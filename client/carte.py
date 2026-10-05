"""Carte de la ville : carrefours, routes et trajets (QGraphicsScene / QGraphicsView).

La carte reçoit directement les messages du protocole :
    charger_ville(message)   avec un message de type "CITY"
    afficher_trajet(message) avec un message de type "ROUTE"
Une unité de la scène = 1 mètre.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView

RAYON_CARREFOUR = 8                    # mètres
MARGE = 30                             # mètres autour de la ville
COULEUR_ROUTE = QColor("#b0bec5")
COULEUR_CARREFOUR = QColor("#37474f")
COULEUR_TRAJET = QColor("#1e88e5")

# Ordre d'affichage (le plus grand est dessiné par-dessus)
Z_ROUTE, Z_TRAJET, Z_CARREFOUR = 0, 1, 2


class CarteVille(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.positions = {}        # nom du carrefour -> (x, y) en mètres
        self.items_trajets = []    # lignes des trajets affichés, pour pouvoir les effacer

    def charger_ville(self, message):
        """Dessine la ville à partir d'un message "CITY"."""
        scene = self.scene()
        scene.clear()
        self.items_trajets.clear()
        self.positions = {nom: (x, y) for nom, (x, y) in message["noeuds"].items()}

        stylo_route = QPen(COULEUR_ROUTE, 6)
        for depart, arrivee, _longueur in message["routes"]:
            x1, y1 = self.positions[depart]
            x2, y2 = self.positions[arrivee]
            ligne = scene.addLine(x1, y1, x2, y2, stylo_route)
            ligne.setZValue(Z_ROUTE)

        r = RAYON_CARREFOUR
        for nom, (x, y) in self.positions.items():
            rond = scene.addEllipse(x - r, y - r, 2 * r, 2 * r,
                                    QPen(Qt.PenStyle.NoPen), QBrush(COULEUR_CARREFOUR))
            rond.setZValue(Z_CARREFOUR)
            texte = scene.addSimpleText(nom)
            texte.setPos(x + r, y + r)
            texte.setZValue(Z_CARREFOUR)

        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-MARGE, -MARGE, MARGE, MARGE))
        self.ajuster()

    def afficher_trajet(self, message, couleur=COULEUR_TRAJET):
        """Trace le chemin d'un message "ROUTE" (sans effacer les trajets déjà affichés)."""
        stylo = QPen(couleur, 4)
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

    def ajuster(self):
        """Fait tenir toute la ville dans la fenêtre."""
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ajuster()
