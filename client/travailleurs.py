"""Threads de calcul du client : simulation d'une mission et analyse horaire hors-ligne."""

import queue
import time

from PyQt6.QtCore import QThread, pyqtSignal

from sae.itineraire import PRIORITE, calculer_itineraires
from sae.simulation import Mission

PAS_SIM_S = 0.1          # pas de temps de la simulation
PERIODE_IHM_S = 0.04     # ~25 images par seconde


class TravailleurMission(QThread):
    trame = pyqtSignal(dict)
    termine = pyqtSignal(dict)

    def __init__(self, ville, densites, itineraires, lien=None, niveau=2, nom="Ambulance", parent=None):
        super().__init__(parent)
        self.ville = ville
        self.densites = densites
        self.itineraires = itineraires
        self.lien = lien
        self.niveau = niveau
        self.nom = nom
        # réglages modifiés par l'IHM (simples affectations d'attributs : atomiques en Python)
        self.acceleration = 5.0
        self.feux_affiches = PRIORITE
        self.en_pause = False
        self._actif = True

    def arreter(self):
        self._actif = False

    def _lire_accords(self, mission):
        if self.lien is None:
            return
        monde = mission.monde_connecte
        while True:
            try:
                msg = self.lien.accords.get_nowait()
            except queue.Empty:
                return
            if msg["type"] == "PRIORITY_GRANT":
                # l'accord arrive un peu après la demande : on ne le fait pas démarrer dans le passé
                msg["vert_depuis"] = max(msg["vert_depuis"], mission.t)
                monde.appliquer(msg["noeud"], msg)
            elif msg["type"] == "PRIORITY_REVOKED":
                monde.liberer(msg["noeud"])

    def run(self):
        mission = Mission(self.ville, self.densites, self.itineraires, obu_reseau=self.lien, niveau=self.niveau,
                          nom_connecte=self.nom)
        if self.lien is None:
            # pas de serveur : aucun carrefour ne répond, le véhicule "connecté" subit les feux
            for v in mission.vehicules:
                if v.mode == PRIORITE:
                    v.obu = None
        dette = 0.0
        precedent = time.perf_counter()
        while self._actif and not mission.terminee:
            maintenant = time.perf_counter()
            ecoule, precedent = maintenant - precedent, maintenant
            if not self.en_pause:
                dette += ecoule * self.acceleration
                while dette >= PAS_SIM_S and not mission.terminee:
                    self._lire_accords(mission)
                    mission.etape(PAS_SIM_S)
                    dette -= PAS_SIM_S
            self.trame.emit(self._instantane(mission))
            time.sleep(PERIODE_IHM_S)
        self.trame.emit(self._instantane(mission))
        if mission.terminee:
            self.termine.emit(mission.resultats())

    def _instantane(self, mission):
        vehicules = []
        for v in mission.vehicules:
            x, y, cap = v.position()
            vehicules.append({"mode": v.mode, "x": x, "y": y, "cap": cap, "arrive": v.arrive,
                              "vitesse_kmh": round(v.vitesse * 3.6), "arrets": v.arrets,
                              "attente": round(v.attente_feux, 1),
                              "t": v.t_arrivee if v.arrive else mission.t})
        monde = mission.monde(self.feux_affiches) or mission.monde_connecte
        return {"t": mission.t, "vehicules": vehicules, "feux": monde.instantane(mission.t),
                "perturbation": mission.perturbation}


class TravailleurAnalyse(QThread):
    """Rejoue la mission pour chaque heure de 0 h à 23 h (simulation locale, sans réseau)."""

    progression = pyqtSignal(int)
    resultat = pyqtSignal(list)

    def __init__(self, ville, depart, arrivee, niveau=2, parent=None):
        super().__init__(parent)
        self.ville = ville
        self.depart = depart
        self.arrivee = arrivee
        self.niveau = niveau

    def run(self):
        points = []
        for h in range(24):
            dens = self.ville.densites(h)
            its = calculer_itineraires(self.ville, dens, self.depart, self.arrivee)
            res = Mission(self.ville, dens, its, niveau=self.niveau).executer(dt=0.2)
            temps = {v["mode"]: v["temps_simule"] for v in res["vehicules"]}
            points.append({"heure": h, **temps})
            self.progression.emit(h + 1)
        self.resultat.emit(points)
