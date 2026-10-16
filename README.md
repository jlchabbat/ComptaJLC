# ComptaJLC

Comptabilité ordinaire en ligne (application web Django, base SQLite), pensée pour PythonAnywhere.
C'est une application **indépendante** : elle a son propre dépôt, son propre site et ses propres données.

- **Un seul axe analytique, Anal** : chaque compte du plan porte un code Anal.
- **Des tiers** (clients, fournisseurs…) ; **deux modes** de travail : Administration et Gestion.
- Saisie guidée, écritures libres, journaux, grand livre, balance, rapprochement bancaire, justificatifs,
  budget, états annuels, clôture, imports et exports Excel.

## Pour commencer

- Description de l'application, des pages et des droits : [`appli/README.md`](appli/README.md)
- Installation sur l'hébergement : [`docs/hebergement-pythonanywhere.md`](docs/hebergement-pythonanywhere.md)
- Structure des fichiers d'échange : [`docs/specification-fichiers.md`](docs/specification-fichiers.md),
  modèles vides dans `Imports/modeles/`
- Relevés bancaires : [`docs/banques.md`](docs/banques.md)

## Développement

```
cd appli
pip install -r requirements.txt
python manage.py test compta
```

Les données réelles (bases, `Imports/`, `Exports/`, justificatifs) ne vont jamais dans Git.
