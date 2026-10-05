"""Petits graphiques dessinés avec QPainter (pas de dépendance supplémentaire)."""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from .carte import COULEURS_MODE

LIBELLES_COURTS = {"classique": "Classique", "trafic": "Trafic", "priorite": "Priorité feux"}
TEXTE = QColor("#263238")
GRILLE = QColor("#dde3e8")


def format_temps(s):
    if s is None:
        return "–"
    s = int(round(s))
    return f"{s // 60} min {s % 60:02d} s"


class GraphiqueBarres(QWidget):
    """Temps de trajet des trois stratégies (barres horizontales)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.valeurs = {}
        self.setMinimumHeight(110)

    def definir(self, valeurs):
        self.valeurs = {k: v for k, v in valeurs.items() if v is not None}
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = QFont()
        f.setPixelSize(12)
        p.setFont(f)
        if not self.valeurs:
            p.setPen(QColor("#90a4ae"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Lancez une mission pour comparer les temps")
            return
        maxi = max(self.valeurs.values()) or 1
        largeur = self.width() - 190
        h = (self.height() - 10) / 3
        for i, mode in enumerate(("classique", "trafic", "priorite")):
            y = 5 + i * h
            p.setPen(TEXTE)
            p.drawText(QRectF(0, y, 84, h), Qt.AlignmentFlag.AlignVCenter, LIBELLES_COURTS[mode])
            v = self.valeurs.get(mode)
            if v is None:
                continue
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(COULEURS_MODE[mode])
            p.drawRoundedRect(QRectF(86, y + h * 0.2, max(2.0, largeur * v / maxi), h * 0.6), 4, 4)
            p.setPen(TEXTE)
            p.drawText(QRectF(92 + largeur * v / maxi, y, 95, h), Qt.AlignmentFlag.AlignVCenter, format_temps(v))


class GraphiqueHoraire(QWidget):
    """Temps de trajet en fonction de l'heure de la journée (0 h – 23 h)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.setMinimumHeight(200)

    def definir(self, points):
        self.points = points
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = QFont()
        f.setPixelSize(11)
        p.setFont(f)
        g, d, hh, b = 52, 16, 14, 28
        zone = QRectF(g, hh, self.width() - g - d, self.height() - hh - b)
        if not self.points:
            p.setPen(QColor("#90a4ae"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Choisissez un départ et une arrivée puis lancez l'analyse sur 24 h")
            return
        maxi = max(v for pt in self.points for k, v in pt.items() if k != "heure" and v) * 1.1
        # grille
        p.setPen(QPen(GRILLE, 1))
        for k in range(5):
            y = zone.bottom() - zone.height() * k / 4
            p.drawLine(QPointF(zone.left(), y), QPointF(zone.right(), y))
            p.setPen(TEXTE)
            p.drawText(QRectF(0, y - 8, g - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{maxi * k / 4 / 60:.1f} min")
            p.setPen(QPen(GRILLE, 1))
        p.setPen(TEXTE)
        for h in range(0, 24, 3):
            x = zone.left() + zone.width() * h / 23
            p.drawText(QRectF(x - 20, zone.bottom() + 4, 40, 16), Qt.AlignmentFlag.AlignCenter, f"{h} h")
        for mode in ("classique", "trafic", "priorite"):
            poly = QPolygonF([QPointF(zone.left() + zone.width() * pt["heure"] / 23,
                                      zone.bottom() - zone.height() * pt[mode] / maxi)
                              for pt in self.points if pt.get(mode)])
            p.setPen(QPen(COULEURS_MODE[mode], 2.5))
            p.drawPolyline(poly)
        # légende
        x = zone.left() + 8
        for mode in ("classique", "trafic", "priorite"):
            p.setPen(QPen(COULEURS_MODE[mode], 3))
            p.drawLine(QPointF(x, zone.top() + 6), QPointF(x + 18, zone.top() + 6))
            p.setPen(TEXTE)
            p.drawText(QPointF(x + 22, zone.top() + 10), LIBELLES_COURTS[mode])
            x += 110
