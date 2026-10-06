# ComptaJLC — contexte pour Claude Code

Comptabilité ordinaire, en ligne (application Django, base SQLite, hébergée sur
PythonAnywhere). Dépôt indépendant, issu de ComptaBB (copie renommée) : les deux
applications sont **différentes** ; on ne touche jamais à ComptaBB, on ne modifie
que ComptaJLC. Interface en français ; relevés bancaires possibles en hébreu.

## Principes

- Compta ordinaire : **plus de bénévoles, de fiches bénévoles ni de tiers provisoires**.
- **On ne parle plus de membres** : il y a des **tiers** (clients 411, fournisseurs 401,
  autres types des Référentiels). Plus d'adhésion, de statut ni de cotisation.
- **Deux modes** seulement : **Administration** (paramétrage de base, utilisateurs, base de
  données, imports / exports) et **Gestion** (tenue de la comptabilité). Plus de rôles
  Consultation ni Bénévole.
- Base neuve : aucune donnée de ComptaBB (ni plan, ni codes Anal, ni écritures).

## Un seul axe analytique : Anal

- Il n'y a **qu'un axe**, appelé **Anal**. Chaque compte du plan porte un code Anal
  (obligatoire) ; une écriture n'a **aucun** code analytique propre : son Anal est
  celui de son compte.
- Pas d'axe 2, pas de statut sur les codes (« En cours », « Terminé »… n'existent plus).
- Nom interne : `CodeAnalytique` (table des codes), `Compte.anal1` (lien du compte vers
  son code Anal — le nom `anal1` est conservé en interne), `Prefixe` (préfixes proposés
  pour numéroter les codes : préfixe + plus grand numéro + 1, ex. `COT.4`).
- Affichage : « Anal » partout (colonnes, menus, fichiers d'échange `Anal.xlsx`).

## Application

- Code : `appli/compta/` (modèles, vues, imports/exports, tests), projet Django
  `appli/comptajlc/`, déploiement `appli/deploiement/`.
- Tests : `cd appli && python manage.py test compta`.
- Montants : `Decimal`, formats `₪ #,##0.00` (devise par réglage), dates `jj/mm/aaaa`.
- Ce qui est propre à l'association (nom, devise, journaux de banque, carte, traductions)
  passe par `appli/compta/reglages.py` : jamais en dur dans le code.
- Site neuf : assistant de premier démarrage (`appli/compta/demarrage.py`) ; la base est
  créée vide (plan comptable de base facultatif).
- Fichiers d'échange : structure dans `docs/specification-fichiers.md`, modèles vides dans
  `Imports/modeles/`. Les données réelles (Imports/, Exports/, bases, classeurs) ne vont
  **jamais** dans Git.
- Une écriture existante se corrige ou se supprime depuis l'application (trésorier,
  jamais dans un exercice clos, historique conservé).
- Un Mvt = une opération équilibrée ; une ligne = débit **ou** crédit.
- Situation financière : colonnes « Solde » seulement, le mot « résultat » n'y figure pas.
- Licence (`appli/compta/licence.py`) : la clé privée de l'éditeur ne va jamais dans le dépôt.
- Documentation PDF : `docs/*.html` → `python appli/deploiement/documentation.py --sans-captures`.

## À reprendre (héritage de ComptaBB)

- `src/`, `tests/recette_*.py`, `docs/cahier-des-charges.md`, `docs/plan-lots.md`,
  `docs/inventaire.md` et `docs/livraison-*.md` décrivent le classeur Excel de ComptaBB et ses
  « lots » ; conservés pour mémoire, ils ne reflètent pas ComptaJLC.
- `docs/*.html` et les PDF (`docs/`, `appli/compta/documentation/`) portent encore le texte de
  ComptaBB (axes 1 et 2, membres, bénévoles) : à réécrire puis à régénérer.
- `appli/deploiement/documentation.py` (génération des PDF avec captures) crée des données
  d'exemple qui utilisent l'ancien modèle : à réécrire avant usage.

## Git

Branche `main` protégée ; une évolution = une branche et une pull request.
Commits courts, en français.
