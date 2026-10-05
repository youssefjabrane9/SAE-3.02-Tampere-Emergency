"""Fenêtre principale du client : choix du trajet à gauche, carte de la ville à droite.

La fenêtre ne connaît que des messages du protocole (des dict) :
- elle en reçoit par traiter_message() : "CITY", "ROUTE", "ERROR" ;
- elle en envoie par self.reseau.envoyer() : "GET_CITY", "COMPUTE_ROUTE".
"""

from PyQt6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QMainWindow,
                             QPushButton, QSpinBox, QWidget)

from client.carte import CarteVille


class FenetrePrincipale(QMainWindow):
    def __init__(self, reseau):
        super().__init__()
        self.setWindowTitle("SAÉ 3.02 — Véhicules prioritaires")
        self.reseau = reseau

        # --- Widgets ---
        self.carte = CarteVille()
        self.choix_depart = QComboBox()
        self.choix_arrivee = QComboBox()
        self.choix_heure = QSpinBox()
        self.choix_heure.setRange(0, 23)
        self.choix_heure.setSuffix(" h")
        self.bouton_calculer = QPushButton("Calculer")
        self.bouton_calculer.setEnabled(False)     # tant que la ville n'est pas chargée
        self.resultat = QLabel("—")
        self.resultat.setWordWrap(True)

        # --- Disposition : formulaire à gauche, carte à droite ---
        formulaire = QFormLayout()
        formulaire.addRow("Départ", self.choix_depart)
        formulaire.addRow("Arrivée", self.choix_arrivee)
        formulaire.addRow("Heure", self.choix_heure)
        formulaire.addRow(self.bouton_calculer)
        formulaire.addRow(self.resultat)
        panneau = QWidget()
        panneau.setLayout(formulaire)
        panneau.setFixedWidth(220)

        disposition = QHBoxLayout()
        disposition.addWidget(panneau)
        disposition.addWidget(self.carte, 1)       # 1 : la carte prend toute la place restante
        centre = QWidget()
        centre.setLayout(disposition)
        self.setCentralWidget(centre)

        self.bouton_calculer.clicked.connect(self.calculer)

        # --- Réseau ---
        # Connecter les signaux AVANT start(), sinon on peut rater "connecte".
        self.reseau.connecte.connect(self.quand_connecte)
        self.reseau.message_recu.connect(self.traiter_message)
        self.reseau.erreur.connect(self.afficher_erreur)
        self.reseau.finished.connect(self.quand_deconnecte)   # signal fourni par QThread
        self.statusBar().showMessage(f"Connexion à {self.reseau.hote}:{self.reseau.port}…")
        self.reseau.start()

    # --- Messages reçus ---

    def quand_connecte(self):
        self.statusBar().showMessage(f"Connecté à {self.reseau.hote}:{self.reseau.port}")
        self.reseau.envoyer({"type": "GET_CITY"})

    def quand_deconnecte(self):
        """Le thread réseau est terminé (serveur absent ou coupé) : plus rien ne peut être envoyé."""
        self.bouton_calculer.setEnabled(False)

    def traiter_message(self, message):
        """Aiguille chaque message reçu selon son "type"."""
        if message["type"] == "CITY":
            self.afficher_ville(message)
        elif message["type"] == "ROUTE":
            self.afficher_route(message)
        elif message["type"] == "ERROR":
            self.afficher_erreur(message["raison"])
        else:
            self.statusBar().showMessage(f"Message ignoré : {message['type']}")

    def afficher_ville(self, message):
        self.carte.charger_ville(message)
        noms = sorted(message["noeuds"])
        self.choix_depart.clear()
        self.choix_depart.addItems(noms)
        self.choix_arrivee.clear()
        self.choix_arrivee.addItems(noms)
        self.choix_arrivee.setCurrentIndex(len(noms) - 1)   # arrivée ≠ départ par défaut
        self.bouton_calculer.setEnabled(True)

    def afficher_route(self, message):
        self.carte.effacer_trajets()
        self.carte.afficher_trajet(message)
        self.resultat.setText(f"{' → '.join(message['chemin'])}\n"
                              f"{message['distance']} m — {message['temps']:.1f} s")

    def afficher_erreur(self, texte):
        self.resultat.setText(f"Erreur : {texte}")
        self.statusBar().showMessage(f"Erreur : {texte}")

    # --- Actions de l'utilisateur ---

    def calculer(self):
        self.reseau.envoyer({
            "type": "COMPUTE_ROUTE",
            "depart": self.choix_depart.currentText(),
            "arrivee": self.choix_arrivee.currentText(),
            "heure": self.choix_heure.value(),
        })

    def closeEvent(self, event):
        """À la fermeture : arrêter proprement le thread réseau avant de quitter."""
        self.reseau.arreter()
        self.reseau.wait()
        super().closeEvent(event)
