# Imports — initialisation et reprise de ComptaBB

Ce dossier sert à deux choses :

- **initialiser** une comptabilité neuve à partir des modèles de
  `modeles/` ;
- **reprendre** la comptabilité existante à partir des exports de
  `reprise/`.

Tous les chemins sont relatifs à la racine du projet
(`Applications/ComptaBB`).

> Statut : **projet**. Les formats ci-dessous reprennent les colonnes des
> tables du classeur actuel (voir `docs/inventaire.md`). Ils seront figés
> au Lot 0, en même temps que la procédure d'import dans Excel.

## Format commun

| | |
|---|---|
| Type de fichier | CSV, encodage UTF-8 avec BOM (l'hébreu et les accents restent lisibles dans Excel) |
| Séparateur | point-virgule `;` |
| Première ligne | en-têtes, **exactement** les noms de colonnes ci-dessous |
| Dates | `jj/mm/aaaa` |
| Montants | virgule décimale, pas de séparateur de milliers, pas de symbole ₪ : `1234,50` |
| Montant absent | cellule vide (pas de 0 dans la colonne inutilisée débit/crédit) |
| Codes | texte, sans espace avant ni après ; les comptes restent du texte (`411TAIEB001`, `512000`) |

## Fichiers, colonnes et ordre d'import

L'ordre compte : chaque fichier ne cite que des codes définis par les
fichiers précédents.

| Ordre | Fichier | Table | Colonnes obligatoires | Colonnes facultatives |
|---|---|---|---|---|
| 1 | `01_parametres.csv` | cellules nommées de Paramètres | Nom, Valeur | Description |
| 2 | `02_journaux.csv` | T_Journaux | Code, Intitulé, Type, Actif | Contrepartie, N° de compte, Compte bancaire |
| 3 | `03_axe1.csv` | T_Axe1 | Code, Libellé, Actif | |
| 4 | `04_axe2.csv` | T_Axe2 | Code, Actif (0, 1 ou 2) | Libellé |
| 5 | `05_prefixes.csv` | T_Prefixes | Préfixe, Axe (1 ou 2) | Libellé, Code suivant (recalculé) |
| 6 | `06_plan_comptable.csv` | T_PlanComptable | Compte, Libellé compte, Axe 1 (Anal1) | Lettrable (`oui`/vide), Utilisé, Tva, Solde (ignoré) |
| 7 | `07_membres.csv` | T_Membres (Lot 2) | Compte, Nom, Statut | Prénom, Téléphone, E-mail, Date d'adhésion, Cotisation annuelle |
| 8 | `08_trad_banque.csv` | T_TradBanque | Opération (hébreu), Traduction | |
| 9 | `09_ecritures.csv` | T_Ecritures | Date, Jnl, Mvt, Pièce, Compte, Libellé, Débit ou Crédit | Anal2, Let |
| 10 | `10_releve_<Jnl>.csv` | T_Banque<n> (Lot 3) | Date, Montant, Solde relevé | Référence, Opération (relevé) |

Les colonnes calculées du classeur (Intitulé, Anal1, Classe, Contrôle,
Libellé Axe1, Libellé Axe2, État Axe2) ne s'importent pas : Excel les
recalcule.

## Règles de mapping

- `Anal1` n'est pas importé avec les écritures : il vient du compte, via
  T_PlanComptable.
- Statut Anal2 (`Actif`) : 0 = Non affecté, 1 = En cours, 2 = Terminé.
- Compte membre : `411` + 5 premières lettres du nom + rang sur 3
  chiffres (`411TAIEB001`).
- Relevés en hébreu : l'opération est traduite par T_TradBanque ; toute
  opération inconnue apparaît « À traduire ».

## Contrôles avant import

Refuser le fichier si l'un de ces contrôles échoue :

1. En-têtes conformes, dates et montants lisibles.
2. Chaque `Mvt` est équilibré (RG-01) ; une ligne porte soit un débit soit
   un crédit (RG-03).
3. Tout compte, journal et code Anal2 existe dans les fichiers déjà
   importés (RG-02).
4. Aucune écriture datée au plus tard à `P_DateCloture` (RG-04), sauf le
   journal AN.

Après import, `python src/controles.py` doit répondre « Contrôles : OK ».

## Doublons

- Référentiels : le code est la clé. Un code déjà présent n'est **pas**
  écrasé ; il est signalé.
- Écritures : un `Mvt` déjà présent dans T_Ecritures n'est pas réimporté.
  Pour ajouter des écritures, les renuméroter à partir de
  `MAX(T_Ecritures[Mvt]) + 1`, et de même pour `Pièce`.
- Relevés : clé = Date + Référence + Montant + rang dans la journée.

## Reprise et annulation

1. Enregistrer une copie datée du classeur (`ComptaBB_AAAA-MM-JJ_avant-import.xlsm`).
2. `python src/controles.py --photo avant.json`.
3. Importer dans l'ordre ci-dessus.
4. `python src/controles.py --compare avant.json`. L'écart doit
   correspondre exactement aux lignes importées.
5. En cas de problème : fermer sans enregistrer, ou revenir à la copie
   datée. Rien n'est supprimé du classeur par un import.

## `reprise/`

Destiné aux exports complets de la comptabilité existante, dans les
formats ci-dessus. Ils contiennent des données personnelles (noms des
membres, libellés). Ils sont donc **exclus de Git** par `.gitignore` tant
que leur versionnement dans ce dépôt privé n'a pas été autorisé (§12 du
cahier des charges). Sinon, les conserver dans une sauvegarde chiffrée
séparée.
