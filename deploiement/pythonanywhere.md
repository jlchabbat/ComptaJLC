# Déploiement sur PythonAnywhere

1. Console Bash : `git clone https://github.com/jlchabbat/ComptaJLC` puis
   `cd ComptaJLC && python3.11 -m venv ~/.venvs/comptajlc && ~/.venvs/comptajlc/bin/pip install -r requirements.txt`.
2. Onglet **Web** → *Add a new web app* → *Manual configuration* (Python 3.11).
3. *Virtualenv* : `/home/comptajlc/.venvs/comptajlc`.
4. Fichier WSGI : remplacer le contenu par
   ```python
   import sys
   sys.path.insert(0, "/home/comptajlc/ComptaJLC")
   import os
   os.environ["COMPTAJLC_SECRET"] = "une-longue-valeur-secrète"
   from wsgi import application
   ```
5. Recharger l'application. Mise à jour : `git pull` puis *Reload*.

Au premier accès, ouvrir l'adresse du site : la page « Premier démarrage » demande de créer le premier compte. Faites-le tout de suite, car tant qu'aucun compte n'existe, c'est le premier visiteur qui le crée.

`COMPTAJLC_SECRET` est facultative : sans elle, une clé aléatoire est créée dans `instance/secret.key`.

## Compte gratuit `comptajlc`

- Créer le compte sur https://www.pythonanywhere.com (nom d'utilisateur `comptajlc`) : le site sera `https://comptajlc.pythonanywhere.com`, en HTTPS.
- Un compte gratuit n'a qu'une web app. Il faut cliquer sur **Run until 3 months from today** dans l'onglet Web au moins une fois tous les 3 mois, sinon le site s'arrête.
- Le dépôt est privé : cloner avec un jeton GitHub (Settings → Developer settings → Fine-grained token, accès *Contents : lecture* au seul dépôt ComptaJLC) :
  `git clone https://<jeton>@github.com/jlchabbat/ComptaJLC`. Ne jamais écrire le jeton dans un fichier du dépôt.
- La protection par mot de passe de PythonAnywhere n'existe pas en gratuit ; l'authentification de l'application la remplace.
- Sauvegarde : télécharger régulièrement `instance/compta.db` (onglet Files).

## Même compte que ComptaBB

`comptabb.pythonanywhere.com` est déjà l'adresse de ComptaBB : un compte n'a qu'un site à son adresse `.pythonanywhere.com`. Pour héberger ComptaJLC dans ce compte, il faudrait un nom de domaine personnalisé (formule payante).
