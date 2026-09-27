# Modèle d'import — Banque 3 (Bit)

Fichier de référence : `D:\OneDrive\Compta Bnei Brith\Bit.xlsx`

## Structure

- Classeur Excel (`.xlsx`), une seule feuille nommée `Bit`.
- Ligne 1 : en-têtes. Données à partir de la ligne 2, une opération par ligne.

| Colonne | En-tête   | Type                | Contenu                                         |
|---------|-----------|---------------------|-------------------------------------------------|
| A       | `Journ`   | texte               | Code journal — toujours `B2` (voulu)             |
| B       | `Date`    | date Excel          | Date de l'opération (format affiché `mm-dd-yy`) |
| C       | `Libelle` | texte (≤ 50 car.)   | `TIERS - RUBRIQUE - SOUS-RUBRIQUE`              |
| D       | `Debit`   | nombre (entier/décimal) | Montant encaissé sur Bit, sinon vide        |
| E       | `Credit`  | nombre (entier/décimal) | Montant sorti de Bit, sinon vide            |

Une ligne a soit `Debit`, soit `Credit`, jamais les deux.

## Règles observées

- **Code journal** : `B2` est bien le code du journal de Banque 3 (Bit), confirmé.

- **Sens des montants** (point de vue du relevé) :
  - `Debit` = entrée d'argent (ex. participations aux rallyes, fêtes, cotisations).
  - `Credit` = sortie (frais bancaires, `VIREMENT BIT VERS BANQUE`, projets, remboursements).
- **Libellé** : trois parties séparées par ` - ` :
  1. tiers (nom de l'adhérent, ou `BANQUE`, `SOCIAL`, …) ;
  2. rubrique (`FETES`, `SOCIAL`, `CULTUREL`, `LOGE`, `RALLYES`, `BANQUE`, `PROJET`, `DONS`, `TAXES`) ;
  3. sous-rubrique / événement (`RALLY`, `RACLETTE`, `COTISATION ANNUELLE 2026`, …).

  Le libellé est tronqué à 50 caractères (la sous-rubrique peut être coupée,
  ex. `CONFERENCE DANIE`). Il existe des libellés à deux parties seulement
  (ex. `CONFERENCE DANIELLE GUEDJ - REGULARISATION`) : l'import doit les accepter.
- `VIREMENT BIT VERS BANQUE` est un transfert interne vers un autre compte de
  l'association, à traiter comme un virement interne et non comme une charge.

## Exemple

| Journ | Date       | Libelle                                      | Debit | Credit |
|-------|------------|----------------------------------------------|-------|--------|
| B2    | 31/12/2025 | TUBIANAH DANOUCH - RALLYES - RALLY           | 800   |        |
| B2    | 06/01/2026 | VITTORIANO NANCY - FETES - RACLETTE          | 440   |        |
| B2    | 11/01/2026 | BANQUE - BANQUE - FRAIS ET INTERETS BANCAIRE |       | 19.9  |
| B2    | 11/01/2026 | BANQUE - BANQUE - VIREMENT BIT VERS BANQUE   |       | 6820  |
