# Import des fichiers CSV

Ordre à respecter : **1. codes Axe 1, 2. codes Axe 2, 3. plan comptable, 4. écritures.**
Fichiers CSV séparés par « ; », enregistrés en UTF-8 ou en Windows-1252 (export Excel français). La première ligne contient
les titres de colonnes (l'ordre des colonnes n'a pas d'importance, les accents et majuscules non plus).
**Tout ou rien** : si une ligne est refusée, rien n'est importé et le message indique les lignes à corriger.

## Codes Axe 1 et Axe 2 (page « Codes des axes »)
`Code;Libellé;Statut` — Statut : `En cours`, `Terminé` ou `Non affecté` (vide = En cours).
Un code existant est mis à jour. Case facultative : supprimer les codes inutilisés absents du fichier.

## Plan comptable (page « Plan comptable »)
`Compte;Libellé;Axe 1;Lettrable;Actif` — Lettrable et Actif : `Oui` / `Non`. L'Axe 1 doit être un code déjà importé.

## Écritures (page « Journal »)
Une ligne = un débit **ou** un crédit ; les lignes d'une même opération partagent le même `Mvt`.

| Colonne | Obligatoire | Rôle |
|---|---|---|
| `Mvt` | oui | numéro de l'opération : conservé et refusé s'il existe déjà, **sauf** avec la case « Renuméroter à la suite des écritures existantes » (numéros consécutifs après le dernier numéro ; l'ancien numéro est noté dans l'historique) |
| `Jnl` | oui | code du journal (créé s'il n'existe pas) |
| `Date` | oui | `jj/mm/aaaa` |
| `Compte` | oui | numéro de compte (créé s'il n'est pas au plan) |
| `Libelle` | oui | libellé de l'opération (le premier du mouvement est retenu) |
| `Debit`, `Credit` | oui | montants, ex. `1 600.00` ou `1600,50` |
| `LibelCompte` | non | libellé d'un compte à créer |
| `Anal1` | non | Axe 1 d'un compte à créer ; ignoré pour un compte déjà au plan (l'Axe 1 vient du compte) |
| `Anal2` | non | code Axe 2 ; **conservé seulement sur les comptes de classe 6 et 7**, ignoré ailleurs |
| `Lien` | non | adresse `http(s)://` du justificatif |
| autres colonnes | non | ignorées (`LibelAnal1`, `LibelAnal2`, `Let`…) |

Contrôles : chaque mouvement doit être équilibré, avec un seul journal et une seule date.
