"""Feux de circulation : état courant (avec forçages) et logique des carrefours connectés.

MondeFeux            : l'état des feux vu par une simulation (cycle normal + forçages reçus).
GestionnairePriorite : la logique de l'unité de bord de route (RSU) qui accorde ou refuse
                       le vert à un véhicule prioritaire. Elle tourne dans le serveur ;
                       la même classe est réutilisée hors-ligne pour l'analyse horaire.
"""

from .ville import AMBRE_S, ROUGE_INTEGRAL_S

# Niveaux de priorité (plus grand = plus prioritaire en cas de conflit)
VEHICULES = {
    "Pompiers": 3,
    "Ambulance (SAMU)": 2,
    "Police": 1,
}

MARGE_MAINTIEN_S = 20.0    # sécurité : le forçage expire seul si le véhicule ne se libère pas


class MondeFeux:
    def __init__(self, ville):
        self.ville = ville
        self.forcages = {}     # intersection -> dict(axe, vert_depuis, debut_vert, maintien)

    def _forcage(self, noeud, t):
        f = self.forcages.get(noeud)
        if f and t < f["maintien"]:
            return f
        return None

    def etat(self, noeud, axe, t):
        prog = self.ville.intersections[noeud].programme
        if prog is None:
            return "vert"
        f = self._forcage(noeud, t)
        if f is None:
            return prog.etat(axe, t)
        if f["axe"] == axe:
            return "vert" if t >= f["vert_depuis"] else "rouge"
        # axe transversal : on termine proprement la phase en cours (orange puis rouge)
        if t < f["vert_depuis"] - ROUGE_INTEGRAL_S and prog.etat(axe, t) != "rouge":
            return "orange"
        return "rouge"

    def debut_vert(self, noeud, axe, t):
        prog = self.ville.intersections[noeud].programme
        if prog is None:
            return None
        f = self._forcage(noeud, t)
        if f is None:
            return prog.debut_vert(axe, t)
        if f["axe"] == axe and t >= f["vert_depuis"]:
            return f["debut_vert"]
        return None

    def est_force(self, noeud, t):
        return self._forcage(noeud, t) is not None

    def appliquer(self, noeud, accord):
        self.forcages[noeud] = {
            "axe": accord["axe"],
            "vert_depuis": accord["vert_depuis"],
            "debut_vert": accord["debut_vert"],
            "maintien": accord["maintien"],
        }

    def liberer(self, noeud):
        self.forcages.pop(noeud, None)

    def instantane(self, t):
        """État de tous les carrefours à feux (pour l'affichage)."""
        res = {}
        for ident, inter in self.ville.intersections.items():
            if inter.programme is not None:
                res[ident] = (self.etat(ident, "NS", t), self.etat(ident, "EO", t), self.est_force(ident, t))
        return res


class GestionnairePriorite:
    """Logique RSU : un accord de vert par (mission, carrefour)."""

    def __init__(self, ville):
        self.ville = ville
        self.accords = {}      # (mission, noeud) -> accord

    def demander(self, mission, vehicule, niveau, noeud, axe, eta, t):
        """Retourne (réponse, accord_révoqué_ou_None)."""
        prog = self.ville.intersections[noeud].programme
        if prog is None:
            return {"accorde": False, "raison": "pas de feu"}, None
        cle = (mission, noeud)
        existant = self.accords.get(cle)
        revoque = None
        if existant and t < existant["maintien"] and existant["vehicule"] != vehicule:
            if existant["axe"] == axe:
                # même sens : les deux véhicules profitent du même vert
                existant["maintien"] = max(existant["maintien"], t + eta + MARGE_MAINTIEN_S)
                return dict(existant, accorde=True, vehicule=vehicule), None
            if niveau <= existant["niveau"]:
                return {"accorde": False, "raison": f"conflit avec {existant['vehicule']}",
                        "reessayer_dans": 2.0}, None
            revoque = existant

        if existant and existant["vehicule"] == vehicule and t < existant["maintien"]:
            existant["maintien"] = max(existant["maintien"], t + eta + MARGE_MAINTIEN_S)
            return dict(existant, accorde=True), None

        etat = prog.etat(axe, t)
        if etat == "vert":
            vert_depuis, debut_vert = t, prog.debut_vert(axe, t)       # simple prolongation
        elif etat == "orange":
            vert_depuis, debut_vert = t, t - prog.duree_vert(axe)
        else:
            autre = "EO" if axe == "NS" else "NS"
            transition = AMBRE_S + ROUGE_INTEGRAL_S if prog.etat(autre, t) == "vert" else ROUGE_INTEGRAL_S
            vert_depuis = t + transition
            debut_vert = vert_depuis
        accord = {
            "mission": mission, "vehicule": vehicule, "niveau": niveau, "noeud": noeud,
            "axe": axe, "vert_depuis": round(vert_depuis, 2), "debut_vert": round(debut_vert, 2),
            "maintien": round(t + eta + MARGE_MAINTIEN_S, 2),
        }
        self.accords[cle] = accord
        return dict(accord, accorde=True), revoque

    def liberer(self, mission, vehicule, noeud):
        cle = (mission, noeud)
        a = self.accords.get(cle)
        if a and a["vehicule"] == vehicule:
            del self.accords[cle]
            return True
        return False

    def terminer_mission(self, mission):
        for cle in [c for c in self.accords if c[0] == mission]:
            del self.accords[cle]
