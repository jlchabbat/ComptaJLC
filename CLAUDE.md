# ComptaBB — contexte pour Claude Code

Comptabilité d'une association israélienne (Loge Bnei Brith, ₪) tenue
dans un classeur Excel Microsoft 365. Utilisateurs non comptables :
trésorier, bureau, vérificateur. Interface en français ; relevés bancaires
en hébreu. Référence : `docs/cahier-des-charges.md` (la feuille « CDC
ComptaBB » du classeur fait foi).

## Architecture

- `ComptaBB.xlsm` (nom dans `config.json`, hors Git) : tout le métier est en
  **formules** (réponse Q5 : ni VBA ni Office Scripts). Tables structurées
  T_* ; noms P_* pour les hypothèses ; onglet Contrôles = référence.
- `src/powerquery/*.pq` : code M des requêtes, à tenir identique au classeur.
- `src/controles.py` : contrôles et photographie des totaux, lecture seule.
- `Imports/` : modèles (`modeles/`, anonymisés, versionnés) et exports de
  reprise (`reprise/`, hors Git).
- État détaillé du classeur : `docs/inventaire.md`. Plan : `docs/plan-lots.md`.

## Commandes

```
python src/controles.py [classeur] [--photo f.json] [--compare f.json]
python -m unittest discover tests
```

## Interdits (cahier §0, §8)

- Ne jamais modifier ni supprimer une écriture existante sans accord
  explicite.
- Pas de valeur métier en dur dans une formule : cellule nommée ou table.
- Ne pas casser les tables T_* ni la requête « Requête1 » (T_Banque1).
- **Ne jamais enregistrer le classeur avec openpyxl** ou une autre
  bibliothèque qui le réécrit : Power Query, commentaires à thread,
  validations étendues et graphiques seraient perdus. Le modifier dans
  Excel, ou par édition directe et vérifiée du XML.
- Aucun chemin absolu (`D:\…`, nom d'utilisateur) : tout est relatif au
  dossier du projet.
- Ne pas versionner classeurs, exports réels, fichiers `~$*`, secrets.

## Conventions

- Un Mvt = une opération équilibrée ; une ligne = débit **ou** crédit.
- Nouveau Mvt = `MAX(T_Ecritures[Mvt])+1`, Pièce = `MAX(Pièce)+1`.
- Comptes membres `411` + 5 lettres du nom + rang (`411TAIEB001`).
- Codes analytiques : préfixe + numéro sur 3 chiffres (`MAN.013`) ; statut
  T_Axe2[Actif] : 0 Non affecté, 1 En cours, 2 Terminé.
- Colonnes « Libellé Axe1/Axe2 » à côté de tout code affiché ; « Code
  introuvable » si le code est inconnu.
- Saisie : cellules jaunes, texte bleu ; formats `₪ #,##0.00`, `jj/mm/aaaa` ;
  messages en français.
- Écriture ajoutée hors saisie guidée : fond coloré + commentaire (date,
  origine, motif), comme les lignes Isracard (Mvt 412 à 416).

## Git

Branche `main` protégée ; un lot = une branche (`lot-1-saisie`,
`lot-2-membres`, `lot-3-rapprochement`, `lot-4-cloture`) et une pull
request. Commits courts, en français.

## Critères d'acceptation d'un lot

Aucune erreur de formule ; Contrôles = OK ; `src/controles.py` sans
anomalie et totaux identiques à la photographie précédente, hors
écritures nouvelles ; saisie testée pour chaque type d'opération ;
rapprochement Banque 1 inchangé ; Accueil, Compte rendu, README et
journal des modifications à jour.
