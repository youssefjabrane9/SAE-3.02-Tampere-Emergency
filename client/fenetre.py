"""Fenêtre principale du client : choix du trajet à gauche, carte de la ville à droite.

La fenêtre ne connaît que des messages du protocole (des dict) :
- elle en reçoit par traiter_message() : "CITY", "ROUTE", "ERROR" ;
- elle en envoie par self.reseau.envoyer() : "GET_CITY", "COMPUTE_ROUTE".
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QCompleter, QFormLayout, QHBoxLayout, QLabel,
                             QMainWindow, QPushButton, QSpinBox, QWidget)

from client.carte import CarteVille


def liste_avec_recherche():
    """Liste déroulante où l'on peut aussi taper : "bru" propose "Rue Bruat"."""
    liste = QComboBox()
    liste.setEditable(True)
    liste.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)   # le texte tapé n'ajoute rien à la liste
    liste.completer().setFilterMode(Qt.MatchFlag.MatchContains)   # cherche n'importe où dans le nom
    liste.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    return liste


class FenetrePrincipale(QMainWindow):
    def __init__(self, reseau):
        super().__init__()
        self.setWindowTitle("SAÉ 3.02 — Véhicules prioritaires")
        self.reseau = reseau

        # --- Widgets ---
        self.carte = CarteVille()
        self.choix_depart = liste_avec_recherche()
        self.choix_arrivee = liste_avec_recherche()
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
        formulaire.addRow(QLabel("Sur la carte :\nclic gauche = départ\nclic droit = arrivée"))
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
        self.carte.noeud_clique.connect(self.choisir_point)
        # Le marqueur suit le choix fait dans la liste
        self.choix_depart.currentIndexChanged.connect(
            lambda: self.carte.marquer("depart", self.choix_depart.currentData()))
        self.choix_arrivee.currentIndexChanged.connect(
            lambda: self.carte.marquer("arrivee", self.choix_arrivee.currentData()))

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
        lieux = message["lieux"]                   # nom affiché -> identifiant du noeud
        rues = message.get("rues", {})
        for liste in (self.choix_depart, self.choix_arrivee):
            liste.clear()
            for nom in sorted(lieux):
                liste.addItem(nom, lieux[nom])     # le noeud est caché derrière le nom
            liste.insertSeparator(liste.count())   # trait entre les lieux et les rues
            for nom in sorted(rues):
                liste.addItem(nom, rues[nom])
        self.choix_arrivee.setCurrentIndex(len(lieux) - 1)   # arrivée ≠ départ par défaut
        self.bouton_calculer.setEnabled(True)

    def afficher_route(self, message):
        self.carte.effacer_trajets()
        self.carte.afficher_trajet(message)
        self.resultat.setText(f"{self.choix_depart.currentText()} → {self.choix_arrivee.currentText()}\n"
                              f"{message['distance']:.0f} m — {message['temps']:.1f} s")

    def afficher_erreur(self, texte):
        self.resultat.setText(f"Erreur : {texte}")
        self.statusBar().showMessage(f"Erreur : {texte}")

    # --- Actions de l'utilisateur ---

    def choisir_point(self, noeud, role):
        """Un clic sur la carte devient l'entrée "Point choisi sur la carte" de la liste."""
        liste = self.choix_depart if role == "depart" else self.choix_arrivee
        nom = "Point sur la carte"
        index = liste.findText(nom)
        if index == -1:
            liste.addItem(nom, noeud)
            index = liste.count() - 1
        else:
            liste.setItemData(index, noeud)    # on remplace le point précédent
        liste.setCurrentIndex(index)
        self.carte.marquer(role, noeud)        # au cas où l'index n'a pas changé

    def noeud_choisi(self, liste):
        """Identifiant du noeud derrière le texte de la liste, ou None si le texte tapé n'existe pas."""
        index = liste.findText(liste.currentText())
        return liste.itemData(index) if index != -1 else None

    def calculer(self):
        depart = self.noeud_choisi(self.choix_depart)
        arrivee = self.noeud_choisi(self.choix_arrivee)
        if depart is None or arrivee is None:
            self.afficher_erreur("lieu ou rue inconnu : choisissez un nom proposé dans la liste")
            return
        self.reseau.envoyer({
            "type": "COMPUTE_ROUTE",
            "depart": depart,                  # l'identifiant du noeud, pas le nom
            "arrivee": arrivee,
            "heure": self.choix_heure.value(),
        })

    def closeEvent(self, event):
        """À la fermeture : arrêter proprement le thread réseau avant de quitter."""
        self.reseau.arreter()
        self.reseau.wait()
        super().closeEvent(event)
