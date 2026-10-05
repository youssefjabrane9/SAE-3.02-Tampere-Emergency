"""Tests automatiques (bibliothèque standard uniquement) :  python -m unittest -v"""

import os
import random
import socket
import tempfile
import threading
import unittest

from sae.feux import GestionnairePriorite
from sae.itineraire import calculer_itineraires
from sae.protocole import Deframeur, decoder_datagramme, encoder, encoder_datagramme
from sae.simulation import Mission
from sae.ville import TRONCONS_FERMES, Ville
from serveur.serveur import CentreRegulation


class TestVille(unittest.TestCase):
    def setUp(self):
        self.ville = Ville.generer()

    def test_structure(self):
        self.assertEqual(len(self.ville.intersections), 48)
        for a, b in TRONCONS_FERMES:
            self.assertIsNone(self.ville.route_entre(a, b))

    def test_densites_deterministes_et_horaires(self):
        self.assertEqual(self.ville.densites(8), Ville.generer().densites(8))
        nuit = sum(self.ville.densites(3).values())
        pointe = sum(self.ville.densites(8).values())
        self.assertGreater(pointe, 1.5 * nuit)

    def test_feux_jamais_deux_verts(self):
        for inter in self.ville.intersections.values():
            p = inter.programme
            if p is None:
                continue
            for k in range(int(p.cycle * 4)):
                t = k * 0.25
                self.assertFalse(p.etat("NS", t) == "vert" and p.etat("EO", t) == "vert")

    def test_serialisation(self):
        copie = Ville.from_dict(self.ville.to_dict())
        self.assertEqual(copie.densites(17), self.ville.densites(17))
        self.assertEqual(copie.intersections["D3"].programme.to_dict(),
                         self.ville.intersections["D3"].programme.to_dict())


class TestItinerairesEtSimulation(unittest.TestCase):
    def test_comparaison_des_trois_strategies(self):
        ville = Ville.generer()
        ids = list(ville.intersections)
        rng = random.Random(42)
        gains = []
        for _ in range(60):
            h = rng.randrange(24)
            a, b = rng.sample(ids, 2)
            dens = ville.densites(h)
            res = Mission(ville, dens, calculer_itineraires(ville, dens, a, b)).executer()
            c, t, p = (v["temps_simule"] for v in res["vehicules"])
            self.assertLessEqual(t, c + 0.5, f"trafic plus lent que classique {a}->{b} {h}h")
            self.assertLessEqual(p, t + 0.5, f"priorité plus lente que trafic {a}->{b} {h}h")
            # l'estimation "trafic" (Dijkstra dépendant du temps) colle à la simulation
            self.assertAlmostEqual(res["vehicules"][1]["temps_estime"], t, delta=1.0)
            self.assertEqual(res["vehicules"][2]["arrets"], 0)
            gains.append((c - p) / c)
        self.assertGreater(sum(gains) / len(gains), 0.2)


class TestPriorite(unittest.TestCase):
    def test_conflit_entre_vehicules(self):
        ville = Ville.generer()
        g = GestionnairePriorite(ville)
        rep, _ = g.demander("m", "Police", 1, "D3", "NS", 10, 0.0)
        self.assertTrue(rep["accorde"])
        rep, _ = g.demander("m", "Police 2", 1, "D3", "EO", 10, 1.0)
        self.assertFalse(rep["accorde"])            # même niveau : refus, réessayer
        rep, revoque = g.demander("m", "Pompiers", 3, "D3", "EO", 10, 2.0)
        self.assertTrue(rep["accorde"])             # plus prioritaire : révoque la police
        self.assertEqual(revoque["vehicule"], "Police")
        self.assertTrue(g.liberer("m", "Pompiers", "D3"))

    def test_carrefour_sans_feu(self):
        g = GestionnairePriorite(Ville.generer())
        rep, _ = g.demander("m", "A", 2, "A1", "NS", 5, 0.0)
        self.assertFalse(rep["accorde"])


class TestProtocole(unittest.TestCase):
    def test_trames_morcelees(self):
        octets = encoder({"type": "A", "x": "é"}) + encoder({"type": "B"})
        d = Deframeur()
        recus = []
        for i in range(0, len(octets), 3):
            recus += d.alimenter(octets[i:i + 3])
        self.assertEqual([m["type"] for m in recus], ["A", "B"])

    def test_trame_invalide(self):
        with self.assertRaises(ValueError):
            Deframeur().alimenter(b'{"pas_de_type": 1}\n')
        with self.assertRaises(ValueError):
            decoder_datagramme(b"[1,2]")


class TestServeur(unittest.TestCase):
    """Test d'intégration : vrai serveur, vraies sockets TCP et UDP."""

    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.mkdtemp()
        cls.serveur = CentreRegulation("127.0.0.1", 0, 0, os.path.join(cls.dossier, "t.db"))
        cls.serveur.demarrer()
        cls.fil = threading.Thread(target=cls.serveur.executer, daemon=True)
        cls.fil.start()
        cls.serveur.pret.wait(5)

    @classmethod
    def tearDownClass(cls):
        cls.serveur.arreter()
        cls.fil.join(3)

    def _requete(self, sock, deframeur, message, attendu):
        if message is not None:
            sock.sendall(encoder(message))
        while True:
            for m in deframeur.alimenter(sock.recv(65536)):
                if m["type"] == attendu:
                    return m

    def test_scenario_complet(self):
        tcp = socket.create_connection(("127.0.0.1", self.serveur.port_tcp), timeout=5)
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.settimeout(5)
        d = Deframeur()
        try:
            w = self._requete(tcp, d, {"type": "HELLO", "nom": "test"}, "WELCOME")
            self.assertEqual(w["port_udp"], self.serveur.port_udp)
            c = self._requete(tcp, d, {"type": "GET_CITY", "heure": 8}, "CITY")
            self.assertEqual(len(c["ville"]["intersections"]), 48)
            r = self._requete(tcp, d, {"type": "COMPUTE_ROUTES", "depart": "B2", "arrivee": "G5",
                                       "heure": 8}, "ROUTES")
            self.assertEqual([i["mode"] for i in r["itineraires"]], ["classique", "trafic", "priorite"])
            self._requete(tcp, d, {"type": "MISSION_START", "mission": "t1"}, "MISSION_OK")

            udp.sendto(encoder_datagramme({"type": "PRIORITY_REQUEST", "id": 1, "mission": "t1",
                                           "vehicule": "SAMU", "niveau": 2, "noeud": "D3", "axe": "EO",
                                           "eta": 12, "t": 30.0}), ("127.0.0.1", self.serveur.port_udp))
            rep = decoder_datagramme(udp.recvfrom(8192)[0])
            self.assertEqual(rep["type"], "PRIORITY_GRANT")
            self.assertEqual(rep["id"], 1)
            self.assertGreaterEqual(rep["vert_depuis"], 30.0)
            evt = self._requete(tcp, d, None, "RSU_EVENT")      # diffusé aux régulateurs
            self.assertEqual(evt["evenement"], "ACCORD")

            ville = Ville.generer()
            dens = ville.densites(8)
            res = Mission(ville, dens, r["itineraires"]).executer()
            h = self._requete(tcp, d, {"type": "MISSION_RESULT", "mission": "t1", "vehicule": "SAMU",
                                       "depart": "B2", "arrivee": "G5", "heure": 8, "resultats": res},
                              "HISTORY")
            self.assertEqual(h["lignes"][0]["mission"], "t1")
            self.assertGreater(h["lignes"][0]["gain_s"], 0)

            err = self._requete(tcp, d, {"type": "COMPUTE_ROUTES", "depart": "Z9", "arrivee": "A1"}, "ERROR")
            self.assertIn("inconnue", err["message"])
        finally:
            tcp.close()
            udp.close()


if __name__ == "__main__":
    unittest.main()
