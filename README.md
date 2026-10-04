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
flask --app wsgi run
python -m unittest discover tests
```

La base est créée dans `instance/compta.db` (hors Git). Déploiement : `deploiement/pythonanywhere.md`.

## À faire

Authentification, correction/suppression d'écritures avec historique, clôture d'exercice, rapprochement bancaire, exports.
