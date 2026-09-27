# Imports et Exports — échanges de ComptaBB par fichiers Excel

L'application web lit ses données dans le dossier **`Imports`** et écrit ses
exports dans le dossier **`Exports`**, tous deux dans le dossier ComptaBB du
PC (`D:\OneDrive\Applications\ComptaBB`) ; sur PythonAnywhere, dans le dossier des données
(`comptabb-data`), pour survivre aux mises à jour. Les chemins se modifient dans
**Administration › Imports / Exports** (réglages `dossier_imports` et
`dossier_exports`). Les dossiers sont créés automatiquement.

Chaque dossier contient un **`Lexique.xlsx`** (réécrit par l'application) :
liste des fichiers, de leurs colonnes et des règles. `modeles/` contient un
modèle vide de chaque fichier et le lexique ; c'est la seule partie versionnée.
Tout le reste (données des membres, relevés bancaires) est hors Git.

## `Parametres.xlsx` (application web)

Classeur des paramètres de ComptaBB, une feuille par sujet : Réglages,
Axe 1, Axe 2, Préfixes, Plan comptable (hors comptes de tiers), Journaux,
Types de tiers, Moyens de paiement, Modèles d'opération, Natures fiches,
Modes fiches, Relevés, Traductions. Il reflète l'application au moment où
il est écrit, se modifie dans Excel et se réinjecte :

- dans l'application : *Administration › Paramètres (Excel)* — boutons
  « Préparer Imports/Parametres.xlsx » puis « Importer » ;
- ou en ligne de commande :
  `python manage.py parametres exporter` puis
  `python manage.py parametres importer`.

Règles : clé connue = mise à jour, clé nouvelle = création, cellule vide =
aucun changement, rien n'est supprimé (Actif = Non), et au moindre problème
rien n'est enregistré. Une sauvegarde de la base est faite avant chaque
import (dossier `Exports/Sauvegardes`).

Réservé à l'administrateur (paramétrage de base) : pour les autres utilisateurs,
l'application ne lit ni n'écrit rien dans `Imports/` et `Exports/`. Le
fichier n'est pas versionné (règle `*.xlsx` du `.gitignore`).

## Page Imports / Exports (administrateur) : règles communes

| | |
|---|---|
| Fichiers | un `.xlsx` par nature de données, une seule feuille |
| Structure | **identique à l'import et à l'export** : un export se corrige dans Excel et se réimporte tel quel |
| Ligne 1 | exactement les en-têtes ci-dessous ; données dès la ligne 2 |
| Nom | commence par le nom du format : `Tiers.xlsx`, `Tiers_2026-09-27.xlsx`… (les exports sont datés) |
| Dates | dates Excel (affichées jj/mm/aaaa) |
| Montants | nombres, sans ₪ ; cellule vide quand il n'y a pas de montant |
| Import | tout ou rien ; sauvegarde de la base avant ; fichier importé rangé, daté, dans `Imports\Importés` |

## Fichiers, dans l'ordre d'import

| # | Fichier | Colonnes | À l'import |
|---|---|---|---|
| 1 | `Exercices.xlsx` | Libellé, Début, Fin, Clos | mise à jour par libellé ; Clos indicatif |
| 2 | `Reglages.xlsx` | Clé, Valeur, Description | mise à jour par clé |
| 3 | `Axe1.xlsx` | Code, Libellé | mise à jour par code |
| 4 | `Axe2.xlsx` | Code, Libellé, Statut (0, 1, 2) | mise à jour par code |
| 5 | `Prefixes.xlsx` | Préfixe, Axe, Libellé | mise à jour par préfixe |
| 6 | `PlanComptable.xlsx` | Compte, Libellé, Axe 1, Lettrable, Actif | mise à jour par compte |
| 7 | `Journaux.xlsx` | Code, Intitulé, Type, Compte de trésorerie, Actif | mise à jour par code |
| 8 | `Tiers.xlsx` | Compte, Type, Nom, Prénom, Adresse, Code postal, Ville, Téléphone, E-mail, Date d'adhésion, Statut, Cotisation annuelle | par compte, sinon type + nom + prénom ; cellule vide = rien d'effacé |
| 9 | `Traductions.xlsx` | Opération (hébreu), Traduction | mise à jour par opération |
| 10 | `Budget.xlsx` | Exercice, Nature, Compte, Axe 1, Axe 2, Montant | une seule cible par ligne |
| 11 | `Ecritures.xlsx` | Date, Jnl, Mvt, Pièce, Compte, Libellé, Débit, Crédit, Anal2, Let | Mvt nouveau ajouté, Mvt modifié mis à jour (tracé), identique ignoré |
| 12 | `Banque1.xlsx` | Date, Référence, Opération, Montant, Solde | relevé Mizrahi 732-182029 (B1) ; lignes déjà présentes ignorées |
| 13 | `Banque2.xlsx` | idem | relevé Mizrahi (B2) |
| 14 | `Bit.xlsx` | Journ, Date, Libelle, Debit, Credit | relevé Bit (B3), `Journ` = `B3` ; **remplace** le relevé B3 ([détail](../docs/import-banque3.md)) |
| 15 | `Caisse.xlsx` | Date, Référence, Opération, Montant, Solde | caisse (CA) |

Relevés Mizrahi : le PDF de la banque (`tnuot.pdf`, [détail](../docs/import-mizrahi.md))
déposé dans `Imports` se convertit en `Banque1_date.xlsx` ou `Banque2_date.xlsx`
par un bouton de la page ; le solde est complété sur chaque ligne et vérifié
contre les soldes imprimés. Vérifier le fichier, puis l'importer.

## Tout réinjecter

Bouton de la page (confirmation `REMPLACER`) : pour chaque fichier présent dans
`Imports` (un seul par nature), `Ecritures`, `Banque1`, `Banque2`, `Bit`,
`Caisse` et `Budget` **remplacent toutes** les données de leur nature ; les
référentiels (1 à 9) sont mis à jour, jamais supprimés. Les pointages, les
à-nouveaux de clôture et les fiches bénévoles reportées sont recollés quand
leurs écritures et lignes de relevé reviennent à l'identique. Tout ou rien,
avec une sauvegarde préalable.

Non échangés par fichier (Référentiels de l'application) : modèles
d'opérations, moyens de paiement, types de tiers, natures et modes des fiches
bénévoles, utilisateurs, historique.
