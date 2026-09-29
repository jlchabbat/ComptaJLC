#!/bin/bash
# Mise à jour de ComptaBB sur PythonAnywhere.
#   bash ~/maj.sh            installe le dernier ZIP envoyé dans Files (sauvegarde de la base d'abord)
#   bash ~/maj.sh --retour   remet la version précédente du code
# Les données (dossier comptabb-data, avec Imports et Exports) ne sont jamais effacées.
set -e
cd ~
DATA=~/comptabb-data
SAUVEGARDES="$DATA/Exports/Sauvegardes"
WSGI=$(ls /var/www/*_wsgi.py 2>/dev/null | head -1 || true)

recharger() {
  if [ -n "$WSGI" ]; then touch "$WSGI"; echo "   Site rechargé (patientez 10 secondes)."
  else echo "   Onglet Web > bouton vert Reload."; fi
}
echec() {
  echo
  echo "ÉCHEC de la mise à jour. Le site n'est peut-être plus à jour."
  echo "Pour revenir à la version précédente : bash ~/maj.sh --retour"
  echo "Puis copiez ce qui s'affiche ci-dessus et envoyez-le à Claude."
}
trap echec ERR

if [ "$1" = "--retour" ]; then
  [ -d ComptaBB-ancien ] || { echo "Aucune version précédente (dossier ComptaBB-ancien absent)."; exit 1; }
  rm -rf ComptaBB-annule
  mv ComptaBB ComptaBB-annule
  mv ComptaBB-ancien ComptaBB
  echo "Version précédente du code remise en place."
  recharger
  echo "Les données n'ont pas été touchées. Dernières sauvegardes de la base :"
  ls -t "$SAUVEGARDES"/*.sqlite3 2>/dev/null | head -3 | sed 's/^/   /'
  exit 0
fi

ZIP=$(ls -t ~/ComptaBB-*.zip 2>/dev/null | head -1 || true)
if [ -z "$ZIP" ]; then
  echo "Aucun fichier ComptaBB-….zip dans votre dossier : envoyez-le d'abord (onglet Files > Upload a file)."
  exit 1
fi

echo "1/5 Sauvegarde de la base"
mkdir -p "$SAUVEGARDES"
if [ -d "$DATA/sauvegardes" ]; then                              # ancien emplacement (avant Exports)
  mv -n "$DATA"/sauvegardes/* "$SAUVEGARDES"/ 2>/dev/null || true
  rmdir "$DATA/sauvegardes" 2>/dev/null || true
fi
SAUVE="$SAUVEGARDES/comptabb_$(date +%Y-%m-%d_%H%M).sqlite3"
python3 -c "import sqlite3, sys; s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2]); s.backup(d); d.close()" \
  "$DATA/comptabb.sqlite3" "$SAUVE"
ls -t "$SAUVEGARDES"/*.sqlite3 | tail -n +4 | xargs -r -d '\n' rm --       # garde les 3 dernières
echo "   $SAUVE"
if [ -d "$DATA/Justificatifs" ]; then                             # documents scannés : copie ZIP (facultative : jamais bloquante)
  SAUVE_J="$SAUVEGARDES/justificatifs_$(date +%Y-%m-%d_%H%M).zip"
  ls -t "$SAUVEGARDES"/justificatifs_*.zip 2>/dev/null | xargs -r -d '\n' rm --   # une seule copie : l'ancienne libère la place
  if python3 - "$DATA/Justificatifs" "$SAUVE_J" <<'PYJ'
import os, sys, zipfile
racine, cible = sys.argv[1], sys.argv[2]
n = 0
try:
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as z:
        for dossier, _, fichiers in os.walk(racine):
            for f in fichiers:
                z.write(os.path.join(dossier, f), os.path.relpath(os.path.join(dossier, f), racine))
                n += 1
except OSError as e:
    try:
        os.remove(cible)
    except OSError:
        pass
    print("   Copie des documents impossible (%s) : espace disque insuffisant ?" % e)
    sys.exit(1)
print("   %d document(s) : %s (%d Mo)" % (n, cible, os.path.getsize(cible) // 1048576))
PYJ
  then :
  else
    echo "   ATTENTION : documents non sauvegardés (place manquante). La mise à jour continue ; télécharger les documents"
    echo "   sur le PC (page Justificatifs › Tout télécharger) ou libérer de la place (onglet Files)."
  fi
fi

echo "2/5 Nouveau code : $(basename "$ZIP")"
rm -rf ~/maj && mkdir ~/maj && unzip -q "$ZIP" -d ~/maj
NOUVEAU=$(ls -d ~/maj/*/ 2>/dev/null | head -1 || true)
if [ ! -f "$NOUVEAU/appli/manage.py" ]; then
  rm -rf ~/maj "$ZIP"
  echo "Ce ZIP ne contient pas ComptaBB : il a été supprimé, rien n'a changé. Retéléchargez-le depuis GitHub."
  exit 1
fi
rm -rf ComptaBB-ancien
[ -d ComptaBB ] && mv ComptaBB ComptaBB-ancien
mv "$NOUVEAU" ~/ComptaBB
rm -rf ~/maj
rm -f ~/ComptaBB-*.zip

echo "3/5 Bibliothèques Python"
source ~/venv/bin/activate
pip install -q --disable-pip-version-check -r ~/ComptaBB/appli/requirements.txt

echo "4/5 Base de données et paramètres"
cd ~/ComptaBB/appli
COMPTABB_DATA="$DATA" python manage.py preparer
cd ~

echo "5/5 Rechargement du site"
recharger
cp ~/ComptaBB/appli/deploiement/maj.sh ~/maj.sh.nouveau && mv ~/maj.sh.nouveau ~/maj.sh   # le script se met à jour
echo
echo "MISE À JOUR TERMINÉE. Ouvrez le site et appuyez sur Ctrl+F5."
