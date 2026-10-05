class Ville:
    def __init__(self):
        # Les carrefours et les distances entre eux
        self.routes = {
            "A": {"B": 5, "C": 2},
            "B": {"A": 5, "D": 3},
            "C": {"A": 2, "D": 4},
            "D": {"B": 3, "C": 4}
        }


def dijkstra(graphe, depart, arrivee):
    distances = {}
    visites = []
    precedents = {}

    # Au début, toutes les distances sont infinies
    for sommet in graphe:
        distances[sommet] = float("inf")

    distances[depart] = 0

    while len(visites) < len(graphe):

        # Chercher le sommet non visité le plus proche
        actuel = None

        for sommet in graphe:
            if sommet not in visites:
                if actuel is None or distances[sommet] < distances[actuel]:
                    actuel = sommet

        visites.append(actuel)

        # Regarder les voisins
        for voisin in graphe[actuel]:
            nouvelle_distance = distances[actuel] + graphe[actuel][voisin]

            if nouvelle_distance < distances[voisin]:
                distances[voisin] = nouvelle_distance
                precedents[voisin] = actuel

    # Reconstruire le chemin
    chemin = []
    sommet = arrivee

    while sommet != depart:
        chemin.append(sommet)
        sommet = precedents[sommet]

    chemin.append(depart)
    chemin.reverse()

    return distances[arrivee], chemin


# Création de la ville
ville = Ville()

# Test
distance, chemin = dijkstra(ville.routes, "A", "D")

print("Distance :", distance)
print("Chemin :", chemin)