# ComptaBB

Comptabilité de l'association (Loge Bnei Brith, Israël, comptes en ₪),
tenue directement dans un classeur Excel : saisie guidée pour bénévoles,
suivi des membres, rapprochement bancaire, clôture et états annuels.

Dépôt privé : https://github.com/jlchabbat/ComptaBB

## Installation sur le poste

```
D:\OneDrive\Applications\ComptaBB\
    ComptaBB.xlsm          le classeur (hors Git : données de l'association)
    config.json            nom du classeur, dossier Imports
    docs\                  cahier des charges, inventaire, plan par lots
    Imports\               modèles d'import et exports de reprise
    src\                   outils de contrôle, requêtes Power Query (.pq)
    tests\                 tests et photographies des totaux
```

1. Cloner le dépôt dans `D:\OneDrive\Applications\ComptaBB` :
   `git clone https://github.com/jlchabbat/ComptaBB "D:\OneDrive\Applications\ComptaBB"`
2. Y déposer le classeur sous le nom `ComptaBB.xlsm`. Pour l'instant, c'est
   `Fusion.xlsm` renommé. Le nom se change dans `config.json`.
3. Pour les outils de contrôle, installer Python 3 puis
   `pip install -r src/requirements.txt`.

Aucun chemin absolu : tout est relatif à ce dossier, qui peut être déplacé
d'un bloc.

## Contrôler le classeur

Après chaque enregistrement dans Excel :

```
python src/controles.py                        contrôles RG-01 à RG-04
python src/controles.py --photo avant.json     photographie des totaux
python src/controles.py --compare avant.json   totaux inchangés ?
python -m unittest discover tests              tests de l'outil
```

L'outil lit le classeur sans jamais l'enregistrer. Il vérifie : Mvt
équilibrés, comptes, journaux et codes analytiques connus, jamais débit
et crédit sur une même ligne, rien dans une période close, pièces non
partagées, aucune erreur de formule.

## Avancement

| Lot | Contenu | État |
|---|---|---|
| 0 | Inventaire, dissociation des requêtes, chemins relatifs, Imports | inventaire fait — plan en attente de validation |
| 1 | Saisie guidée | — |
| 2 | Suivi des membres | — |
| 3 | Rapprochement bancaire | — |
| 4 | Clôture et états annuels | — |

État du classeur reçu le 26/09/2026 : 1 534 lignes, 416 mouvements
équilibrés, 1 444 703,68 ₪ au débit comme au crédit, résultat
−47 366,41 ₪, Contrôles OK.

## Documentation

- [Cahier des charges](docs/cahier-des-charges.md)
- [Inventaire du classeur](docs/inventaire.md)
- [Plan par lots et arbitrages demandés](docs/plan-lots.md)
- [Imports : formats, ordre, reprise](Imports/README.md)
