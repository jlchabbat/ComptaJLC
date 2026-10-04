# ComptaJLC

Comptabilité web en français (Flask + SQLite), conçue pour PythonAnywhere.

- **Plan comptable modifiable** : ajout, modification, suppression (si inutilisé), import CSV `numéro;libellé`.
- **Axes analytiques paramétrables** : nombre d'axes et codes libres ; un code par axe et par ligne d'écriture.
- **Partie double** : une écriture est refusée si débit ≠ crédit. Montants stockés en centimes.
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

Correction/suppression d'écritures avec historique, clôture d'exercice, rapprochement bancaire, exports.
