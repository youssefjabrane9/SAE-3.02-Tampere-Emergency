"""Fenêtre principale du client : choix du trajet à gauche, carte de la ville à droite.

Départ : l'hôpital ou le commissariat.
Arrivée : une adresse (rue ou lieu) ou un clic sur la carte.
La fenêtre ne connaît que des messages du protocole (des dict) :
- en TCP, elle reçoit par traiter_message() : "CITY", "TRAFFIC", "ROUTES", "HISTORY", "ERROR"
  et envoie par self.reseau.envoyer() : "GET_CITY", "GET_TRAFFIC", "COMPUTE_ROUTE", "GET_HISTORY" ;
- en UDP (étape 7), elle envoie "PRIORITY_REQUEST" aux carrefours par self.v2i.envoyer()
  et reçoit leur réponse par reponse_carrefour() : "PRIORITY_GRANT" ou "PRIORITY_DENY".
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QMainWindow,
                             QMessageBox, QPushButton, QSpinBox, QWidget)

from client.carte import MODES, NOMS_MODE, Carte, en_minutes
from client.graphiques import GraphiqueTemps
from client.reseau import ClientV2I
from sae.protocole import PORT_UDP

# Les véhicules d'urgence partent d'un de ces lieux (noms de "lieux" dans le message CITY)
DEPARTS = ["Hôpital Pasteur", "Commissariat de police"]
TEXTE_CLIC = "point choisi sur la carte"     # écrit dans le champ Arrivée après un clic


class FenetrePrincipale(QMainWindow):
    def __init__(self, reseau):
        super().__init__()
        self.setWindowTitle("SAÉ 3.02 — Véhicules prioritaires")
        self.reseau = reseau
        self.point_clique = None                   # dernier noeud cliqué sur la carte
        self.noms = {}                             # noeud -> nom de lieu ou de rue (pour l'historique)
        self.v2i = ClientV2I(reseau.hote, PORT_UDP)   # UDP vers les carrefours, même machine que le serveur

        # --- Widgets ---
        self.carte = Carte()
        self.choix_depart = QComboBox()
        self.choix_arrivee = QComboBox()
        self.choix_arrivee.setEditable(True)       # on peut taper : "bru" propose "Rue Bruat"
        self.choix_arrivee.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)   # le texte tapé n'ajoute rien
        self.choix_arrivee.completer().setFilterMode(Qt.MatchFlag.MatchContains)  # cherche partout dans le nom
        self.choix_arrivee.lineEdit().setPlaceholderText("adresse ou clic sur la carte")
        self.choix_heure = QSpinBox()
        self.choix_heure.setRange(0, 23)
        self.choix_heure.setValue(8)
        self.choix_heure.setSuffix(" h")
        self.bouton_calculer = QPushButton("Calculer")
        self.bouton_calculer.setEnabled(False)     # tant que la ville n'est pas chargée
        self.bouton_effacer = QPushButton("Effacer")
        self.bouton_historique = QPushButton("Historique")
        self.resultat = QLabel("—")
        self.resultat.setWordWrap(True)
        legende = QLabel("Trafic : vert = fluide, orange = chargé, rouge = bouché")
        legende.setWordWrap(True)
        self.graphique = GraphiqueTemps()

        # --- Disposition : formulaire à gauche, carte à droite ---
        formulaire = QFormLayout()
        formulaire.addRow("Départ", self.choix_depart)
        formulaire.addRow("Arrivée", self.choix_arrivee)
        formulaire.addRow("Heure", self.choix_heure)
        formulaire.addRow(legende)
        formulaire.addRow(self.bouton_calculer)
        formulaire.addRow(self.bouton_effacer)
        formulaire.addRow(self.bouton_historique)
        formulaire.addRow(self.resultat)
        formulaire.addRow(self.graphique)
        panneau = QWidget()
        panneau.setLayout(formulaire)
        panneau.setFixedWidth(300)

        disposition = QHBoxLayout()
        disposition.addWidget(panneau)
        disposition.addWidget(self.carte, 1)       # 1 : la carte prend toute la place restante
        centre = QWidget()
        centre.setLayout(disposition)
        self.setCentralWidget(centre)

        # --- Signaux ---
        self.bouton_calculer.clicked.connect(self.calculer)
        self.bouton_effacer.clicked.connect(self.effacer)
        self.choix_heure.valueChanged.connect(self.demander_trafic)
        # Les marqueurs suivent ce qui est choisi (None enlève le marqueur)
        self.choix_depart.currentIndexChanged.connect(
            lambda: self.carte.marquer("depart", self.choix_depart.currentData()))
        self.choix_arrivee.currentTextChanged.connect(
            lambda: self.carte.marquer("arrivee", self.lire_arrivee()))
        self.carte.noeud_clique.connect(self.choisir_point)
        self.carte.feu_proche.connect(self.demander_priorite)
        self.bouton_historique.clicked.connect(lambda: self.reseau.envoyer({"type": "GET_HISTORY"}))
        self.v2i.message_recu.connect(self.reponse_carrefour)
        self.v2i.start()

        # --- Réseau ---
        # Connecter les signaux AVANT start(), sinon on peut rater "connecte".
        self.reseau.connecte.connect(self.quand_connecte)
        self.reseau.message_recu.connect(self.traiter_message)
        self.reseau.erreur.connect(self.afficher_erreur)
        self.reseau.finished.connect(lambda: self.bouton_calculer.setEnabled(False))  # thread terminé
        self.statusBar().showMessage(f"Connexion à {self.reseau.hote}:{self.reseau.port}…")
        self.reseau.start()

    # --- Messages reçus ---

    def quand_connecte(self):
        self.statusBar().showMessage(f"Connecté à {self.reseau.hote}:{self.reseau.port}")
        self.reseau.envoyer({"type": "GET_CITY"})

    def traiter_message(self, message):
        """Aiguille chaque message reçu selon son "type".

        try : avec PyQt6, une erreur dans une méthode appelée par un signal FERME l'appli.
        Un message incomplet (un champ qui manque...) affiche donc juste une erreur.
        """
        try:
            if message["type"] == "CITY":
                self.afficher_ville(message)
            elif message["type"] == "TRAFFIC":
                self.carte.colorer_trafic(message["densites"])
            elif message["type"] == "ROUTES":
                self.afficher_routes(message)
            elif message["type"] == "HISTORY":
                self.afficher_historique(message["simulations"])
            elif message["type"] == "ERROR":
                self.afficher_erreur(message["raison"])
        except (KeyError, ValueError, TypeError) as e:
            self.afficher_erreur(f"message {message['type']} incomplet ({e})")

    def afficher_ville(self, message):
        self.carte.dessiner_ville(message)
        for nom in DEPARTS:
            self.choix_depart.addItem(nom, message["lieux"][nom])   # le noeud est caché derrière le nom
        adresses = {**message["lieux"], **message["rues"]}         # nom -> noeud
        for nom in sorted(adresses):
            self.choix_arrivee.addItem(nom, adresses[nom])
        self.choix_arrivee.setCurrentIndex(-1)     # champ vide au départ
        # L'inverse (noeud -> nom), pour l'historique. Les lieux en dernier : si un lieu et
        # une rue ont le même noeud, on garde "Hôpital Pasteur" plutôt que le nom de sa rue.
        for nom, noeud in message["rues"].items():
            self.noms[noeud] = nom
        for nom, noeud in message["lieux"].items():
            self.noms[noeud] = nom
        self.bouton_calculer.setEnabled(True)
        self.demander_trafic()

    def afficher_routes(self, message):
        """Les 3 trajets (message "ROUTES") : chemins en couleur, véhicules animés, graphique."""
        self.carte.effacer_trajets()
        lignes = []
        for mode in MODES:
            trajet = message[mode]
            self.carte.dessiner_chemin(trajet["chemin"], mode)
            lignes.append(f'{NOMS_MODE[mode]} : {trajet["distance"]:.0f} m, {en_minutes(trajet["temps"])}')
        gain = message["classique"]["temps"] - message["priorite"]["temps"]
        lignes.append(f"Gain de la priorité : {en_minutes(gain)}")
        self.resultat.setText("\n".join(lignes))
        self.graphique.afficher({mode: message[mode]["temps"] for mode in MODES})
        self.carte.animer({mode: (message[mode]["chemin"], message[mode]["temps_noeuds"])
                           for mode in MODES})

    def afficher_erreur(self, texte):
        self.resultat.setText(f"Erreur : {texte}")

    def afficher_historique(self, simulations):
        """Les 10 dernières simulations enregistrées par le serveur, dans une petite fenêtre."""
        lignes = []
        for s in simulations[-10:]:
            depart = self.noms.get(s["depart"], "point de la carte")
            arrivee = self.noms.get(s["arrivee"], "point de la carte")
            lignes.append(f"{s['heure']} h, {depart} → {arrivee} : classique {en_minutes(s['classique'])}, "
                          f"trafic {en_minutes(s['trafic'])}, priorité {en_minutes(s['priorite'])}")
        QMessageBox.information(self, "Historique", "\n".join(lignes) or "Aucune simulation pour l'instant.")

    # --- Étape 7 : priorité aux feux (UDP) ---

    def demander_priorite(self, feu):
        """Le véhicule prioritaire approche d'un feu : il demande le vert au carrefour."""
        self.v2i.envoyer({"type": "PRIORITY_REQUEST", "feu": feu})

    def reponse_carrefour(self, message):
        """Réponse UDP d'un carrefour : si la priorité est accordée, son feu passe au vert."""
        if message["type"] == "PRIORITY_GRANT":
            self.carte.accorder_priorite(message.get("feu"))

    # --- Actions de l'utilisateur ---

    def demander_trafic(self):
        """Demande au serveur le trafic de l'heure choisie (au chargement et à chaque changement)."""
        self.reseau.envoyer({"type": "GET_TRAFFIC", "heure": self.choix_heure.value()})

    def choisir_point(self, noeud):
        """Clic sur la carte : ce point de rue devient l'arrivée."""
        self.point_clique = noeud
        self.choix_arrivee.setEditText(TEXTE_CLIC)
        self.carte.marquer("arrivee", noeud)       # même si le texte était déjà TEXTE_CLIC

    def lire_arrivee(self):
        """Traduit le texte du champ Arrivée en noeud, ou None si on ne le comprend pas.

        2 cas : le point cliqué, ou une adresse de la liste.
        """
        texte = self.choix_arrivee.currentText()
        if texte == TEXTE_CLIC:
            return self.point_clique
        index = self.choix_arrivee.findText(texte)
        if index >= 0:
            return self.choix_arrivee.itemData(index)
        return None                                 # texte qui n'est pas dans la liste

    def calculer(self):
        arrivee = self.lire_arrivee()
        if arrivee is None:
            self.afficher_erreur("arrivée inconnue : choisissez une adresse de la liste "
                                 "ou cliquez sur la carte")
            return
        self.reseau.envoyer({
            "type": "COMPUTE_ROUTE",
            "depart": self.choix_depart.currentData(),   # l'identifiant du noeud, pas le nom
            "arrivee": arrivee,
            "heure": self.choix_heure.value(),
        })

    def effacer(self):
        """Bouton Effacer : enlève les trajets, les véhicules, les résultats et le graphique."""
        self.carte.effacer_trajets()
        self.resultat.setText("—")
        self.graphique.afficher({})

    def closeEvent(self, event):
        """À la fermeture : arrêter proprement les deux threads réseau avant de quitter."""
        for liaison in (self.reseau, self.v2i):
            liaison.arreter()
            liaison.wait()
        super().closeEvent(event)
