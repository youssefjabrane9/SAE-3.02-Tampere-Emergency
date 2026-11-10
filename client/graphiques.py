"""Graphique de comparaison des temps des 3 trajets (matplotlib dans une fenêtre PyQt6).

FigureCanvasQTAgg est un widget Qt qui contient une figure matplotlib :
on le place dans la fenêtre comme un bouton ou une étiquette.
"""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from client.carte import COULEURS_MODE, MODES, NOMS_MODE, en_minutes


class GraphiqueTemps(FigureCanvasQTAgg):
    def __init__(self):
        super().__init__(Figure(figsize=(3, 2.5), layout="tight"))
        self.axes = self.figure.add_subplot()
        self.afficher({})

    def afficher(self, temps):
        """Redessine les barres. temps : {mode: secondes}, ex. {"classique": 140.2, ...}."""
        self.axes.clear()
        modes = [m for m in MODES if m in temps]           # dans l'ordre classique, trafic, priorité
        barres = self.axes.bar([NOMS_MODE[m] for m in modes],
                               [temps[m] / 60 for m in modes],          # secondes -> minutes
                               color=[COULEURS_MODE[m] for m in modes])
        # la valeur au-dessus de chaque barre, ex. "5 min 37 s"
        self.axes.bar_label(barres, labels=[en_minutes(temps[m]) for m in modes], fontsize=8)
        self.axes.margins(y=0.15)                           # de la place pour ces valeurs
        self.axes.set_ylabel("Temps (min)")
        self.axes.set_title("Temps de trajet", fontsize=10)
        self.axes.tick_params(labelsize=8)
        self.draw()                                         # demande à Qt de réafficher le widget
