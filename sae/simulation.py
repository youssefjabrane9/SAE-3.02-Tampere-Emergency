"""Simulation d'une mission : trois véhicules prioritaires roulent en parallèle,
chacun dans son propre "monde" (mêmes densités, mêmes cycles de feux), un par stratégie.

Seul le véhicule PRIORITE est connecté : à l'approche d'un carrefour il envoie une
demande de priorité (V2I) via son unité embarquée (OBU). L'OBU réseau est fournie
par le client ; une OBU locale (sans réseau) sert à l'analyse hors-ligne et aux tests.
"""

import math

from .feux import GestionnairePriorite, MondeFeux
from .itineraire import PRIORITE
from .ville import PENALITE_VIRAGE_S, delai_file, vitesse_urgence

DISTANCE_DEMANDE_M = 250.0    # le véhicule s'annonce à 250 m du carrefour ...
ETA_DEMANDE_S = 20.0          # ... ou 20 s avant d'y arriver
RELANCE_S = 2.0               # nouvelle demande si pas de réponse / refus


class ObuLocale:
    """Unité embarquée sans réseau : parle directement à un GestionnairePriorite."""

    def __init__(self, gestionnaire, monde, mission="local", niveau=2):
        self.g = gestionnaire
        self.monde = monde
        self.mission = mission
        self.niveau = niveau

    def demander(self, vehicule, noeud, axe, eta, t):
        rep, _ = self.g.demander(self.mission, vehicule, self.niveau, noeud, axe, eta, t)
        if rep.get("accorde"):
            self.monde.appliquer(noeud, rep)

    def liberer(self, vehicule, noeud, t):
        self.g.liberer(self.mission, vehicule, noeud)

    def cam(self, vehicule, x, y, v, t):
        pass


class Vehicule:
    def __init__(self, ville, densites, itineraire, monde, obu=None, nom=None):
        self.ville = ville
        self.densites = densites
        self.mode = itineraire["mode"]
        self.chemin = itineraire["chemin"]
        self.distance = itineraire["distance"]
        self.temps_estime = itineraire["temps_estime"]
        self.monde = monde
        self.obu = obu
        self.nom = nom or self.mode
        self.idx = 0
        self.s = 0.0
        self.arrive = len(self.chemin) < 2
        self.t_arrivee = 0.0 if self.arrive else None
        self.attente_feux = 0.0
        self.arrets = 0
        self._bloque_jusqua = 0.0
        self._raison = None
        self._arrete_au_feu = False
        self._file_servie = set()
        self._relances = {}
        self._prochain_cam = 0.0
        self.vitesse = 0.0

    # ---------------------------------------------------------------- géométrie
    def _arc(self):
        return self.chemin[self.idx], self.chemin[self.idx + 1]

    def position(self):
        if self.arrive:
            n = self.ville.intersections[self.chemin[-1]]
            return n.x, n.y, 0.0
        a, b = (self.ville.intersections[n] for n in self._arc())
        r = self.ville.route_entre(a.id, b.id)
        f = min(1.0, self.s / r.longueur)
        cap = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        return a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f, cap

    # ---------------------------------------------------------------- dynamique
    def etape(self, t, dt):
        if self.arrive:
            return
        u, v = self._arc()
        route = self.ville.route_entre(u, v)
        dens = self.densites[route.id]
        vit = vitesse_urgence(route, dens)
        axe = self.ville.axe_approche(u, v)
        a_un_feu = v != self.chemin[-1] and self.ville.intersections[v].programme is not None

        # Unité embarquée : demande de priorité et balise de position (CAM)
        if self.obu is not None:
            if t >= self._prochain_cam:
                x, y, _ = self.position()
                self.obu.cam(self.nom, x, y, self.vitesse, t)
                self._prochain_cam = t + 1.0
            if a_un_feu:
                reste = route.longueur - self.s
                f = self.monde.forcages.get(v)
                deja = f is not None and f["axe"] == axe and t < f["maintien"]
                if not deja and (reste <= DISTANCE_DEMANDE_M or reste / vit <= ETA_DEMANDE_S) \
                        and t >= self._relances.get(v, 0.0):
                    self.obu.demander(self.nom, v, axe, round(reste / vit, 1), t)
                    self._relances[v] = t + RELANCE_S

        if t < self._bloque_jusqua:
            self.vitesse = 0.0
            if self._raison == "feu":
                self.attente_feux += dt
            return

        nouvelle = self.s + vit * dt
        if nouvelle < route.longueur:
            self.s = nouvelle
            self.vitesse = vit
            self._arrete_au_feu = False
            return

        # on atteint la ligne de feu / l'intersection v
        if v == self.chemin[-1]:
            self.t_arrivee = t - dt + (route.longueur - self.s) / vit
            self.s = route.longueur
            self.arrive = True
            self.vitesse = 0.0
            return

        if a_un_feu:
            # instant exact d'arrivée à la ligne (dans ce pas de temps), sauf si déjà arrêté
            t_ligne = t if self._arrete_au_feu else t - dt + (route.longueur - self.s) / vit
            if self.monde.etat(v, axe, t_ligne) != "vert":
                if not self._arrete_au_feu:
                    self.arrets += 1
                    self._arrete_au_feu = True
                self.s = route.longueur
                self.vitesse = 0.0
                self.attente_feux += dt
                return
            if v not in self._file_servie:
                self._file_servie.add(v)
                debut = self.monde.debut_vert(v, axe, t_ligne)
                reste = (debut if debut is not None else t_ligne) + delai_file(route, dens) - t
                if reste > 0.05:
                    if not self._arrete_au_feu:
                        self.arrets += 1
                    self._arrete_au_feu = True
                    self.s = route.longueur
                    self.vitesse = 0.0
                    self._bloque_jusqua = t + reste
                    self._raison = "feu"
                    return

        # franchissement du carrefour
        self._arrete_au_feu = False
        if a_un_feu and self.obu is not None:
            self.obu.liberer(self.nom, v, t)
            self.monde.liberer(v)
        self.idx += 1
        self.s = 0.0
        w = self.chemin[self.idx + 1]
        if self.ville.axe_approche(u, v) != self.ville.axe_approche(v, w):
            self._bloque_jusqua = t + PENALITE_VIRAGE_S
            self._raison = "virage"

    def resultat(self):
        return {
            "mode": self.mode,
            "distance": self.distance,
            "temps_estime": self.temps_estime,
            "temps_simule": round(self.t_arrivee, 1) if self.t_arrivee is not None else None,
            "arrets": self.arrets,
            "attente_feux": round(self.attente_feux, 1),
            "chemin": self.chemin,
        }


class Mission:
    """Trois véhicules, trois mondes. `obu_reseau` : OBU du véhicule connecté (ou None = locale)."""

    def __init__(self, ville, densites, itineraires, obu_reseau=None, niveau=2, nom_connecte="Ambulance"):
        self.ville = ville
        self.t = 0.0
        self.vehicules = []
        self.perturbation = 0.0
        self.monde_connecte = None
        for it in itineraires:
            monde = MondeFeux(ville)
            obu = None
            if it["mode"] == PRIORITE:
                self.monde_connecte = monde
                if obu_reseau is not None:
                    obu = obu_reseau
                else:
                    obu = ObuLocale(GestionnairePriorite(ville), monde, niveau=niveau)
            nom = nom_connecte if it["mode"] == PRIORITE else it["mode"]
            self.vehicules.append(Vehicule(ville, densites, it, monde, obu, nom))

    def monde(self, mode):
        for v in self.vehicules:
            if v.mode == mode:
                return v.monde
        return None

    @property
    def terminee(self):
        return all(v.arrive for v in self.vehicules)

    def etape(self, dt):
        self.t += dt
        for v in self.vehicules:
            v.etape(self.t, dt)
        m = self.monde_connecte
        if m is not None:
            # "perturbation" : secondes de vert retirées aux voies transversales
            for noeud, f in list(m.forcages.items()):
                if self.t < f["maintien"]:
                    prog = self.ville.intersections[noeud].programme
                    autre = "EO" if f["axe"] == "NS" else "NS"
                    if prog.etat(autre, self.t) == "vert":
                        self.perturbation += dt

    def executer(self, dt=0.1, t_max=3600.0):
        while not self.terminee and self.t < t_max:
            self.etape(dt)
        return self.resultats()

    def resultats(self):
        res = [v.resultat() for v in self.vehicules]
        ref = next((r["temps_simule"] for r in res if r["mode"] == "classique"), None)
        for r in res:
            if ref and r["temps_simule"] is not None:
                r["gain_s"] = round(ref - r["temps_simule"], 1)
                r["gain_pct"] = round(100 * (ref - r["temps_simule"]) / ref, 1)
        return {"vehicules": res, "perturbation_s": round(self.perturbation, 1)}
