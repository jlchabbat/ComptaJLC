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

Au premier accès, ouvrir l'adresse du site : la page « Premier démarrage » demande de créer le premier compte. Faites-le tout de suite, car tant qu'aucun compte n'existe, c'est le premier visiteur qui le crée.

`COMPTAJLC_SECRET` est facultative : sans elle, une clé aléatoire est créée dans `instance/secret.key`.

## Même compte que ComptaBB

`comptabb.pythonanywhere.com` est déjà l'adresse de ComptaBB : un compte PythonAnywhere n'a qu'un site à son adresse `.pythonanywhere.com`. Pour héberger ComptaJLC dans le même compte, ajouter une web app avec un **nom de domaine personnalisé** (formule payante qui l'autorise), puis créer l'enregistrement CNAME chez le registrar. Sinon, utiliser un second compte PythonAnywhere.
