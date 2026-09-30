# Promptographie — journal d'usage de l'IA

Journal de travail tenu au fil du projet, à mettre en forme (`.docx`) pour le livrable
final du 15/11/2026. Une entrée par session : outil, demande, ce que l'IA a produit, ce que
nous avons vérifié ou modifié nous-mêmes.

## Outils utilisés

| Outil | Usage |
|---|---|
| ChatGPT | Brouillon initial du projet (`source/cnvo-chat-gpt.txt`). Écarté comme référence technique : il recommandait networkx, pygame et pandas, hors de la liste autorisée. |
| Claude Code (Anthropic) | Génération des documents (scripts `outils/*.js`), code Python du noyau, tests. |

## Sessions

### 20/09/2026 — Claude Code — documents de cadrage

- **Demande** : rédiger le cahier des charges, le compte rendu de la semaine 2 et la
  répartition des tâches ; retranscrire les notes manuscrites scannées.
- **Produit** : scripts `outils/cdc.js`, `outils/cr.js`, `outils/repartition.js` qui
  génèrent les `.docx` ; `source/cours-transcription.md`.
- **Vérifié / modifié par nous** : [À COMPLÉTER — relecture du CdC, choix MoSCoW,
  estimations validées ou corrigées.]
- **Limite constatée** : les horaires du compte rendu de la semaine 2 ont été
  reconstitués par l'IA à partir des dates de fichiers, pas relevés ; ils doivent être
  vérifiés par nous.

### 25/09/2026 — Claude Code — démarrage du code (F01, F02)

- **Demande** : « démarrer le projet ». L'IA a demandé de préciser le périmètre ; nous
  avons choisi : arborescence du dépôt + F01 + F02, dépôt local uniquement (pas de
  création sur GitHub).
- **Produit** :
  - arborescence `github/` conforme au CdC, `requirements.txt`, `.gitignore`, README
    provisoire ;
  - `src/core/graph.py` (F01) : graphe orienté, poids en temps de parcours, congestion,
    sérialisation JSON, générateur de quadrillage ;
  - `src/core/engine.py` (F02) : moteur à pas fixe, événements planifiés, graine
    aléatoire, mode temps réel avec pause / reprise / arrêt depuis un autre thread ;
  - `src/core/routing.py` (F05, pris en avance sur le sprint 2) : Dijkstra et A* écrits
    à la main, poids interchangeable (temps à vide / avec trafic) ;
  - 35 tests unitaires (`tests/`), dont une vérification des itinéraires contre une
    recherche exhaustive sur des villes aléatoires ;
  - brouillon du compte rendu de la semaine 3 ;
  - sur la demande « arriver au premier prototype minimal » : versions minimales des feux
    (`lights.py`), du trafic (`traffic.py`), de la comparaison des stratégies et de la
    préemption (`scenario.py`), et le prototype console `python -m src.prototype` ;
    56 tests au total.
- **Correction en cours de route** : la première version donnait une stratégie
  « optimisée » plus lente que la « classique ». L'IA a identifié deux causes : une
  congestion mal estimée (files aux feux ignorées) et, plus fondamentalement, l'absence
  de bouchon durable dans un trafic uniforme. Après correction de l'estimation, la
  stratégie optimisée ne gagnait toujours rien sans incident : un tronçon ralenti
  (accident / travaux) a été ajouté au scénario par défaut, et le mode
  `--sans-incident` conservé pour montrer ce résultat honnêtement.
- **Choix proposés par l'IA et retenus** : unittest plutôt que pytest (hors liste
  autorisée) ; une rue à double sens = deux arcs ; poids en secondes plutôt qu'en mètres ;
  graine aléatoire pour rendre les trois stratégies comparables ; heuristique A* bornée
  par le plus petit rapport poids / distance du réseau pour rester admissible.
- **Vérifié / modifié par nous** : [À COMPLÉTER — relecture du code par David et Youssef,
  modifications éventuelles.]
- **Ce que l'IA n'a pas fait** : publication sur GitHub, premier commit. F03 et F04 sont
  confiés à Youssef : l'IA n'en a écrit que des versions minimales pour le prototype.

### 25/09/2026 (suite) — Claude Code — aperçu jetable du projet presque fini

- **Demande** : « aller le plus loin possible pour voir un projet presque fini, sans
  git ; on recommencera proprement ensuite ».
- **Produit** : dossier `apercu/` (copie de `github/` enrichie) — IHM PyQt6 complète,
  protocole V2X et serveur d'infrastructure sur sockets, arbitrage de plusieurs
  véhicules prioritaires, scénarios JSON, historique SQLite, export CSV, graphique,
  thème sombre ; 98 tests. Voir `apercu/APERCU.md`.
- **Méthode** : l'IA a testé l'interface sans écran (Qt « offscreen ») et relu des
  captures d'écran pour corriger l'affichage.
- **Erreurs de l'IA trouvées en cours de route** : lambda connecté à un signal de
  thread (violation de la règle d'or Qt), numéros de séquence globaux au lieu de par
  session, déconnexion à tort d'un véhicule silencieux (d'où l'ajout d'un HEARTBEAT),
  journal réseau inondé, boutons désactivés illisibles en thème sombre, scénario
  centre-ville dont l'incident n'était pas sur le trajet.
- **Statut** : non destiné au rendu. Sert de référence pour la vraie version.
