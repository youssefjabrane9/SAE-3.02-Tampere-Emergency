
"""Fenetre principale de l'application SAE 3.02."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QWidget
)

from client.carte import CarteVille


def liste_avec_recherche():
    """Creer une liste avec recherche de rue ou de lieu."""
    liste = QComboBox()
    liste.setEditable(True)
    liste.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

    liste.completer().setFilterMode(Qt.MatchFlag.MatchContains)
    liste.completer().setCompletionMode(
        QCompleter.CompletionMode.PopupCompletion
    )

    return liste


class FenetrePrincipale(QMainWindow):

    def __init__(self, reseau):
        super().__init__()

        self.setWindowTitle("SAE 3.02 - Vehicules prioritaires")
        self.reseau = reseau

        # Carte de Colmar
        self.carte = CarteVille()

        # Choix du trajet
        self.choix_depart = liste_avec_recherche()
        self.choix_arrivee = liste_avec_recherche()

        self.choix_heure = QSpinBox()
        self.choix_heure.setRange(0, 23)
        self.choix_heure.setSuffix(" h")
        self.choix_heure.setValue(8)

        # Bouton calculer
        self.bouton_calculer = QPushButton("Calculer")
        self.bouton_calculer.setEnabled(False)

        # Resultats
        self.resultat = QLabel("Choisissez un trajet")
        self.resultat.setWordWrap(True)

        # Formulaire de gauche
        formulaire = QFormLayout()
        formulaire.addRow("Depart", self.choix_depart)
        formulaire.addRow("Arrivee", self.choix_arrivee)
        formulaire.addRow("Heure", self.choix_heure)

        formulaire.addRow(
            QLabel(
                "Sur la carte :\n"
                "clic gauche = depart\n"
                "clic droit = arrivee"
            )
        )

        formulaire.addRow(self.bouton_calculer)
        formulaire.addRow(self.resultat)

        panneau = QWidget()
        panneau.setLayout(formulaire)
        panneau.setFixedWidth(250)

        # Disposition principale
        disposition = QHBoxLayout()
        disposition.addWidget(panneau)
        disposition.addWidget(self.carte, 1)

        centre = QWidget()
        centre.setLayout(disposition)
        self.setCentralWidget(centre)

        # Actions des boutons et de la carte
        self.bouton_calculer.clicked.connect(self.calculer)
        self.carte.noeud_clique.connect(self.choisir_point)

        self.choix_depart.currentIndexChanged.connect(
            lambda: self.carte.marquer(
                "depart", self.choix_depart.currentData()
            )
        )

        self.choix_arrivee.currentIndexChanged.connect(
            lambda: self.carte.marquer(
                "arrivee", self.choix_arrivee.currentData()
            )
        )

        # Communication avec le serveur
        self.reseau.connecte.connect(self.quand_connecte)
        self.reseau.message_recu.connect(self.traiter_message)
        self.reseau.erreur.connect(self.afficher_erreur)
        self.reseau.finished.connect(self.quand_deconnecte)

        self.statusBar().showMessage(
            f"Connexion a {self.reseau.hote}:{self.reseau.port}"
        )

        self.reseau.start()

    # Connexion au serveur
    def quand_connecte(self):
        self.statusBar().showMessage("Connecte au serveur")
        self.reseau.envoyer({"type": "GET_CITY"})

    def quand_deconnecte(self):
        self.bouton_calculer.setEnabled(False)
        self.statusBar().showMessage("Serveur deconnecte")

    # Recevoir les messages
    def traiter_message(self, message):
        type_message = message.get("type")

        if type_message == "CITY":
            self.afficher_ville(message)

        elif type_message == "ROUTE":
            self.afficher_route(message)

        elif type_message == "ERROR":
            self.afficher_erreur(message.get("raison", "Erreur inconnue"))

    # Afficher la carte de Colmar
    def afficher_ville(self, message):
        self.carte.charger_ville(message)

        lieux = message["lieux"]
        rues = message.get("rues", {})

        for liste in (self.choix_depart, self.choix_arrivee):
            liste.clear()

            for nom in sorted(lieux):
                liste.addItem(nom, lieux[nom])

            liste.insertSeparator(liste.count())

            for nom in sorted(rues):
                liste.addItem(nom, rues[nom])

        self.choix_arrivee.setCurrentIndex(len(lieux) - 1)
        self.bouton_calculer.setEnabled(True)

    # Afficher les trois strategies
    def afficher_route(self, message):

        self.carte.effacer_trajets()

        strategies = message.get("strategies")

        # Compatibilite avec l'ancien serveur
        if not strategies:
            self.carte.afficher_trajet(message)

            self.resultat.setText(
                f"Distance : {message['distance']:.0f} m\n"
                f"Temps : {message['temps']:.1f} s"
            )
            return

        # Couleurs des itineraires
        couleurs = {
            "classique": QColor("blue"),
            "trafic": QColor("orange"),
            "prioritaire": QColor("green")
        }

        noms = {
            "classique": "Classique",
            "trafic": "Trafic",
            "prioritaire": "Prioritaire"
        }

        lignes = [
            "Comparaison des itineraires",
            "",
            f"Trafic : {message.get('trafic', 'inconnu')}",
            ""
        ]

        # Dessiner les trois trajets
        for nom in ("classique", "trafic", "prioritaire"):

            trajet = strategies.get(nom)

            if trajet is None:
                continue

            self.carte.afficher_trajet(
                trajet,
                couleurs[nom]
            )

            lignes.append(
                f"{noms[nom]} :\n"
                f"{trajet['distance']:.0f} m - "
                f"{trajet['temps']:.1f} s\n"
            )

        self.resultat.setText("\n".join(lignes))

    # Afficher une erreur
    def afficher_erreur(self, texte):
        self.resultat.setText(f"Erreur : {texte}")
        self.statusBar().showMessage(f"Erreur : {texte}")

    # Choisir un point sur la carte
    def choisir_point(self, noeud, role):

        liste = (
            self.choix_depart
            if role == "depart"
            else self.choix_arrivee
        )

        nom = "Point sur la carte"
        index = liste.findText(nom)

        if index == -1:
            liste.addItem(nom, noeud)
            index = liste.count() - 1
        else:
            liste.setItemData(index, noeud)

        liste.setCurrentIndex(index)
        self.carte.marquer(role, noeud)

    # Recuperer le noeud selectionne
    def noeud_choisi(self, liste):

        index = liste.findText(liste.currentText())

        if index == -1:
            return None

        return liste.itemData(index)

    # Demander le calcul au serveur
    def calculer(self):

        depart = self.noeud_choisi(self.choix_depart)
        arrivee = self.noeud_choisi(self.choix_arrivee)

        if depart is None or arrivee is None:
            self.afficher_erreur(
                "Choisissez un depart et une arrivee valides"
            )
            return

        self.reseau.envoyer({
            "type": "COMPUTE_ROUTE",
            "depart": depart,
            "arrivee": arrivee,
            "heure": self.choix_heure.value()
        })

    # Fermer correctement l'application
    def closeEvent(self, event):
        self.reseau.arreter()
        self.reseau.wait()
        super().closeEvent(event)
