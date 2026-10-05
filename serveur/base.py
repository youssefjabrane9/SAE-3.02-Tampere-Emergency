"""Stockage SQLite de l'historique des missions (métriques et comparaisons)."""

import datetime
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mission         TEXT NOT NULL,
    date            TEXT NOT NULL,
    vehicule        TEXT,
    depart          TEXT,
    arrivee         TEXT,
    heure           INTEGER,
    t_classique     REAL,
    t_trafic        REAL,
    t_priorite      REAL,
    gain_s          REAL,
    gain_pct        REAL,
    arrets_classique INTEGER,
    arrets_priorite INTEGER,
    perturbation_s  REAL,
    messages_v2i    INTEGER
)
"""

COLONNES = ["mission", "date", "vehicule", "depart", "arrivee", "heure", "t_classique", "t_trafic",
            "t_priorite", "gain_s", "gain_pct", "arrets_classique", "arrets_priorite",
            "perturbation_s", "messages_v2i"]


class BaseMissions:
    def __init__(self, chemin="sae_missions.db"):
        self.cnx = sqlite3.connect(chemin)
        self.cnx.execute(SCHEMA)
        self.cnx.commit()

    def enregistrer(self, msg, messages_v2i=0):
        par_mode = {v["mode"]: v for v in msg.get("resultats", {}).get("vehicules", [])}
        c, t, p = (par_mode.get(m, {}) for m in ("classique", "trafic", "priorite"))
        ligne = {
            "mission": str(msg.get("mission", "?")),
            "date": datetime.datetime.now().isoformat(timespec="seconds"),
            "vehicule": msg.get("vehicule"),
            "depart": msg.get("depart"),
            "arrivee": msg.get("arrivee"),
            "heure": msg.get("heure"),
            "t_classique": c.get("temps_simule"),
            "t_trafic": t.get("temps_simule"),
            "t_priorite": p.get("temps_simule"),
            "gain_s": p.get("gain_s"),
            "gain_pct": p.get("gain_pct"),
            "arrets_classique": c.get("arrets"),
            "arrets_priorite": p.get("arrets"),
            "perturbation_s": msg.get("resultats", {}).get("perturbation_s"),
            "messages_v2i": messages_v2i,
        }
        self.cnx.execute(
            f"INSERT INTO missions ({','.join(COLONNES)}) VALUES ({','.join('?' * len(COLONNES))})",
            [ligne[k] for k in COLONNES])
        self.cnx.commit()
        return ligne

    def historique(self, limite=100):
        cur = self.cnx.execute(
            f"SELECT {','.join(COLONNES)} FROM missions ORDER BY id DESC LIMIT ?", (limite,))
        return [dict(zip(COLONNES, r)) for r in cur.fetchall()]

    def fermer(self):
        self.cnx.close()
