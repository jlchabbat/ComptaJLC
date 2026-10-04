# ComptaJLC

Comptabilité web en français (Flask + SQLite), conçue pour PythonAnywhere.

- **Plan comptable** modifiable (ajout, modification, compte inactif, suppression si inutilisé), avec une rubrique **Axe 1** par compte, Lettrable, Actif.
- **Axe 1** : code rattaché au compte (bilan, frais, activités…). **Axe 2** : activité / projet, indépendant du plan et de l'axe 1, choisi **facultativement à la saisie** pour les comptes de classe 6 et 7 (réglage `AXE2_CLASSES`). Statut des codes : En cours / Terminé / Non affecté ; seuls les « En cours » sont proposés.
- **Imports CSV** : codes Axe 1, codes Axe 2, plan comptable, écritures (tout ou rien) — format dans `docs/import-ecritures.md`.
- **Partie double** : une écriture est refusée si débit ≠ crédit. Montants stockés en centimes.
- **Correction et suppression d'écritures** avec motif obligatoire ; chaque création, modification et suppression est conservée dans l'**historique** (qui, quand, avant/après). Un numéro de mouvement supprimé n'est jamais réutilisé.
- **Export Excel** du journal et de la balance (`/export/journal.xlsx`, `/export/balance.xlsx`) ; lien d'un justificatif (http/https) par écriture.
- Journaux, saisie, journal des écritures, balance, grand livre, totaux par code analytique.

## Lancer en local

```
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
COMPTAJLC_HTTP=1 flask --app wsgi run   # HTTP local : cookie de session non « Secure »
python -m unittest discover tests
```

La base est créée dans `instance/compta.db` (hors Git). Déploiement : `deploiement/pythonanywhere.md`.

## Accès

Tout est protégé par connexion. Au premier lancement, la page `/premier-demarrage` crée le premier compte ; d'autres comptes s'ajoutent dans « Utilisateurs ». Mots de passe hachés (10 caractères minimum), jeton CSRF sur tous les formulaires, cookie de session `Secure` en HTTPS. La clé de session est lue dans `COMPTAJLC_SECRET` ou, à défaut, générée dans `instance/secret.key`.

## À faire

Clôture d'exercice, rapprochement bancaire, exports.
