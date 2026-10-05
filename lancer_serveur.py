"""Lance le centre de régulation (serveur TCP + carrefours connectés UDP).

    python lancer_serveur.py [--hote 0.0.0.0] [--port 5050] [--udp 5051] [--base sae_missions.db]
"""

import argparse
import logging

from sae.protocole import PORT_TCP, PORT_UDP
from serveur.serveur import CentreRegulation


def main():
    p = argparse.ArgumentParser(description="Centre de régulation SAE 3.02")
    p.add_argument("--hote", default="0.0.0.0")
    p.add_argument("--port", type=int, default=PORT_TCP)
    p.add_argument("--udp", type=int, default=PORT_UDP)
    p.add_argument("--base", default="sae_missions.db")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    serveur = CentreRegulation(a.hote, a.port, a.udp, a.base)
    try:
        serveur.executer()
    except KeyboardInterrupt:
        serveur.arreter()


if __name__ == "__main__":
    main()
