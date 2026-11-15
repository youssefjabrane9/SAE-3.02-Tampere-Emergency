"""Fenêtre principale du client : choix du trajet à gauche, carte de la ville à droite.

Départ : l'hôpital ou le commissariat.
Arrivée : un lieu (gare, musée...) ou une rue choisi dans une liste, ou un clic sur la carte.
La fenêtre ne connaît que des messages du protocole (des dict) :
- en TCP, elle reçoit par traiter_message() : "CITY", "TRAFFIC", "ROUTES", "HISTORY", "ERROR"
  et envoie par self.reseau.envoyer() : "GET_CITY", "GET_TRAFFIC", "COMPUTE_ROUTE", "GET_HISTORY" ;
- en UDP, elle envoie "PRIORITY_REQUEST" aux carrefours par self.v2i.envoyer()
  et reçoit leur réponse par reponse_carrefour() : "PRIORITY_GRANT" ou "PRIORITY_DENY".
"""

from PyQt6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QMainWindow,
                             QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from client.carte import MODES, NOMS_MODE, Carte, en_minutes
from client.graphiques import GraphiqueTemps
from client.reseau import ClientV2I
from commun.protocole import PORT_UDP

# Les véhicules d'urgence partent d'un de ces lieux (noms de "lieux" dans le message CITY)
DEPARTS = ["Hôpital Pasteur", "Commissariat de police"]
TEXTE_CLIC = "Point cliqué sur la carte"    # 1re ligne de la liste Arrivée


class FenetrePrincipale(QMainWindow):
    """Fenêtre principale : formulaire du trajet à gauche, carte de Colmar à droite.

    Elle ne connaît que des messages du protocole (des dict), reçus et envoyés par
    ClientReseau (TCP) et ClientV2I (UDP).

    Attributes:
        reseau (ClientReseau): liaison TCP avec le serveur.
        v2i (ClientV2I): liaison UDP avec les carrefours.
        carte (Carte): la carte de la ville.
    """
    def __init__(self, reseau):
        """Crée les widgets, branche les signaux et démarre les deux threads réseau.

        Args:
            reseau (ClientReseau): liaison TCP, pas encore démarrée.
        """
        super().__init__()
        self.setWindowTitle("SAÉ 3.02 — Véhicules prioritaires")
        self.reseau = reseau
        self.noms = {}                             # noeud -> nom du lieu ou de la rue (pour l'historique)
        self.v2i = ClientV2I(reseau.hote, PORT_UDP)   # UDP vers les carrefours, même machine que le serveur

        # --- Widgets ---
        self.carte = Carte()
        self.choix_depart = QComboBox()
        self.choix_arrivee = QComboBox()
        self.choix_heure = QSpinBox()
        self.choix_heure.setRange(0, 23)
        self.choix_heure.setValue(8)
        self.choix_heure.setSuffix(" h")
        self.bouton_calculer = QPushButton("Calculer")
        self.bouton_calculer.setEnabled(False)     # tant que la ville n'est pas chargée
        self.bouton_historique = QPushButton("Historique")
        self.resultat = QLabel("—")
        self.resultat.setWordWrap(True)
        # Légende sur une ligne : un carré de la couleur des routes devant chaque mot (QLabel comprend le HTML)
        legende = QLabel('Trafic : <span style="color:#2e7d32">■</span> fluide  '
                         '<span style="color:#f57c00">■</span> chargé  '
                         '<span style="color:#d32f2f">■</span> bouché')
        self.graphique = GraphiqueTemps()

        # --- Disposition : panneau à gauche (formulaire puis le reste en colonne), carte à droite ---
        formulaire = QFormLayout()
        formulaire.addRow("Départ", self.choix_depart)
        formulaire.addRow("Arrivée", self.choix_arrivee)
        formulaire.addRow("Heure", self.choix_heure)
        colonne = QVBoxLayout()                    # chaque widget prend la hauteur dont il a besoin
        colonne.addLayout(formulaire)
        colonne.addWidget(legende)
        colonne.addWidget(self.bouton_calculer)
        colonne.addWidget(self.bouton_historique)
        colonne.addWidget(self.resultat)
        colonne.addWidget(self.graphique)
        colonne.addStretch()                       # l'espace en trop va en bas, pas entre les widgets
        panneau = QWidget()
        panneau.setLayout(colonne)
        panneau.setFixedWidth(300)

        disposition = QHBoxLayout()
        disposition.addWidget(panneau)
        disposition.addWidget(self.carte, 1)       # 1 : la carte prend toute la place restante
        centre = QWidget()
        centre.setLayout(disposition)
        self.setCentralWidget(centre)

        # --- Signaux ---
        self.bouton_calculer.clicked.connect(self.calculer)
        self.choix_heure.valueChanged.connect(self.demander_trafic)
        # Les marqueurs suivent ce qui est choisi dans les listes
        self.choix_depart.currentIndexChanged.connect(self.marquer_depart)
        self.choix_arrivee.currentIndexChanged.connect(self.marquer_arrivee)
        self.carte.noeud_clique.connect(self.choisir_point)
        self.carte.feu_proche.connect(self.demander_priorite)
        self.bouton_historique.clicked.connect(self.demander_historique)
        self.v2i.message_recu.connect(self.reponse_carrefour)
        self.v2i.start()

        # --- Réseau ---
        # Connecter les signaux AVANT start(), sinon on peut rater "connecte".
        self.reseau.connecte.connect(self.quand_connecte)
        self.reseau.message_recu.connect(self.traiter_message)
        self.reseau.erreur.connect(self.afficher_erreur)
        self.reseau.finished.connect(self.quand_deconnecte)    # le thread TCP s'est terminé
        self.statusBar().showMessage(f"Connexion à {self.reseau.hote}:{self.reseau.port}…")
        self.reseau.start()

    # --- Messages reçus ---

    def quand_connecte(self):
        """Connexion établie : l'affiche en bas de la fenêtre et demande la ville (GET_CITY)."""
        self.statusBar().showMessage(f"Connecté à {self.reseau.hote}:{self.reseau.port}")
        self.reseau.envoyer({"type": "GET_CITY"})

    def quand_deconnecte(self):
        """Le thread TCP s'est terminé : on ne peut plus calculer de trajet."""
        self.bouton_calculer.setEnabled(False)

    def traiter_message(self, message):
        """Aiguille chaque message reçu du serveur selon son "type".

        Avec PyQt6, une erreur dans une méthode appelée par un signal ferme l'application :
        un message incomplet affiche donc seulement une erreur.

        Args:
            message (dict): "CITY", "TRAFFIC", "ROUTES", "HISTORY" ou "ERROR".
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
        """Dessine la ville, remplit les listes Départ et Arrivée, puis demande le trafic.

        La liste Arrivée contient : la ligne du point cliqué (vide tant qu'on n'a pas cliqué),
        puis les lieux, un trait, et les rues (chaque partie dans l'ordre alphabétique).

        Args:
            message (dict): message "CITY", avec "lieux" et "rues" (nom -> noeud).
        """
        self.carte.dessiner_ville(message)
        lieux = message["lieux"]
        rues = message["rues"]
        for nom in DEPARTS:
            self.choix_depart.addItem(nom, lieux[nom])     # le noeud est caché derrière le nom
        self.choix_arrivee.addItem(TEXTE_CLIC, None)       # None : pas encore de clic
        for nom in sorted(lieux):
            self.choix_arrivee.addItem(nom, lieux[nom])
        self.choix_arrivee.insertSeparator(self.choix_arrivee.count())   # trait entre lieux et rues
        for nom in sorted(rues):
            self.choix_arrivee.addItem(nom, rues[nom])
        self.choix_arrivee.setCurrentIndex(1)              # le premier lieu, pas la ligne du clic
        # L'inverse (noeud -> nom), pour l'historique. Les lieux en dernier : si un lieu et
        # une rue ont le même noeud, on garde le nom du lieu (ex. "Hôpital Pasteur").
        for nom in sorted(rues):
            self.noms[rues[nom]] = nom
        for nom in sorted(lieux):
            self.noms[lieux[nom]] = nom
        self.bouton_calculer.setEnabled(True)
        self.demander_trafic()

    def afficher_routes(self, message):
        """Affiche les 3 trajets : chemins en couleur, temps, gain de la priorité, graphique et véhicules.

        Args:
            message (dict): message "ROUTES", avec un trajet par stratégie ("chemin", "distance",
                "temps", "temps_noeuds").
        """
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
        """Affiche une erreur dans la zone des résultats.

        Args:
            texte (str): la phrase à afficher.
        """
        self.resultat.setText(f"Erreur : {texte}")

    def afficher_historique(self, simulations):
        """Montre les 10 dernières simulations dans une petite fenêtre.

        Args:
            simulations (list[dict]): champ "simulations" du message "HISTORY".
        """
        lignes = []
        for s in simulations[-10:]:
            depart = self.noms.get(s["depart"], "point de la carte")
            arrivee = self.noms.get(s["arrivee"], "point de la carte")
            lignes.append(f"{s['heure']} h, {depart} → {arrivee} : classique {en_minutes(s['classique'])}, "
                          f"trafic {en_minutes(s['trafic'])}, priorité {en_minutes(s['priorite'])}")
        QMessageBox.information(self, "Historique", "\n".join(lignes) or "Aucune simulation pour l'instant.")

    # --- Priorité aux feux (UDP) ---

    def demander_priorite(self, feu):
        """Le véhicule prioritaire approche d'un feu : demande le vert au carrefour en UDP.

        Args:
            feu (str): identifiant du feu.
        """
        self.v2i.envoyer({"type": "PRIORITY_REQUEST", "feu": feu})

    def reponse_carrefour(self, message):
        """Traite la réponse UDP d'un carrefour : si la priorité est accordée, ouvre le feu.

        Args:
            message (dict): "PRIORITY_GRANT" ou "PRIORITY_DENY".
        """
        if message["type"] == "PRIORITY_GRANT":
            self.carte.accorder_priorite(message.get("feu"))

    # --- Actions de l'utilisateur ---

    def demander_trafic(self):
        """Demande au serveur le trafic de l'heure choisie (GET_TRAFFIC)."""
        self.reseau.envoyer({"type": "GET_TRAFFIC", "heure": self.choix_heure.value()})

    def demander_historique(self):
        """Bouton Historique : demande au serveur les simulations passées (GET_HISTORY)."""
        self.reseau.envoyer({"type": "GET_HISTORY"})

    def marquer_depart(self):
        """Place le marqueur de départ sur le lieu choisi dans la liste Départ."""
        self.carte.marquer("depart", self.choix_depart.currentData())

    def marquer_arrivee(self):
        """Place le marqueur d'arrivée sur le lieu ou la rue choisi dans la liste Arrivée."""
        self.carte.marquer("arrivee", self.choix_arrivee.currentData())

    def choisir_point(self, noeud):
        """Clic sur la carte : range le noeud dans la ligne « Point cliqué » et la sélectionne.

        Args:
            noeud (str): noeud le plus proche du clic.
        """
        self.choix_arrivee.setItemData(0, noeud)
        self.choix_arrivee.setCurrentIndex(0)
        self.marquer_arrivee()     # utile si la ligne était déjà sélectionnée (2e clic)

    def calculer(self):
        """Bouton Calculer : envoie COMPUTE_ROUTE au serveur avec le départ, l'arrivée et l'heure."""
        if self.choix_arrivee.currentData() is None:
            self.afficher_erreur("cliquez d'abord sur la carte, ou choisissez une arrivée dans la liste")
            return
        self.reseau.envoyer({
            "type": "COMPUTE_ROUTE",
            "depart": self.choix_depart.currentData(),     # l'identifiant du noeud, pas le nom
            "arrivee": self.choix_arrivee.currentData(),
            "heure": self.choix_heure.value(),
        })

    def closeEvent(self, event):
        """À la fermeture : arrête proprement les deux threads réseau avant de quitter.

        Args:
            event (QCloseEvent): événement envoyé par Qt.
        """
        for liaison in (self.reseau, self.v2i):
            liaison.arreter()
            liaison.wait()
        super().closeEvent(event)
