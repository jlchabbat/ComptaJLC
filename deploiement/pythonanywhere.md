# Déploiement sur PythonAnywhere

1. Console Bash : `git clone https://github.com/jlchabbat/ComptaJLC` puis
   `cd ComptaJLC && python3.11 -m venv ~/.venvs/comptajlc && ~/.venvs/comptajlc/bin/pip install -r requirements.txt`.
2. Onglet **Web** → *Add a new web app* → *Manual configuration* (Python 3.11).
3. *Virtualenv* : `/home/<utilisateur>/.venvs/comptajlc`.
4. Fichier WSGI : remplacer le contenu par
   ```python
   import sys
   sys.path.insert(0, "/home/<utilisateur>/ComptaJLC")
   import os
   os.environ["COMPTAJLC_SECRET"] = "une-longue-valeur-secrète"
   from wsgi import application
   ```
5. Recharger l'application. Mise à jour : `git pull` puis *Reload*.

**Attention** : l'application n'a pas encore d'authentification. Protéger l'accès (onglet Web → *Password protection*, disponible sur les comptes payants) avant d'y saisir des données réelles.
