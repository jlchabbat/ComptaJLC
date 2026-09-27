# Héberger ComptaBB sur PythonAnywhere

Objectif : un essai gratuit, puis, s'il est concluant, l'offre payante
(environ 5 $ par mois, sans engagement). L'application reste la même que
sur le PC ; seules changent l'adresse et l'endroit où vivent les données.

## À savoir avant de commencer

- **Offre gratuite (Beginner)** : une application à l'adresse
  `https://VOTRE_NOM.pythonanywhere.com`, puissance limitée, et il faut
  cliquer une fois tous les **3 mois** sur « Run until 3 months from today »
  (onglet Web) pour qu'elle reste en ligne. Suffisant pour l'essai.
- **Deux bases distinctes** : pendant l'essai, la base du PC et celle du site
  évoluent séparément. Garder le PC comme référence ; au passage définitif,
  on copie une dernière fois la base du PC vers le site, puis on n'utilise
  plus que le site (le PC devient un simple navigateur).
- **Données personnelles** : pour l'essai, on peut mettre une copie des
  vraies données ou partir de zéro. Les mots de passe doivent être solides
  (12 caractères au moins pour le trésorier).

## 1. Créer le compte (5 minutes)

1. Sur <https://www.pythonanywhere.com>, **Pricing & signup** › **Create a
   Beginner account**. L'identifiant choisi donne l'adresse du site
   (par exemple `comptabb` → `comptabb.pythonanywhere.com`).
2. Confirmer l'adresse e-mail.

Dans la suite, remplacer `VOTRE_NOM` par cet identifiant.

## 2. Déposer le code

1. Sur GitHub, dépôt **ComptaBB**, choisir la branche (`main` une fois la PR
   fusionnée), bouton **Code** › **Download ZIP**.
2. Sur PythonAnywhere, onglet **Files** › **Upload a file** : envoyer le ZIP.
3. Onglet **Consoles** › **Bash**, puis taper :

```bash
unzip -q ComptaBB-*.zip && mv ComptaBB-*/ ComptaBB && rm ComptaBB-*.zip
python3.12 -m venv ~/venv && source ~/venv/bin/activate
pip install -r ComptaBB/appli/requirements.txt
```

## 3. Mettre les données

Choisir **une** des trois possibilités, puis lancer la préparation.

- **A. Copie de la base du PC** (recommandé : comptes, fiches et pointages
  compris) : onglet Files, créer le dossier `comptabb-data` et y envoyer
  `data\comptabb.sqlite3` du PC (ComptaBB fermé).
- **B. Reprise du classeur** : envoyer `ComptaBB.xlsm`, puis après la
  préparation : `python manage.py importer_classeur ~/ComptaBB.xlsm`.
- **C. Base vide** pour tester.

```bash
cd ~/ComptaBB/appli && source ~/venv/bin/activate
export COMPTABB_DATA=~/comptabb-data
python manage.py preparer
python manage.py creer_administrateur # inutile avec la copie A si vos comptes existent déjà
```

## 4. Créer le site

Onglet **Web** › **Add a new web app** › **Manual configuration** ›
**Python 3.12**, puis sur la page de l'application :

| Rubrique | Valeur |
|---|---|
| Virtualenv | `/home/VOTRE_NOM/venv` |
| WSGI configuration file | ouvrir le lien, tout remplacer par le contenu de `appli/deploiement/pythonanywhere_wsgi.py` et y mettre votre identifiant (3 endroits) |
| Static files | URL `/static/`, dossier `/home/VOTRE_NOM/comptabb-data/static` |
| Force HTTPS | Enabled |

Bouton vert **Reload**, puis ouvrir `https://VOTRE_NOM.pythonanywhere.com`.

## 5. Au quotidien

- **Bénévoles** : Fiches bénévoles › Nouveau bénévole ; leur envoyer
  l'adresse du site, leur identifiant et leur mot de passe.
- **Sauvegarde** : onglet Files, télécharger régulièrement
  `comptabb-data/comptabb.sqlite3`.
- **Tous les 3 mois (gratuit)** : onglet Web › **Run until 3 months from
  today**.

## 6. Mettre à jour le code

Suivre le protocole `docs/ComptaBB_protocole_mise_a_jour.pdf` (source :
`docs/protocole-mise-a-jour.html`). En bref : envoyer le ZIP dans Files, puis
`bash ~/maj.sh` dans une console Bash (script `appli/deploiement/maj.sh` :
sauvegarde de la base, nouveau code, bibliothèques, `preparer`, rechargement ;
`bash ~/maj.sh --retour` remet la version précédente).

## 7. Fin de l'essai

- **On garde** : Account › passer à l'offre payante (environ 5 $/mois), qui
  lève la limite des 3 mois et permet un nom de domaine à soi.
- **On arrête** : onglet Web › Delete, puis Account › supprimer le compte.
  L'application du PC continue de fonctionner.
