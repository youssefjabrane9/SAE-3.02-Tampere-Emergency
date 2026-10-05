"""Calcul des trois itinéraires (Dijkstra sur les arcs, pour tenir compte des virages).

  - CLASSIQUE : le plus court en distance (GPS "naïf", ignore trafic et feux) ;
  - TRAFIC    : le plus rapide selon la densité du trafic à l'heure donnée et
                les plans de feux connus du centre de régulation (Dijkstra
                "dépendant du temps" : on calcule l'attente réelle à chaque feu) ;
  - PRIORITE  : le plus rapide en supposant que les carrefours connectés
                donnent le vert au véhicule (préemption des feux).
"""

import heapq

from .ville import PENALITE_VIRAGE_S, delai_file, vitesse_urgence

CLASSIQUE = "classique"
TRAFIC = "trafic"
PRIORITE = "priorite"
MODES = [CLASSIQUE, TRAFIC, PRIORITE]
LIBELLES = {
    CLASSIQUE: "Trajet classique",
    TRAFIC: "Adapté au trafic",
    PRIORITE: "Optimisé + priorité feux",
}

DELAI_PREEMPTION_S = 1.5   # coût moyen résiduel d'un carrefour connecté


def passage_feu(prog, axe, t_arrivee, file_s):
    """Instant où le véhicule franchit un feu à cycle fixe (attente du vert + file)."""
    debut = prog.debut_vert(axe, t_arrivee)
    if debut is None:
        u = (t_arrivee + prog.decalage) % prog.cycle
        r = (u - prog._debut_phase(axe)) % prog.cycle
        debut = t_arrivee + (prog.cycle - r)       # prochain passage au vert
    return max(t_arrivee, debut + file_s)


def _cout_route(ville, densites, precedent, depuis, vers):
    route = ville.route_entre(depuis, vers)
    t = route.longueur / vitesse_urgence(route, densites[route.id])
    if precedent is not None and ville.axe_approche(precedent, depuis) != ville.axe_approche(depuis, vers):
        t += PENALITE_VIRAGE_S
    return t


def _arrivee_trafic(ville, densites, t, precedent, depuis, vers, arrivee):
    """Heure de franchissement de `vers` en partant de `depuis` à l'instant t (feux normaux)."""
    t += _cout_route(ville, densites, precedent, depuis, vers)
    prog = ville.intersections[vers].programme
    if vers != arrivee and prog is not None:
        route = ville.route_entre(depuis, vers)
        t = passage_feu(prog, ville.axe_approche(depuis, vers), t, delai_file(route, densites[route.id]))
    return t


def cout_arc(ville, densites, mode, precedent, depuis, vers, arrivee):
    """Coût (additif) d'un arc pour les modes CLASSIQUE (mètres) et PRIORITE (secondes)."""
    if mode == CLASSIQUE:
        return ville.route_entre(depuis, vers).longueur
    t = _cout_route(ville, densites, precedent, depuis, vers)
    if vers != arrivee and ville.intersections[vers].programme is not None:
        t += DELAI_PREEMPTION_S
    return t


def plus_court_chemin(ville, densites, depart, arrivee, mode):
    """Dijkstra sur les états (intersection, intersection précédente)."""
    if depart == arrivee:
        return [depart]
    tas = [(0.0, depart, None)]
    meilleur = {(depart, None): 0.0}
    parent = {}
    while tas:
        cout, noeud, prec = heapq.heappop(tas)
        if cout > meilleur.get((noeud, prec), float("inf")):
            continue
        if noeud == arrivee:
            chemin = [noeud]
            etat = (noeud, prec)
            while etat in parent:
                etat = parent[etat]
                chemin.append(etat[0])
            return chemin[::-1]
        for v in ville.intersections[noeud].voisins:
            if v == prec:
                continue                      # pas de demi-tour
            if mode == TRAFIC:          # coût = heure de passage (FIFO => Dijkstra reste exact)
                c = _arrivee_trafic(ville, densites, cout, prec, noeud, v, arrivee)
            else:
                c = cout + cout_arc(ville, densites, mode, prec, noeud, v, arrivee)
            etat = (v, noeud)
            if c < meilleur.get(etat, float("inf")):
                meilleur[etat] = c
                parent[etat] = (noeud, prec)
                heapq.heappush(tas, (c, v, noeud))
    return None


def estimer_temps(ville, densites, chemin, mode):
    """Temps estimé (s) d'un chemin : feux normaux, ou priorité aux feux pour PRIORITE."""
    total = 0.0
    for i in range(len(chemin) - 1):
        prec = chemin[i - 1] if i > 0 else None
        if mode == PRIORITE:
            total += cout_arc(ville, densites, PRIORITE, prec, chemin[i], chemin[i + 1], chemin[-1])
        else:
            total = _arrivee_trafic(ville, densites, total, prec, chemin[i], chemin[i + 1], chemin[-1])
    return total


def distance(ville, chemin):
    return sum(ville.route_entre(chemin[i], chemin[i + 1]).longueur for i in range(len(chemin) - 1))


def calculer_itineraires(ville, densites, depart, arrivee):
    res = []
    for mode in MODES:
        chemin = plus_court_chemin(ville, densites, depart, arrivee, mode)
        if chemin is None:
            continue
        res.append({
            "mode": mode,
            "libelle": LIBELLES[mode],
            "chemin": chemin,
            "distance": distance(ville, chemin),
            "temps_estime": round(estimer_temps(ville, densites, chemin, mode), 1),
        })
    return res
