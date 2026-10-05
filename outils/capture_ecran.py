"""Démonstration automatique : serveur + client, mission complète, captures d'écran.

    python -m outils.capture_ecran [dossier_sortie]

Utile pour vérifier l'application sans écran (QT_QPA_PLATFORM=offscreen) et pour
préparer les illustrations du rapport.
"""

import os
import sys
import tempfile
import threading

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from client.fenetre import FenetrePrincipale
from serveur.serveur import CentreRegulation


def main():
    sortie = sys.argv[1] if len(sys.argv) > 1 else "captures"
    os.makedirs(sortie, exist_ok=True)
    base = os.path.join(tempfile.mkdtemp(), "demo.db")
    serveur = CentreRegulation("127.0.0.1", 0, 0, base)
    serveur.demarrer()
    threading.Thread(target=serveur.executer, daemon=True).start()
    serveur.pret.wait(5)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    f = FenetrePrincipale("127.0.0.1", serveur.port_tcp)
    f.resize(1500, 940)
    f.show()
    f.curseur_heure.setValue(8)
    f.connecter()
    etat = {"capture_mi_parcours": False}

    def capturer(nom):
        chemin = os.path.join(sortie, nom)
        f.grab().save(chemin)
        print("capture :", chemin)

    def etape_calcul():
        f._calculer()
        QTimer.singleShot(800, etape_lancer)

    def etape_lancer():
        capturer("1_itineraires.png")
        f.combo_vitesse.setCurrentIndex(4)       # x20
        f._lancer_mission()
        f.travailleur.termine.connect(lambda _: QTimer.singleShot(800, etape_fin))

    def surveiller():
        if f.travailleur is not None and not etat["capture_mi_parcours"]:
            v = f.travailleur
            if v.isRunning() and f.label_horloge.text() and "1 min" in f.label_horloge.text():
                etat["capture_mi_parcours"] = True
                capturer("2_mission_en_cours.png")

    def etape_fin():
        capturer("3_resultats.png")
        f._lancer_analyse()
        f.analyse.finished.connect(lambda: QTimer.singleShot(300, etape_analyse))

    def etape_analyse():
        capturer("4_analyse_horaire.png")
        f.onglets.setCurrentIndex(0)
        capturer("5_journal_reseau.png")
        f.onglets.setCurrentIndex(1)
        capturer("6_historique.png")
        print(f.journal.toPlainText()[-3000:])
        f.close()
        serveur.arreter()
        app.quit()

    minuterie = QTimer()
    minuterie.timeout.connect(surveiller)
    minuterie.start(50)
    QTimer.singleShot(1500, etape_calcul)
    QTimer.singleShot(120000, app.quit)      # garde-fou
    app.exec()


if __name__ == "__main__":
    main()
