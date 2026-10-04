# ComptaJLC

Compta web en français (Flask, SQLite, PythonAnywhere). Dépôt indépendant de ComptaBB.

- Code : `comptajlc/` (models, vues, initial, templates). Tests : `python -m unittest discover tests`.
- Montants en centimes (entiers). Pas de plan comptable ni de code analytique en dur : tables modifiables.
- Interface et messages en français. Pas de secret ni de base `.db` dans Git.
- Axe 1 = rubrique du compte (`Compte.axe1_code`) ; Axe 2 = `Ligne.axe2_code`, facultatif, comptes de classe `AXE2_CLASSES` (67) seulement. Imports CSV dans `comptajlc/imports.py` (UTF-8 ou Windows-1252, tout ou rien).
- Les fichiers de données réelles de l'association (plan, codes, écritures) ne vont jamais dans le dépôt (public) : les tests utilisent des CSV fictifs.
- Base existante : `comptajlc/initial.py` (`migrer`) ajoute les colonnes manquantes au démarrage.
- Droits : deux niveaux (admin, gestion) dans `auth.py` (`DROITS`, `EXIGE`, refus par défaut). Tout nouvel écran doit être déclaré dans `EXIGE`.
- Tableaux : `table.grille` avec `thead`/`tbody`, `data-v` (valeur brute, centimes pour les montants), `th data-total="cents"` pour les totaux, `data-group` pour regrouper les lignes d'une écriture, `tfoot.serveur` pour le total sans JavaScript. La logique est dans `static/grille.js` (testée dans Chromium, pas par `unittest`).
