"""Commit rapide : demande le message, puis fait git add + git commit + git push.

    make commit
"""

import subprocess

# "﻿" : caractère invisible (BOM) que PowerShell peut ajouter devant le texte
message = input("Message du commit : ").strip().lstrip("﻿")
if not message:
    print("Message vide : commit annulé.")
else:
    subprocess.run(["git", "add", "."])
    resultat = subprocess.run(["git", "commit", "-m", message])
    if resultat.returncode == 0:          # 0 = le commit a réussi
        subprocess.run(["git", "push"])
