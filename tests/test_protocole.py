"""Tests du contrat. Lancez-les avant chaque merge : python -m unittest test_protocole.py"""

import unittest

from sae import protocole as p


class TestProtocole(unittest.TestCase):

    def test_aller_retour(self):
        # Chaque exemple du catalogue doit survivre à encoder puis décoder.
        for exemple in (p.EXEMPLE_GET_CITY, p.EXEMPLE_CITY, p.EXEMPLE_COMPUTE_ROUTE,
                        p.EXEMPLE_ROUTE, p.EXEMPLE_ERROR):
            octets = p.encoder(exemple)
            self.assertTrue(octets.endswith(b"\n"))
            self.assertEqual(p.decoder(octets[:-1]), exemple)

    def test_types_connus(self):
        for exemple in (p.EXEMPLE_GET_CITY, p.EXEMPLE_CITY, p.EXEMPLE_COMPUTE_ROUTE,
                        p.EXEMPLE_ROUTE, p.EXEMPLE_ERROR):
            self.assertIn(exemple["type"], p.TYPES_CONNUS)

    def test_message_coupe_en_deux(self):
        # TCP peut livrer un message en plusieurs morceaux.
        octets = p.encoder(p.EXEMPLE_ROUTE)
        d = p.Deframeur()
        self.assertEqual(d.alimenter(octets[:10]), [])
        self.assertEqual(d.alimenter(octets[10:]), [p.EXEMPLE_ROUTE])

    def test_deux_messages_colles(self):
        # ... ou deux messages dans un seul recv().
        octets = p.encoder(p.EXEMPLE_GET_CITY) + p.encoder(p.EXEMPLE_ROUTE)
        d = p.Deframeur()
        self.assertEqual(d.alimenter(octets), [p.EXEMPLE_GET_CITY, p.EXEMPLE_ROUTE])

    def test_accents(self):
        msg = {"type": "ERROR", "raison": "carrefour fermé"}
        self.assertEqual(p.Deframeur().alimenter(p.encoder(msg)), [msg])

    def test_message_invalide(self):
        with self.assertRaises(ValueError):
            p.decoder(b'{"pas_de_type": 1}')
        with self.assertRaises(ValueError):
            p.decoder(b"[1, 2, 3]")


if __name__ == "__main__":
    unittest.main()
