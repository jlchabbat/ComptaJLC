# ComptaJLC – Fichiers d'échange

Tous les échanges de données se font par fichiers **.xlsx** (une feuille, ligne 1 = en-têtes), un par nature de données,
de **même structure à l'import et à l'export**. Le fichier est reconnu d'après les colonnes de sa ligne 1, quel que soit son nom.
Les modèles vides sont dans `Imports/modeles/` ; `Lexique.xlsx` décrit chaque colonne. L'application ne transforme pas les fichiers
d'une banque ou d'un autre logiciel : on les met en forme avant (Power Query dans Excel, par exemple).

Règles communes : import **tout ou rien** (une erreur et rien n'est enregistré) ; une sauvegarde de la base précède chaque import ;
les référentiels sont mis à jour (clé existante) ou créés (clé nouvelle), jamais supprimés ; une cellule vide ne change rien.
Montants : nombres, un débit **ou** un crédit par ligne ; dates jj/mm/aaaa.

## Un seul axe analytique : Anal

Chaque compte du plan porte un code **Anal** (obligatoire). Une écriture n'a pas de code analytique propre : son Anal est celui de son compte.
Dans `Ecritures.xlsx`, les colonnes `Anal` et `LibelAnal` sont donc **informatives** (reprises du plan).

## Formats (ordre d'import)

| Fichier | Colonnes | Remarque |
|---|---|---|
| `Exercices` | Libellé, Début, Fin, Clos | |
| `Reglages` | Clé, Valeur, Description | nom de l'association, devise, options |
| `Anal` | Code, Libellé | codes Anal, ex. `REC.1` |
| `Prefixes` | Préfixe, Libellé | préfixes proposés pour numéroter les codes |
| `PlanComptable` | Compte, Libellé, Anal, Lettrable, Actif | `Anal` obligatoire |
| `AxesComptes` | Compte, puis une colonne par regroupement libre | regroupements de comptes (facultatif) |
| `Journaux` | Code, Intitulé, Type, Compte de trésorerie, Actif | banques, caisses, ventes, achats, OD, à-nouveaux |
| `Tiers` | Compte, Type, Nom, Prénom, Adresse, Code postal, Ville, Téléphone, E-mail | clients (411), fournisseurs (401), autres types ; seul `Nom` obligatoire |
| `Traductions` | Opération (hébreu), Traduction | si l'option est activée |
| `Budget` | Exercice, Nature, Compte, Anal, Montant | un budget porte sur un compte **ou** un code Anal |
| `Ecritures` | Mvt, Jnl, Date, Compte, LibelCompte, Libelle, Debit, Credit, Anal, LibelAnal, Lien, Let | un `Mvt` = une opération équilibrée |
| `Libelles` | idem `Ecritures` | ne change que les libellés ; Mvt retrouvés par leur contenu |
| `Liens` | Mvt, Lien, Description | documents restés en ligne, joints à leur Mvt |
| `Banque` | Journ, Date, Libelle, Debit, Credit | un seul modèle pour toutes les banques et caisses |

## Banque.xlsx : le relevé

- `Journ` : code du journal de la banque ou de la caisse (B1, B2, CA…).
- `Date` : date de l'opération.
- `Libelle` : libellé du relevé, **dans la langue d'origine** (l'hébreu est accepté).
- `Debit` : montant **sorti** du compte (dépense) ; `Credit` : montant **entré** (recette). Nombres positifs, une des deux colonnes renseignée.
- Pas de solde, pas d'état, pas de montant en devise d'origine : la comptabilité est en une seule devise.
- Une ligne déjà importée est ignorée : on peut reprendre un relevé qui chevauche le précédent.

Voir aussi `banques.md`.
