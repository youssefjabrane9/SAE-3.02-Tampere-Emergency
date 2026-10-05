"""Fenêtre principale du poste du régulateur "véhicules d'urgence"."""

import datetime
import uuid

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                             QHeaderView, QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar,
                             QPushButton, QSlider, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                             QVBoxLayout, QWidget)

from sae.feux import VEHICULES, MondeFeux
from sae.itineraire import LIBELLES, MODES, PRIORITE
from sae.protocole import PORT_TCP
from sae.ville import Ville, profil_horaire

from .carte import COULEURS_MODE, CarteVille
from .graphiques import LIBELLES_COURTS, GraphiqueBarres, GraphiqueHoraire, format_temps
from .reseau import ClientTcp, LienV2I
from .travailleurs import TravailleurAnalyse, TravailleurMission

STYLE = """
QMainWindow, QWidget { font-size: 13px; }
QGroupBox { font-weight: 600; border: 1px solid #cfd8dc; border-radius: 8px; margin-top: 10px; padding-top: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #37474f; }
QPushButton { padding: 6px 12px; border-radius: 6px; border: 1px solid #b0bec5; background: #fafafa; }
QPushButton:hover { background: #eceff1; }
QPushButton:disabled { color: #9e9e9e; }
QPushButton#primaire { background: #8e24aa; color: white; border: none; font-weight: 600; }
QPushButton#primaire:hover { background: #7b1fa2; }
QPushButton#primaire:disabled { background: #ce93d8; }
QTableWidget { gridline-color: #eceff1; }
QPlainTextEdit { font-family: Consolas, 'DejaVu Sans Mono', monospace; font-size: 12px; }
"""


def niveau_charge(heure):
    p = profil_horaire(heure)
    if p < 0.35:
        return "trafic fluide"
    if p < 0.7:
        return "trafic modéré"
    return "heure de pointe"


class FenetrePrincipale(QMainWindow):
    def __init__(self, hote="127.0.0.1", port=PORT_TCP):
        super().__init__()
        self.setWindowTitle("SAE 3.02 — Optimisation du trajet des véhicules prioritaires")
        self.resize(1440, 900)
        self.setStyleSheet(STYLE)

        self.tcp = None
        self.lien = None
        self.ville = None
        self.densites = {}
        self.itineraires = []
        self.mission_id = None
        self.travailleur = None
        self.analyse = None
        self.derniers_resultats = None
        self._v2i_depart = (0, 0)

        self._construire(hote, port)
        self._minuterie_feux = QTimer(self)          # feux animés hors mission (cycle normal)
        self._minuterie_feux.timeout.connect(self._animer_feux_repos)
        self._t_repos = 0.0
        self._minuterie_heure = QTimer(self)          # anti-rebond du curseur horaire
        self._minuterie_heure.setSingleShot(True)
        self._minuterie_heure.timeout.connect(self._demander_ville)
        self._etat_boutons()

    # ================================================================== construction IHM
    def _construire(self, hote, port):
        central = QWidget()
        self.setCentralWidget(central)
        racine = QVBoxLayout(central)
        racine.setContentsMargins(10, 8, 10, 8)

        # --- barre de connexion
        barre = QHBoxLayout()
        titre = QLabel("Poste du régulateur — véhicules d'urgence")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        titre.setFont(f)
        barre.addWidget(titre)
        barre.addStretch()
        barre.addWidget(QLabel("Centre de régulation :"))
        self.champ_hote = QLineEdit(hote)
        self.champ_hote.setFixedWidth(130)
        self.champ_port = QLineEdit(str(port))
        self.champ_port.setFixedWidth(60)
        barre.addWidget(self.champ_hote)
        barre.addWidget(self.champ_port)
        self.bouton_connexion = QPushButton("Se connecter")
        self.bouton_connexion.clicked.connect(self._basculer_connexion)
        barre.addWidget(self.bouton_connexion)
        self.voyant = QLabel()
        barre.addWidget(self.voyant)
        racine.addLayout(barre)
        self._definir_voyant(False, "déconnecté")

        # --- carte + onglets (gauche) / panneau de commande (droite)
        split = QSplitter(Qt.Orientation.Horizontal)
        racine.addWidget(split, 1)

        gauche = QSplitter(Qt.Orientation.Vertical)
        self.carte = CarteVille()
        self.carte.depart_choisi.connect(lambda n: self._choisir(self.combo_depart, n))
        self.carte.arrivee_choisie.connect(lambda n: self._choisir(self.combo_arrivee, n))
        gauche.addWidget(self.carte)
        self.onglets = QTabWidget()
        gauche.addWidget(self.onglets)
        gauche.setSizes([700, 190])
        split.addWidget(gauche)

        self.journal = QPlainTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setMaximumBlockCount(2000)
        self.onglets.addTab(self.journal, "Journal réseau (TCP / V2I)")

        self.table_historique = QTableWidget(0, 9)
        self.table_historique.setHorizontalHeaderLabels(
            ["Date", "Véhicule", "Trajet", "Heure", "Classique", "Trafic", "Priorité", "Gain", "Msg V2I"])
        self._table_lecture_seule(self.table_historique)
        self.onglets.addTab(self.table_historique, "Historique des missions (SQLite)")

        analyse = QWidget()
        la = QVBoxLayout(analyse)
        ligne = QHBoxLayout()
        self.bouton_analyse = QPushButton("Analyser ce trajet de 0 h à 23 h")
        self.bouton_analyse.clicked.connect(self._lancer_analyse)
        ligne.addWidget(self.bouton_analyse)
        self.progression_analyse = QProgressBar()
        self.progression_analyse.setRange(0, 24)
        self.progression_analyse.setTextVisible(False)
        self.progression_analyse.setMaximumHeight(8)
        ligne.addWidget(self.progression_analyse, 1)
        la.addLayout(ligne)
        self.graphique_horaire = GraphiqueHoraire()
        la.addWidget(self.graphique_horaire, 1)
        self.onglets.addTab(analyse, "Analyse horaire")

        droite = QWidget()
        droite.setMinimumWidth(440)
        droite.setMaximumWidth(500)
        ld = QVBoxLayout(droite)
        ld.setContentsMargins(6, 0, 0, 0)
        split.addWidget(droite)
        split.setStretchFactor(0, 1)

        # --- mission
        gm = QGroupBox("Mission")
        fm = QFormLayout(gm)
        self.combo_vehicule = QComboBox()
        for nom, niveau in VEHICULES.items():
            self.combo_vehicule.addItem(f"{nom}  (priorité {niveau})", nom)
        self.combo_vehicule.setCurrentIndex(1)
        fm.addRow("Véhicule :", self.combo_vehicule)
        self.combo_depart = QComboBox()
        self.combo_arrivee = QComboBox()
        self.combo_depart.currentIndexChanged.connect(self._selection_changee)
        self.combo_arrivee.currentIndexChanged.connect(self._selection_changee)
        fm.addRow("Départ :", self.combo_depart)
        fm.addRow("Arrivée :", self.combo_arrivee)
        astuce = QLabel("Astuce : clic gauche sur la carte = départ, clic droit = arrivée")
        astuce.setStyleSheet("color:#78909c; font-size:11px;")
        fm.addRow(astuce)
        ligne_h = QHBoxLayout()
        self.curseur_heure = QSlider(Qt.Orientation.Horizontal)
        self.curseur_heure.setRange(0, 23)
        self.curseur_heure.setValue(datetime.datetime.now().hour)
        self.curseur_heure.valueChanged.connect(self._heure_changee)
        self.label_heure = QLabel()
        self.label_heure.setMinimumWidth(150)
        ligne_h.addWidget(self.curseur_heure, 1)
        ligne_h.addWidget(self.label_heure)
        fm.addRow("Heure :", ligne_h)
        self._maj_label_heure()

        boutons = QHBoxLayout()
        self.bouton_calculer = QPushButton("Calculer les itinéraires")
        self.bouton_calculer.clicked.connect(self._calculer)
        self.bouton_lancer = QPushButton("Lancer la mission")
        self.bouton_lancer.setObjectName("primaire")
        self.bouton_lancer.clicked.connect(self._lancer_mission)
        boutons.addWidget(self.bouton_calculer)
        boutons.addWidget(self.bouton_lancer)
        fm.addRow(boutons)
        ld.addWidget(gm)

        # --- simulation
        gs = QGroupBox("Simulation")
        fs = QFormLayout(gs)
        self.combo_vitesse = QComboBox()
        for a in (1, 2, 5, 10, 20):
            self.combo_vitesse.addItem(f"× {a}", a)
        self.combo_vitesse.setCurrentIndex(2)
        self.combo_vitesse.currentIndexChanged.connect(self._reglages_simulation)
        fs.addRow("Vitesse :", self.combo_vitesse)
        self.combo_feux = QComboBox()
        for m in (PRIORITE, "trafic", "classique"):
            self.combo_feux.addItem(f"Feux vus par : {LIBELLES[m]}", m)
        self.combo_feux.currentIndexChanged.connect(self._reglages_simulation)
        fs.addRow("Affichage :", self.combo_feux)
        self.case_trafic = QCheckBox("Afficher le trafic ordinaire")
        self.case_trafic.setChecked(True)
        self.case_trafic.toggled.connect(self.carte.definir_trafic_visible)
        fs.addRow(self.case_trafic)
        lb = QHBoxLayout()
        self.bouton_pause = QPushButton("Pause")
        self.bouton_pause.setCheckable(True)
        self.bouton_pause.toggled.connect(self._reglages_simulation)
        self.bouton_stop = QPushButton("Arrêter")
        self.bouton_stop.clicked.connect(self._arreter_mission)
        self.bouton_recentrer = QPushButton("Recentrer la carte")
        self.bouton_recentrer.clicked.connect(self.carte.ajuster)
        lb.addWidget(self.bouton_pause)
        lb.addWidget(self.bouton_stop)
        lb.addWidget(self.bouton_recentrer)
        fs.addRow(lb)
        self.label_horloge = QLabel("Temps simulé : –")
        self.label_horloge.setWordWrap(True)
        fs.addRow(self.label_horloge)
        ld.addWidget(gs)

        # --- résultats
        gr = QGroupBox("Comparaison des trois trajets")
        lr = QVBoxLayout(gr)
        self.table_resultats = QTableWidget(3, 5)
        self.table_resultats.setHorizontalHeaderLabels(["Itinéraire", "Dist.", "Estimé", "Simulé", "Arrêts"])
        self._table_lecture_seule(self.table_resultats)
        self.table_resultats.verticalHeader().setVisible(False)
        self.table_resultats.setFixedHeight(118)
        entete = self.table_resultats.horizontalHeader()
        for c in range(5):
            entete.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        entete.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for i, m in enumerate(MODES):
            item = QTableWidgetItem("● " + LIBELLES_COURTS[m])
            item.setForeground(COULEURS_MODE[m])
            f = item.font()
            f.setBold(True)
            item.setFont(f)
            self.table_resultats.setItem(i, 0, item)
        lr.addWidget(self.table_resultats)
        self.graphique = GraphiqueBarres()
        lr.addWidget(self.graphique)
        self.label_gain = QLabel("")
        self.label_gain.setWordWrap(True)
        self.label_gain.setStyleSheet("font-size:14px;")
        lr.addWidget(self.label_gain)
        ld.addWidget(gr)
        ld.addStretch()

        self.statusBar().showMessage("Démarrez le serveur (python lancer_serveur.py) puis connectez-vous.")

    @staticmethod
    def _table_lecture_seule(table):
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

    def _definir_voyant(self, ok, texte):
        couleur = "#2e7d32" if ok else "#c62828"
        self.voyant.setText(f"<span style='color:{couleur}; font-size:16px'>●</span> {texte}")

    def _etat_boutons(self):
        connecte = self.ville is not None and self.tcp is not None
        en_mission = self.travailleur is not None
        pret = connecte and self.combo_depart.currentData() and \
            self.combo_depart.currentData() != self.combo_arrivee.currentData()
        self.bouton_calculer.setEnabled(bool(pret) and not en_mission)
        self.bouton_lancer.setEnabled(bool(pret) and bool(self.itineraires) and not en_mission)
        self.bouton_pause.setEnabled(en_mission)
        self.bouton_stop.setEnabled(en_mission)
        self.bouton_analyse.setEnabled(bool(pret) and self.analyse is None)
        self.curseur_heure.setEnabled(not en_mission)
        self.combo_depart.setEnabled(not en_mission)
        self.combo_arrivee.setEnabled(not en_mission)
        self.combo_vehicule.setEnabled(not en_mission)

    def log(self, texte, couleur="#37474f"):
        heure = datetime.datetime.now().strftime("%H:%M:%S")
        self.journal.appendHtml(f"<span style='color:#90a4ae'>{heure}</span> "
                                f"<span style='color:{couleur}'>{texte}</span>")

    # ================================================================== réseau TCP
    def _basculer_connexion(self):
        if self.tcp is not None:
            self._arreter_mission()
            self.tcp.arreter()
            return
        try:
            port = int(self.champ_port.text())
        except ValueError:
            self.statusBar().showMessage("Port invalide")
            return
        self.tcp = ClientTcp(self.champ_hote.text().strip(), port, self)
        self.tcp.recu.connect(self._message_recu)
        self.tcp.connecte.connect(self._connecte)
        self.tcp.deconnecte.connect(self._deconnecte)
        self.bouton_connexion.setEnabled(False)
        self._definir_voyant(False, "connexion…")
        self.tcp.start()

    def connecter(self):
        if self.tcp is None:
            self._basculer_connexion()

    def _connecte(self):
        self.bouton_connexion.setEnabled(True)
        self.bouton_connexion.setText("Se déconnecter")
        self._definir_voyant(True, "connecté")
        self.log(f"TCP connecté à {self.tcp.hote}:{self.tcp.port}", "#2e7d32")
        self._envoyer({"type": "HELLO", "nom": "Régulateur"})
        self._demander_ville()
        self._envoyer({"type": "GET_HISTORY"})

    def _deconnecte(self, raison):
        self.bouton_connexion.setEnabled(True)
        self.bouton_connexion.setText("Se connecter")
        self._definir_voyant(False, "déconnecté")
        self.log(f"TCP fermé : {raison}", "#c62828")
        self.statusBar().showMessage(f"Déconnecté : {raison}")
        if self.tcp is not None:
            self.tcp.wait(1000)
        self.tcp = None
        if self.lien is not None:
            self.lien.arreter()
            self.lien.wait(1000)
            self.lien = None
        self._etat_boutons()

    def _envoyer(self, message):
        if self.tcp is not None:
            self.tcp.envoyer(message)
            if message["type"] not in ("GET_CITY", "GET_HISTORY"):
                self.log(f"→ TCP {message['type']}", "#1565c0")

    def _demander_ville(self):
        self._envoyer({"type": "GET_CITY", "heure": self.curseur_heure.value()})

    def _message_recu(self, msg):
        t = msg["type"]
        if t == "WELCOME":
            self.log(f"← TCP WELCOME {msg['serveur']} v{msg['version']} (V2I sur UDP {msg['port_udp']})", "#2e7d32")
            self.lien = LienV2I(self.tcp.hote, msg["port_udp"], self)
            self.lien.journal.connect(self._journal_v2i)
            self.lien.start()
        elif t == "CITY":
            nouvelle = self.ville is None
            if nouvelle:
                self.ville = Ville.from_dict(msg["ville"])
                self.carte.charger_ville(self.ville)
                self._remplir_combos()
                self._minuterie_feux.start(200)
                self.log(f"← TCP CITY : {len(self.ville.intersections)} carrefours, "
                         f"{len(self.ville.routes)} tronçons", "#2e7d32")
            self.densites = msg["densites"]
            self.carte.appliquer_densites(self.densites)
            self.statusBar().showMessage(f"Carte chargée — densités de {msg['heure']} h")
        elif t == "ROUTES":
            self.itineraires = msg["itineraires"]
            self.densites = msg["densites"]
            self.carte.appliquer_densites(self.densites)
            self.carte.afficher_itineraires(self.itineraires)
            self._remplir_resultats(estimations=True)
            self.log("← TCP ROUTES " + ", ".join(
                f"{i['mode']} {i['distance'] / 1000:.2f} km / {format_temps(i['temps_estime'])}"
                for i in self.itineraires), "#2e7d32")
            self.statusBar().showMessage("Itinéraires calculés — lancez la mission pour les comparer en simulation.")
        elif t == "MISSION_OK":
            self.log(f"← TCP MISSION_OK {msg['mission']}", "#2e7d32")
        elif t == "HISTORY":
            self._remplir_historique(msg["lignes"])
        elif t == "RSU_EVENT":
            if msg.get("mission") == self.mission_id:
                self._evenement_rsu(msg)
        elif t == "ERROR":
            self.log(f"← TCP ERROR {msg.get('message')}", "#c62828")
        self._etat_boutons()

    def _evenement_rsu(self, msg):
        e = msg["evenement"]
        if e == "ACCORD":
            self.log(f"RSU {msg['noeud']} : vert accordé axe {msg['axe']} à {msg['vehicule']} "
                     f"(arrivée dans {msg['eta']:.0f} s)", "#6a1b9a")
        elif e == "REFUS":
            self.log(f"RSU {msg['noeud']} : demande refusée ({msg.get('raison')})", "#e65100")
        elif e == "LIBERATION":
            self.log(f"RSU {msg['noeud']} : carrefour libéré, retour au cycle normal", "#78909c")

    def _journal_v2i(self, sens, msg):
        t = msg.get("type")
        if sens == "->":
            if t == "PRIORITY_REQUEST":
                self.log(f"→ UDP {t} #{msg['id']} carrefour {msg['noeud']} axe {msg['axe']} "
                         f"ETA {msg['eta']} s", "#1565c0")
            elif t == "PASSED":
                self.log(f"→ UDP PASSED carrefour {msg['noeud']}", "#1565c0")
        elif sens == "<-":
            if t == "PRIORITY_GRANT":
                self.log(f"← UDP PRIORITY_GRANT #{msg.get('id')} {msg['noeud']} : vert {msg['axe']} "
                         f"à t={msg['vert_depuis']:.1f} s", "#6a1b9a")
            else:
                self.log(f"← UDP {t} {msg.get('noeud', '')} {msg.get('raison') or ''}", "#e65100")
        else:
            self.log(f"UDP : {msg.get('message')}", "#c62828")

    # ================================================================== sélection
    def _remplir_combos(self):
        for combo in (self.combo_depart, self.combo_arrivee):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("— choisir —", None)
            lieux = sorted((i for i in self.ville.intersections.values() if i.lieu), key=lambda i: i.lieu)
            autres = sorted((i for i in self.ville.intersections.values() if not i.lieu), key=lambda i: i.id)
            for inter in lieux + autres:
                combo.addItem(f"{inter.lieu} ({inter.id})" if inter.lieu else f"Carrefour {inter.id}", inter.id)
            combo.blockSignals(False)
        self._choisir(self.combo_depart, "B2")    # hôpital
        self._choisir(self.combo_arrivee, "G5")   # caserne / zone d'intervention

    def _choisir(self, combo, noeud):
        if self.travailleur is not None:
            return
        i = combo.findData(noeud)
        if i >= 0:
            combo.setCurrentIndex(i)

    def _selection_changee(self):
        self.carte.marquer("depart", self.combo_depart.currentData())
        self.carte.marquer("arrivee", self.combo_arrivee.currentData())
        self._invalider_itineraires()

    def _invalider_itineraires(self):
        self.itineraires = []
        self.carte.effacer_itineraires()
        self._remplir_resultats()
        self._etat_boutons()

    def _heure_changee(self):
        self._maj_label_heure()
        self._invalider_itineraires()
        self._minuterie_heure.start(150)

    def _maj_label_heure(self):
        h = self.curseur_heure.value()
        self.label_heure.setText(f"{h:02d}:00 — {niveau_charge(h)}")

    # ================================================================== itinéraires & mission
    def _calculer(self):
        self._envoyer({"type": "COMPUTE_ROUTES", "depart": self.combo_depart.currentData(),
                       "arrivee": self.combo_arrivee.currentData(), "heure": self.curseur_heure.value(),
                       "vehicule": self.combo_vehicule.currentData()})

    def _lancer_mission(self):
        if not self.itineraires:
            return
        self.mission_id = uuid.uuid4().hex[:8]
        vehicule = self.combo_vehicule.currentData()
        self._envoyer({"type": "MISSION_START", "mission": self.mission_id, "vehicule": vehicule,
                       "depart": self.combo_depart.currentData(), "arrivee": self.combo_arrivee.currentData(),
                       "heure": self.curseur_heure.value()})
        if self.lien is not None:
            self.lien.mission = self.mission_id
            self.lien.niveau = VEHICULES[vehicule]
            while not self.lien.accords.empty():
                self.lien.accords.get_nowait()
            self._v2i_depart = (self.lien.nb_envoyes, self.lien.nb_recus)
        else:
            self.log("Pas de lien V2I : les carrefours ne répondront pas (mode dégradé)", "#e65100")
        self.log(f"Mission {self.mission_id} : {vehicule}, {self.combo_depart.currentText()} → "
                 f"{self.combo_arrivee.currentText()} à {self.curseur_heure.value()} h", "#263238")
        self._minuterie_feux.stop()
        self.carte.effacer_vehicules()
        self._remplir_resultats(estimations=True)
        self.graphique.definir({})
        self.label_gain.setText("")
        self.travailleur = TravailleurMission(self.ville, self.densites, self.itineraires, self.lien,
                                              VEHICULES[vehicule], vehicule, self)
        self.travailleur.trame.connect(self._trame)
        self.travailleur.termine.connect(self._mission_terminee)
        self.travailleur.finished.connect(self._travailleur_fini)
        self._reglages_simulation()
        self.travailleur.start()
        self._etat_boutons()

    def _reglages_simulation(self):
        if self.travailleur is not None:
            self.travailleur.acceleration = float(self.combo_vitesse.currentData())
            self.travailleur.feux_affiches = self.combo_feux.currentData()
            self.travailleur.en_pause = self.bouton_pause.isChecked()

    def _arreter_mission(self):
        if self.travailleur is not None:
            self.travailleur.arreter()
            self.log("Mission interrompue", "#e65100")

    def _travailleur_fini(self):
        self.travailleur = None
        self.bouton_pause.setChecked(False)
        self._minuterie_feux.start(200)
        self._etat_boutons()

    def _trame(self, trame):
        self.carte.afficher_trame(trame)
        self.label_horloge.setText(f"Temps simulé : <b>{format_temps(trame['t'])}</b><br>"
                                   f"<span style='color:#78909c'>Vert retiré aux voies transversales : "
                                   f"{trame['perturbation']:.0f} s</span>")
        for i, v in enumerate(trame["vehicules"]):
            etat = format_temps(v["t"]) + (" ✓" if v["arrive"] else f" · {v['vitesse_kmh']} km/h")
            self.table_resultats.setItem(i, 3, QTableWidgetItem(etat))
            self.table_resultats.setItem(i, 4, QTableWidgetItem(str(v["arrets"])))
        self._t_repos = trame["t"]

    def _mission_terminee(self, resultats):
        self.derniers_resultats = resultats
        self.statusBar().showMessage("Mission terminée — résultats enregistrés dans l'historique du serveur.")
        par_mode = {v["mode"]: v for v in resultats["vehicules"]}
        self._remplir_resultats(estimations=True, resultats=par_mode)
        self.graphique.definir({m: par_mode[m]["temps_simule"] for m in par_mode})
        c, p = par_mode.get("classique"), par_mode.get(PRIORITE)
        if c and p:
            self.label_gain.setText(
                f"Temps gagné par le véhicule connecté : <b style='color:#6a1b9a'>{format_temps(p['gain_s'])}"
                f" (−{p['gain_pct']:.0f} %)</b><br><span style='color:#78909c;font-size:12px'>"
                f"{c['arrets']} arrêt(s) au feu en trajet classique contre {p['arrets']} ; "
                f"vert retiré aux voies transversales : {resultats['perturbation_s']:.0f} s</span>")
        self.log(f"Mission {self.mission_id} terminée — gain {p['gain_s']:.0f} s ({p['gain_pct']:.0f} %)"
                 if p else "Mission terminée", "#2e7d32")
        nb_v2i = 0
        if self.lien is not None:
            e, r = self._v2i_depart
            nb_v2i = self.lien.nb_envoyes - e + self.lien.nb_recus - r
        self._envoyer({"type": "MISSION_RESULT", "mission": self.mission_id,
                       "vehicule": self.combo_vehicule.currentData(),
                       "depart": self.combo_depart.currentData(), "arrivee": self.combo_arrivee.currentData(),
                       "heure": self.curseur_heure.value(), "resultats": resultats, "messages_v2i": nb_v2i})

    def _remplir_resultats(self, estimations=False, resultats=None):
        par_mode = {i["mode"]: i for i in self.itineraires}
        for i, m in enumerate(MODES):
            it = par_mode.get(m) if estimations or self.itineraires else None
            valeurs = ["", "", "", ""]
            if it:
                valeurs[0] = f"{it['distance'] / 1000:.2f} km"
                valeurs[1] = format_temps(it["temps_estime"])
            if resultats and m in resultats:
                r = resultats[m]
                valeurs[2] = format_temps(r["temps_simule"])
                if m != "classique" and r.get("gain_s") is not None:
                    valeurs[2] += f" · −{r['gain_pct']:.0f}%"
                valeurs[3] = str(r["arrets"])
            for j, v in enumerate(valeurs):
                self.table_resultats.setItem(i, j + 1, QTableWidgetItem(v))

    def _remplir_historique(self, lignes):
        self.table_historique.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            vals = [l["date"].replace("T", " "), l["vehicule"] or "", f"{l['depart']} → {l['arrivee']}",
                    f"{l['heure']} h", format_temps(l["t_classique"]), format_temps(l["t_trafic"]),
                    format_temps(l["t_priorite"]),
                    f"{l['gain_s']:.0f} s ({l['gain_pct']:.0f} %)" if l["gain_s"] is not None else "–",
                    str(l["messages_v2i"])]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if j == 7:
                    item.setForeground(QColor("#6a1b9a"))
                self.table_historique.setItem(i, j, item)

    # ================================================================== divers
    def _animer_feux_repos(self):
        """Hors mission : les feux suivent leur cycle normal (et le trafic circule)."""
        if self.ville is None:
            return
        self._t_repos += 0.2 * 5
        self.carte.afficher_feux(MondeFeux(self.ville).instantane(self._t_repos))
        if self.carte.trafic and self.carte.trafic.isVisible():
            self.carte.trafic.definir(t=self._t_repos)

    def _lancer_analyse(self):
        dep, arr = self.combo_depart.currentData(), self.combo_arrivee.currentData()
        self.analyse = TravailleurAnalyse(self.ville, dep, arr, VEHICULES[self.combo_vehicule.currentData()], self)
        self.analyse.progression.connect(self.progression_analyse.setValue)
        self.analyse.resultat.connect(self.graphique_horaire.definir)
        self.analyse.finished.connect(self._analyse_finie)
        self.onglets.setCurrentIndex(2)
        self.analyse.start()
        self._etat_boutons()

    def _analyse_finie(self):
        self.analyse = None
        self._etat_boutons()

    def closeEvent(self, event):
        for th in (self.travailleur, self.analyse):
            if th is not None:
                if hasattr(th, "arreter"):
                    th.arreter()
                th.wait(2000)
        if self.lien is not None:
            self.lien.arreter()
            self.lien.wait(1000)
        if self.tcp is not None:
            self.tcp.arreter()
            self.tcp.wait(1000)
        super().closeEvent(event)
