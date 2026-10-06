# Héberger ComptaJLC sur PythonAnywhere

Objectif : un essai gratuit, puis, s'il est concluant, l'offre payante
(environ 5 $ par mois, sans engagement). L'application n'existe plus qu'en ligne
(l'ancien programme du PC est abandonné).

## À savoir avant de commencer

- **Offre gratuite (Beginner)** : une application à l'adresse
  `https://VOTRE_NOM.pythonanywhere.com`, puissance limitée, et il faut
  cliquer une fois tous les **3 mois** sur « Run until 3 months from today »
  (onglet Web) pour qu'elle reste en ligne. Suffisant pour l'essai.
- **Données personnelles** : pour l'essai, on peut mettre une copie des
  vraies données ou partir de zéro. Les mots de passe doivent être solides
  (12 caractères au moins pour le trésorier).

## 1. Créer le compte (5 minutes)

1. Sur <https://www.pythonanywhere.com>, **Pricing & signup** › **Create a
   Beginner account**. L'identifiant choisi donne l'adresse du site
   (par exemple `comptajlc` → `comptajlc.pythonanywhere.com`).
2. Confirmer l'adresse e-mail.

Dans la suite, remplacer `VOTRE_NOM` par cet identifiant.

## 2. Installer (script)

1. Onglet **Web** › **Add a new web app** › **Manual configuration** ›
   **Python 3.12**.
2. Sur GitHub, dépôt **ComptaJLC**, bouton **Code** › **Download ZIP** ;
   onglet **Files** › **Upload a file** : envoyer le ZIP.
3. Onglet **Consoles** › **Bash** :

```bash
unzip -qo ComptaJLC-*.zip -d ~/inst && bash ~/inst/*/appli/deploiement/installer.sh
```

Le script (`appli/deploiement/installer.sh`) installe le code et les
bibliothèques, crée la base vide, écrit le fichier WSGI et `~/maj.sh`, puis
affiche le **code d'installation**.

## 3. Régler l'application web

Onglet **Web** :

| Rubrique | Valeur |
|---|---|
| Virtualenv | `/home/VOTRE_NOM/venv` |
| Static files | URL `/static/`, dossier `/home/VOTRE_NOM/comptajlc-data/static` |
| Force HTTPS | Enabled |

Bouton vert **Reload**.

## 4. Premier démarrage

Ouvrir `https://VOTRE_NOM.pythonanywhere.com` : saisir le code
d'installation, créer l'administrateur, puis décrire l'association (nom,
devise, plan de base ou fichiers à importer, exercice, banques, options).
Pour reprendre des données existantes : Administration › Base de données ›
recharger une sauvegarde ou un export complet.

## 5. Au quotidien

- **Bénévoles** : Fiches bénévoles › Nouveau bénévole ; leur envoyer
  l'adresse du site, leur identifiant et leur mot de passe.
- **Sauvegarde** : onglet Files, télécharger régulièrement
  `comptajlc-data/comptajlc.sqlite3`.
- **Tous les 3 mois (gratuit)** : onglet Web › **Run until 3 months from
  today**.

## 6. Mettre à jour le code

Suivre le protocole `docs/ComptaJLC_protocole_mise_a_jour.pdf` (source :
`docs/protocole-mise-a-jour.html`). En bref : envoyer le ZIP dans Files, puis
`bash ~/maj.sh` dans une console Bash (script `appli/deploiement/maj.sh` :
sauvegarde de la base, nouveau code, bibliothèques, `preparer`, rechargement ;
`bash ~/maj.sh --retour` remet la version précédente).

## 7. Fin de l'essai

- **On garde** : Account › passer à l'offre payante (environ 5 $/mois), qui
  lève la limite des 3 mois et permet un nom de domaine à soi.
- **On arrête** : onglet Web › Delete, puis Account › supprimer le compte.
  Faire d'abord un export complet (Administration › Base de données).
