"""Affichage 2D de la ville avec QGraphicsScene / QGraphicsView.

Clic gauche sur un carrefour = départ, clic droit = arrivée, molette = zoom.
"""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem,
                             QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView)

from sae.ville import TRONCONS_FERMES, vitesse_trafic

COULEURS_MODE = {
    "classique": QColor("#5f6b7a"),
    "trafic": QColor("#1e88e5"),
    "priorite": QColor("#8e24aa"),
}
LETTRES_MODE = {"classique": "C", "trafic": "T", "priorite": "P"}
COULEURS_FEU = {"vert": QColor("#2e7d32"), "orange": QColor("#f9a825"), "rouge": QColor("#d32f2f")}
FOND = QColor("#eef1f4")


def couleur_densite(d):
    """Vert (fluide) -> jaune -> rouge (saturé)."""
    stops = [(0.0, (129, 199, 132)), (0.45, (255, 213, 79)), (0.8, (239, 83, 80)), (1.0, (183, 28, 28))]
    for (d0, c0), (d1, c1) in zip(stops, stops[1:]):
        if d <= d1:
            f = (d - d0) / (d1 - d0)
            return QColor(*(round(a + (b - a) * f) for a, b in zip(c0, c1)))
    return QColor(*stops[-1][1])


class ItemFeu(QGraphicsItem):
    """Carrefour à feux : barre verticale = axe NS, barre horizontale = axe EO."""

    def __init__(self, inter):
        super().__init__()
        self.inter = inter
        self.ns, self.eo, self.force = "rouge", "rouge", False
        self.setPos(inter.x, inter.y)
        self.setZValue(5)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)   # taille fixe à l'écran
        p = inter.programme
        self.setToolTip(f"{inter.libelle}\nCarrefour à feux — cycle {p.cycle:.0f} s "
                        f"(vert NS {p.vert_ns:.0f} s / EO {p.vert_eo:.0f} s)")

    def boundingRect(self):
        return QRectF(-17, -17, 34, 34)

    def definir(self, ns, eo, force):
        if (ns, eo, force) != (self.ns, self.eo, self.force):
            self.ns, self.eo, self.force = ns, eo, force
            self.update()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.force:
            painter.setPen(QPen(COULEURS_MODE["priorite"], 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), 15, 15)
        painter.setPen(QPen(QColor("#263238"), 1.5))
        painter.setBrush(QColor("#37474f"))
        painter.drawEllipse(QPointF(0, 0), 11, 11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(COULEURS_FEU[self.ns])
        painter.drawRoundedRect(QRectF(-2.8, -9, 5.6, 18), 2.5, 2.5)
        painter.setBrush(COULEURS_FEU[self.eo])
        painter.drawRoundedRect(QRectF(-9, -2.8, 18, 5.6), 2.5, 2.5)


class CoucheTrafic(QGraphicsItem):
    """Petits véhicules du trafic ordinaire, dessinés en un seul item (performances)."""

    def __init__(self, ville, rect):
        super().__init__()
        self.ville = ville
        self.rect = rect
        self.densites = {}
        self.t = 0.0
        self.setZValue(3)

    def boundingRect(self):
        return self.rect

    def definir(self, densites=None, t=None):
        if densites is not None:
            self.densites = densites
        if t is not None:
            self.t = t
        self.update()

    def paint(self, painter, option, widget=None):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(55, 71, 79, 170))
        for rid, r in self.ville.routes.items():
            d = self.densites.get(rid, 0.0)
            a, b = self.ville.intersections[r.a], self.ville.intersections[r.b]
            dx, dy = b.x - a.x, b.y - a.y
            ux, uy = dx / r.longueur, dy / r.longueur
            nb = max(1, round(d * 6))
            v = vitesse_trafic(r, d)
            for sens in (1, -1):
                ox, oy = -uy * 4.5 * sens, ux * 4.5 * sens
                for k in range(nb):
                    s = (self.t * v + k * r.longueur / nb + (sum(map(ord, rid)) * 37 % 200)) % r.longueur
                    if sens < 0:
                        s = r.longueur - s
                    s = 14 + s * (r.longueur - 28) / r.longueur
                    painter.drawEllipse(QPointF(a.x + ux * s + ox, a.y + uy * s + oy), 3.6, 3.6)


class ItemVehicule(QGraphicsEllipseItem):
    def __init__(self, mode):
        super().__init__(-12, -12, 24, 24)
        self.setBrush(QBrush(COULEURS_MODE[mode]))
        self.setPen(QPen(QColor("white"), 3))
        self.setZValue(20)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        texte = QGraphicsSimpleTextItem(LETTRES_MODE[mode], self)
        f = QFont()
        f.setBold(True)
        f.setPixelSize(13)
        texte.setFont(f)
        texte.setBrush(QColor("white"))
        br = texte.boundingRect()
        texte.setPos(-br.width() / 2, -br.height() / 2)


class CarteVille(QGraphicsView):
    depart_choisi = pyqtSignal(str)
    arrivee_choisie = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(FOND)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setMinimumSize(520, 380)
        self.ville = None
        self.items_routes = {}
        self.items_feux = {}
        self.items_itineraires = []
        self.items_vehicules = {}
        self.marqueurs = {}
        self.trafic = None
        self._zoom_utilisateur = False

    # ------------------------------------------------------------------ construction
    def charger_ville(self, ville):
        self.ville = ville
        sc = self.scene()
        sc.clear()
        self.items_routes.clear()
        self.items_feux.clear()
        self.items_itineraires.clear()
        self.items_vehicules.clear()
        self.marqueurs.clear()
        xs = [i.x for i in ville.intersections.values()]
        ys = [i.y for i in ville.intersections.values()]
        rect = QRectF(min(xs) - 90, min(ys) - 80, max(xs) - min(xs) + 200, max(ys) - min(ys) + 190)
        sc.setSceneRect(rect)

        # îlots (pâtés de maisons) pour l'ambiance
        for inter in ville.intersections.values():
            if inter.x < max(xs) and inter.y < max(ys):
                ilot = sc.addRect(QRectF(inter.x + 22, inter.y + 22, 176, 176), QPen(Qt.PenStyle.NoPen),
                                  QBrush(QColor("#e1e6ea")))
                ilot.setZValue(0)

        for rid, r in ville.routes.items():
            a, b = ville.intersections[r.a], ville.intersections[r.b]
            largeur = {"boulevard": 20, "avenue": 18, "rue": 12}[r.categorie]
            item = sc.addLine(a.x, a.y, b.x, b.y, QPen(QColor("#b0bec5"), largeur, Qt.PenStyle.SolidLine,
                                                         Qt.PenCapStyle.RoundCap))
            item.setZValue(1)
            item.setToolTip(f"{r.a} – {r.b} : {r.categorie}, {r.vitesse_kmh:.0f} km/h, {r.voies} voie(s)")
            self.items_routes[rid] = item

        for a_id, b_id in TRONCONS_FERMES:
            a, b = ville.intersections[a_id], ville.intersections[b_id]
            pen = QPen(QColor("#ff8f00"), 5, Qt.PenStyle.DashLine)
            ligne = sc.addLine(a.x + (b.x - a.x) * 0.3, a.y + (b.y - a.y) * 0.3,
                               a.x + (b.x - a.x) * 0.7, a.y + (b.y - a.y) * 0.7, pen)
            ligne.setZValue(1)
            ligne.setToolTip(f"{a_id} – {b_id} : fermé (travaux)")

        self.trafic = CoucheTrafic(ville, rect)
        sc.addItem(self.trafic)

        police = QFont()
        police.setPixelSize(11)
        police_lieu = QFont()
        police_lieu.setPixelSize(12)
        police_lieu.setBold(True)
        for inter in ville.intersections.values():
            if inter.programme is not None:
                item = ItemFeu(inter)
                sc.addItem(item)
                self.items_feux[inter.id] = item
            else:
                p = sc.addEllipse(inter.x - 8, inter.y - 8, 16, 16, QPen(QColor("#78909c"), 2),
                                  QBrush(QColor("#eceff1")))
                p.setZValue(5)
                p.setToolTip(f"{inter.libelle}\nCarrefour sans feu")
            # étiquettes à taille fixe, décalées en pixels depuis le carrefour
            ancre = self._ancre(inter.x, inter.y, 6)
            t = QGraphicsSimpleTextItem(inter.id, ancre)
            t.setFont(police)
            t.setBrush(QColor("#607d8b"))
            t.setPos(10, -24)
            if inter.lieu:
                lbl = QGraphicsSimpleTextItem(inter.lieu)
                lbl.setFont(police_lieu)
                lbl.setBrush(QColor("#263238"))
                br = lbl.boundingRect()
                fond = QGraphicsRectItem(QRectF(12, 9, br.width() + 10, br.height() + 4),
                                         self._ancre(inter.x, inter.y, 7))
                fond.setPen(QPen(QColor("#90a4ae"), 1))
                fond.setBrush(QBrush(QColor(255, 255, 255, 235)))
                lbl.setParentItem(fond)
                lbl.setPos(17, 11)
        self.ajuster()

    def _ancre(self, x, y, z):
        ancre = QGraphicsRectItem(0, 0, 0, 0)
        ancre.setPen(QPen(Qt.PenStyle.NoPen))
        ancre.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        ancre.setPos(x, y)
        ancre.setZValue(z)
        self.scene().addItem(ancre)
        return ancre

    def appliquer_densites(self, densites):
        for rid, item in self.items_routes.items():
            d = densites.get(rid, 0.0)
            pen = item.pen()
            pen.setColor(couleur_densite(d))
            item.setPen(pen)
            r = self.ville.routes[rid]
            item.setToolTip(f"{r.a} – {r.b} : {r.categorie}, {r.vitesse_kmh:.0f} km/h, {r.voies} voie(s)\n"
                            f"Densité : {d * 100:.0f} %")
        if self.trafic:
            self.trafic.definir(densites=densites)

    def definir_trafic_visible(self, visible):
        if self.trafic:
            self.trafic.setVisible(visible)

    # ------------------------------------------------------------------ itinéraires
    def afficher_itineraires(self, itineraires):
        self.effacer_itineraires()
        decalages = {"classique": -13, "trafic": 0, "priorite": 13}
        for it in itineraires:
            chemin = it["chemin"]
            dec = decalages[it["mode"]]
            path = QPainterPath()
            points = []
            for i, n in enumerate(chemin):
                inter = self.ville.intersections[n]
                # décalage perpendiculaire pour que les tracés superposés restent visibles
                j0, j1 = (i - 1, i) if i > 0 else (0, 1)
                a, b = self.ville.intersections[chemin[j0]], self.ville.intersections[chemin[j1]]
                lg = math.hypot(b.x - a.x, b.y - a.y) or 1
                points.append(QPointF(inter.x - (b.y - a.y) / lg * dec, inter.y + (b.x - a.x) / lg * dec))
            path.moveTo(points[0])
            for p in points[1:]:
                path.lineTo(p)
            couleur = QColor(COULEURS_MODE[it["mode"]])
            couleur.setAlpha(215)
            item = QGraphicsPathItem(path)
            item.setPen(QPen(couleur, 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            item.setZValue(10 + list(decalages).index(it["mode"]))
            self.scene().addItem(item)
            self.items_itineraires.append(item)

    def effacer_itineraires(self):
        for item in self.items_itineraires:
            self.scene().removeItem(item)
        self.items_itineraires.clear()
        self.effacer_vehicules()

    def marquer(self, role, noeud):
        """role = 'depart' ou 'arrivee'."""
        ancien = self.marqueurs.pop(role, None)
        if ancien:
            self.scene().removeItem(ancien)
        if not noeud or self.ville is None:
            return
        inter = self.ville.intersections[noeud]
        couleur = QColor("#2e7d32") if role == "depart" else QColor("#c62828")
        item = QGraphicsEllipseItem(-17, -17, 34, 34)
        item.setPen(QPen(couleur, 5))
        item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        item.setPos(inter.x, inter.y)
        item.setZValue(15)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        texte = QGraphicsSimpleTextItem("DÉPART" if role == "depart" else "ARRIVÉE", item)
        f = QFont()
        f.setBold(True)
        f.setPixelSize(12)
        texte.setFont(f)
        texte.setBrush(couleur)
        texte.setPos(-texte.boundingRect().width() / 2, -38)
        self.scene().addItem(item)
        self.marqueurs[role] = item

    # ------------------------------------------------------------------ animation
    def afficher_trame(self, trame):
        for v in trame["vehicules"]:
            item = self.items_vehicules.get(v["mode"])
            if item is None:
                item = ItemVehicule(v["mode"])
                self.scene().addItem(item)
                self.items_vehicules[v["mode"]] = item
            item.setPos(v["x"], v["y"])
            item.setOpacity(0.55 if v["arrive"] else 1.0)
        for noeud, (ns, eo, force) in trame["feux"].items():
            item = self.items_feux.get(noeud)
            if item:
                item.definir(ns, eo, force)
        if self.trafic and self.trafic.isVisible():
            self.trafic.definir(t=trame["t"])

    def afficher_feux(self, etats):
        for noeud, (ns, eo, force) in etats.items():
            if noeud in self.items_feux:
                self.items_feux[noeud].definir(ns, eo, force)

    def effacer_vehicules(self):
        for item in self.items_vehicules.values():
            self.scene().removeItem(item)
        self.items_vehicules.clear()

    # ------------------------------------------------------------------ interactions
    def _carrefour_sous(self, pos_vue):
        if self.ville is None:
            return None
        p = self.mapToScene(pos_vue)
        meilleur, dmin = None, 30.0
        for inter in self.ville.intersections.values():
            d = math.hypot(inter.x - p.x(), inter.y - p.y())
            if d < dmin:
                meilleur, dmin = inter.id, d
        return meilleur

    def mousePressEvent(self, event):
        noeud = self._carrefour_sous(event.position().toPoint())
        if noeud and event.button() == Qt.MouseButton.LeftButton:
            self.depart_choisi.emit(noeud)
            return
        if noeud and event.button() == Qt.MouseButton.RightButton:
            self.arrivee_choisie.emit(noeud)
            return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        facteur = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom_utilisateur = True
        self.scale(facteur, facteur)

    def ajuster(self):
        self._zoom_utilisateur = False
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._zoom_utilisateur:
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def drawForeground(self, painter, rect):
        """Légende fixe en bas à gauche de la vue."""
        painter.save()
        painter.resetTransform()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        lignes = [("C", COULEURS_MODE["classique"], "Trajet classique"),
                  ("T", COULEURS_MODE["trafic"], "Adapté au trafic"),
                  ("P", COULEURS_MODE["priorite"], "Optimisé + priorité feux")]
        f = QFont()
        f.setPixelSize(12)
        painter.setFont(f)
        h = 20 * len(lignes) + 32
        x0, y0 = 10, self.viewport().height() - h - 10
        painter.setPen(QPen(QColor("#b0bec5")))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawRoundedRect(QRectF(x0, y0, 205, h), 6, 6)
        for i, (lettre, c, txt) in enumerate(lignes):
            y = y0 + 16 + i * 20
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c)
            painter.drawEllipse(QPointF(x0 + 16, y), 7, 7)
            painter.setPen(QColor("#263238"))
            painter.drawText(QPointF(x0 + 30, y + 4), txt)
        y = y0 + 16 + len(lignes) * 20
        for k, d in enumerate((0.1, 0.45, 0.8)):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(couleur_densite(d))
            painter.drawRect(QRectF(x0 + 10 + k * 16, y - 5, 16, 10))
        painter.setPen(QColor("#263238"))
        painter.drawText(QPointF(x0 + 64, y + 4), "Densité du trafic")
        painter.restore()
