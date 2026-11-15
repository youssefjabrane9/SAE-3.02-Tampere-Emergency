"""Graphique de comparaison des temps des 3 trajets (matplotlib dans une fenêtre PyQt6).

FigureCanvasQTAgg est un widget Qt qui contient une figure matplotlib :
on le place dans la fenêtre comme un bouton ou une étiquette.
"""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from client.carte import COULEURS_MODE, MODES, NOMS_MODE, en_minutes


class GraphiqueTemps(FigureCanvasQTAgg):
    """Graphique en barres des temps des 3 trajets, affiché dans la fenêtre PyQt6.

    Attributes:
        axes (matplotlib.axes.Axes): la zone de dessin du graphique.
    """
    def __init__(self):
        """Crée la figure matplotlib et affiche un graphique vide."""
        super().__init__(Figure(figsize=(3, 2.5), layout="tight"))
        self.axes = self.figure.add_subplot()
        self.afficher({})

    def afficher(self, temps):
        """Redessine les barres.

        Args:
            temps (dict[str, float]): secondes par stratégie, par exemple {"classique": 140.2, ...}.
                Un dict vide affiche seulement un message (pas d'axes vides).
        """
        self.axes.clear()
        if not temps:
            self.axes.set_axis_off()                        # pas d'axes tant qu'il n'y a rien à montrer
            self.axes.text(0.5, 0.5, "Cliquez sur Calculer\npour comparer les 3 temps",
                           ha="center", va="center", fontsize=10, color="gray")
            self.draw()
            return
        self.axes.set_axis_on()
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
