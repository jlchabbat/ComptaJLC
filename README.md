# ComptaBB

Comptabilité de l'association (Loge Bnei Brith, Israël, comptes en ₪),
tenue directement dans un classeur Excel : saisie guidée pour bénévoles,
suivi des membres, rapprochement bancaire, clôture et états annuels.

Dépôt privé : https://github.com/jlchabbat/ComptaBB

## Installation sur le poste

```
D:\OneDrive\Applications\ComptaBB\
    ComptaBB.xlsm          le classeur (hors Git : données de l'association)
    Releves\               relevés bancaires téléchargés (hors Git), dont tnuot.pdf
    config.json            nom du classeur, dossier Imports
    docs\                  cahier des charges, inventaire, plan par lots
    Imports\               modèles d'import et exports de reprise
    src\                   outils de contrôle, requêtes Power Query (.pq)
    tests\                 tests et photographies des totaux
```

1. Cloner le dépôt dans `D:\OneDrive\Applications\ComptaBB` :
   `git clone https://github.com/jlchabbat/ComptaBB "D:\OneDrive\Applications\ComptaBB"`
2. Y déposer le classeur `ComptaBB.xlsm` (produit du Lot 0) et le relevé
   Banque 1 sous `Releves\tnuot.pdf`. Le nom du classeur se change dans
   `config.json`.
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
| 0 | Dissociation de l'ancien logiciel, chemins relatifs, paramètres, Isracard, Journal des modifications | **livré le 26/09/2026** — recette dans Excel à faire ([livraison](docs/livraison-lot0.md)) |
| 1 | Saisie guidée | **livré le 26/09/2026** : Saisie, Codes, Modèles, Transmission, classeur de saisie à distance, protection ([livraison](docs/livraison-lot1.md)) — recette Excel à faire |
| 2 | Suivi des membres | — |
| 3 | Rapprochement bancaire | — |
| 4 | Clôture et états annuels | — |

État après le Lot 0 : 1 544 lignes, 421 mouvements équilibrés,
1 451 040,66 ₪ au débit comme au crédit, résultat −47 366,41 ₪ (inchangé),
Contrôles OK. Photographies : `tests/reference/`.

## Documentation

- [Cahier des charges](docs/cahier-des-charges.md)
- [Inventaire du classeur](docs/inventaire.md)
- [Plan par lots, décisions, accès à distance](docs/plan-lots.md)
- [Imports : formats, ordre, reprise](Imports/README.md)
- [Livraison du Lot 0](docs/livraison-lot0.md)
- [Livraison du Lot 1](docs/livraison-lot1.md)

Le classeur est reproductible depuis `Fusion.xlsm` :

```
python src/lot0_preparation.py Fusion.xlsm lot0.xlsm
python src/lot1_saisie.py lot0.xlsm lot1.xlsm
python src/lot1_distance.py lot1.xlsm ComptaBB.xlsm
python src/classeur_saisie.py ComptaBB.xlsm ComptaBB_Saisie.xlsx   classeur du saisisseur
python tests/recette_lot1.py lot0.xlsm              recette LibreOffice (15 scénarios)
python tests/recette_lot1_distance.py lot1.xlsm     recette LibreOffice (saisie à distance)
```
