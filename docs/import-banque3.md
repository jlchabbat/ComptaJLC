# Modèle d'import — Banque 3 (Bit)

Fichier de référence : `D:\OneDrive\Compta Bnei Brith\Bit.xlsx`

## Structure

- Classeur Excel (`.xlsx`), une seule feuille nommée `Bit`.
- Ligne 1 : en-têtes. Données à partir de la ligne 2, une opération par ligne.

| Colonne | En-tête   | Type                | Contenu                                         |
|---------|-----------|---------------------|-------------------------------------------------|
| A       | `Journ`   | texte               | Code journal — `B3`                             |
| B       | `Date`    | date Excel          | Date de l'opération (format affiché `mm-dd-yy`) |
| C       | `Libelle` | texte (≤ 50 car.)   | `TIERS - RUBRIQUE - SOUS-RUBRIQUE`              |
| D       | `Debit`   | nombre (entier/décimal) | Montant encaissé sur Bit, sinon vide        |
| E       | `Credit`  | nombre (entier/décimal) | Montant sorti de Bit, sinon vide            |

Une ligne a soit `Debit`, soit `Credit`, jamais les deux.

Fichier de référence validé : 166 lignes, toutes en `B3`, du 02/01/2026 au
01/07/2026 ; total `Debit` 38 920, total `Credit` 49 362,40.

## Contrôles obligatoires à l'import

L'import de Banque 3 doit respecter strictement cette structure :

1. Une feuille nommée `Bit`.
2. Ligne 1 = exactement `Journ`, `Date`, `Libelle`, `Debit`, `Credit`, dans cet ordre.
3. Chaque ligne de données :
   - `Journ` = `B3`. Toute ligne avec un autre code (ex. `B2`) est **rejetée** et
     signalée, jamais importée ni recodée ;
   - `Date` : une date valide ;
   - `Libelle` : non vide, 50 caractères au plus ;
   - exactement un montant renseigné, `Debit` **ou** `Credit`, nombre positif.
4. Si une ligne est rejetée, l'import s'arrête et liste les lignes en erreur
   (numéro de ligne Excel et motif) : rien n'est enregistré.
5. Un nouvel import de `Bit.xlsx` **remplace** les écritures `B3` existantes
   (pas d'ajout à la suite, pas de doublons).

## Règles observées

- **Code journal** : `B3` pour Bit (Banque 3).
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
| B3    | 02/01/2026 | TUBIANAH DANOUCH - CULTUREL - CONFERENCE DANIELLE  | 140   |        |
| B3    | 06/01/2026 | VITTORIANO NANCY - FETES - RACLETTE          | 440   |        |
| B3    | 11/01/2026 | BANQUE - BANQUE - FRAIS ET INTERETS BANCAIRE |       | 19.9  |
| B3    | 11/01/2026 | BANQUE - BANQUE - VIREMENT BIT VERS BANQUE   |       | 6820  |
