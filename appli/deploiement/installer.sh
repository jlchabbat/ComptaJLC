#!/bin/bash
# Installation de ComptaBB sur un compte PythonAnywhere neuf (un site par association), une seule fois.
# Avant : onglet Web > Add a new web app > Manual configuration > Python 3.12 ; envoyer le ZIP de ComptaBB dans Files.
# Puis, dans une console Bash :
#   unzip -qo ComptaBB-*.zip -d ~/inst && bash ~/inst/*/appli/deploiement/installer.sh
# Ensuite, les mises à jour se font avec bash ~/maj.sh.
set -e
cd ~
NOM=$(whoami)
MIN=$(echo "$NOM" | tr '[:upper:]' '[:lower:]')          # adresse et fichier WSGI : en minuscules (ComptaJLC → comptajlc)
DATA=~/comptabb-data
ADRESSE="$MIN.pythonanywhere.com"
WSGI="/var/www/${MIN}_pythonanywhere_com_wsgi.py"
trap 'echo; echo "ÉCHEC de l installation : copiez ce qui s affiche ci-dessus et envoyez-le à la personne qui vous aide."' ERR

if [ -d ~/ComptaBB ]; then
  echo "ComptaBB est déjà installé (dossier ~/ComptaBB). Pour une mise à jour : bash ~/maj.sh"
  exit 1
fi
ZIP=$(ls -t ~/ComptaBB-*.zip 2>/dev/null | head -1 || true)
if [ -z "$ZIP" ]; then
  echo "Aucun fichier ComptaBB-….zip : envoyez-le d'abord (onglet Files > Upload a file)."
  exit 1
fi

echo "1/5 Code : $(basename "$ZIP")"
rm -rf ~/maj && mkdir ~/maj && unzip -q "$ZIP" -d ~/maj
NOUVEAU=$(ls -d ~/maj/*/ | head -1)
[ -f "$NOUVEAU/appli/manage.py" ] || { echo "Ce ZIP ne contient pas ComptaBB."; exit 1; }
mv "$NOUVEAU" ~/ComptaBB
rm -rf ~/maj ~/inst "$ZIP"

echo "2/5 Python et bibliothèques (quelques minutes)"
PY=""
for v in 3.13 3.12 3.11; do command -v "python$v" >/dev/null && { PY="python$v"; break; }; done
[ -n "$PY" ] || { echo "Python 3.11 ou plus récent introuvable."; exit 1; }
[ -d ~/venv ] || "$PY" -m venv ~/venv
source ~/venv/bin/activate
pip install -q --disable-pip-version-check -r ~/ComptaBB/appli/requirements.txt

echo "3/5 Base de données (vide) et dossiers"
mkdir -p "$DATA"
cd ~/ComptaBB/appli
COMPTABB_DATA="$DATA" python manage.py preparer > ~/preparer.txt
CODE=$(sed -n "s/.*code d'installation \([0-9A-F]*\).*/\1/p" ~/preparer.txt)
rm -f ~/preparer.txt
cd ~

echo "4/5 Fichier WSGI du site"
sed "s/VOTRE_NOM.pythonanywhere.com/$ADRESSE/; s/VOTRE_NOM/$NOM/g" ~/ComptaBB/appli/deploiement/pythonanywhere_wsgi.py > ~/comptabb_wsgi.py
if [ -f "$WSGI" ]; then
  cp ~/comptabb_wsgi.py "$WSGI"
  touch "$WSGI"
  echo "   $WSGI écrit, site rechargé."
else
  echo "   Application web introuvable ($WSGI) : créez-la (onglet Web > Add a new web app > Manual configuration >"
  echo "   Python 3.12), puis relancez seulement : cp ~/comptabb_wsgi.py $WSGI"
fi

echo "5/5 Script de mise à jour"
cp ~/ComptaBB/appli/deploiement/maj.sh ~/maj.sh

echo
echo "INSTALLATION TERMINÉE. Reste à faire dans l'onglet Web :"
echo "  - Virtualenv   : $HOME/venv"
echo "  - Static files : URL /static/   dossier $HOME/comptabb-data/static"
echo "  - Force HTTPS  : Enabled"
echo "  - bouton vert Reload"
echo
echo "Puis ouvrez https://$ADRESSE"
echo "CODE D'INSTALLATION (à saisir sur la page « Bienvenue dans ComptaBB ») : ${CODE:-voir python manage.py preparer}"
