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
- Depuis le Lot 0, les tables T_* sont de simples tables : plus aucune
  n'est rechargée depuis l'ancien logiciel. Seule requête : `Requête1`
  (relevé Banque 1, chemin `CheminReleveB1` = `P_Dossier` + `P_ReleveB1`).
- `src/powerquery/*.pq` : code M des requêtes, à tenir identique au classeur
  (`docs/historique/` : requêtes supprimées).
- `src/lot0_preparation.py` : exemple d'édition directe du XML (tables,
  commentaires à thread, DataMashup, chaînes partagées).
- `src/lot1_saisie.py` : onglets Saisie, Codes, Modèles (appliqué après le Lot 0).
  Paramètres de saisie dans T_ModelesOperation / T_Schemas / T_Paiements /
  T_TypesTiers ; calculs intermédiaires nommés `SA_*` (Saisie!Q:R masquées).
- `src/lot1_distance.py` : onglet Transmission (T_Recu), Libellé Axe1 du plan,
  protection sans mot de passe des onglets de consultation (pas des onglets
  dont les tables s'agrandissent). `src/classeur_saisie.py` : classeur du
  saisisseur à distance (T_Envoi, référentiels en valeurs, sans grand livre).
- `src/classeur_liaison.py` : fichier de liaison bénévole (Activité, Gestion, Tiers,
  Export vers Transmission), formules simples testées par `tests/recette_liaison.py`.
- `src/controles.py` : contrôles et photographie des totaux, lecture seule.
- `tests/recette_lot1.py` : scénarios de saisie recalculés par LibreOffice
  (formules sans LET/FILTER seulement : LibreOffice 24.2 ne les connaît pas ;
  AGGREGATE en mode tableau non plus). `tests/recette_lot1_distance.py` : idem pour
  la saisie à distance.
- `Imports/` et `Exports/` : échanges de l'application web par fichiers .xlsx
  (`appli/compta/echanges.py`) ; `Imports/modeles/` : modèles vides et
  Lexique.xlsx, versionnés ; le reste est hors Git (données réelles).
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
- Une opération avec tiers = un Mvt de 4 lignes dans le journal du paiement
  (facture puis règlement) ; sans règlement : 2 lignes en VT (recette) ou HA.
- Pas de code de format de date dans TEXT (dépend de la langue d'Excel) :
  `TEXT(DAY(d),"00")&"/"&TEXT(MONTH(d),"00")&"/"&YEAR(d)`.
- Comptes membres `411` + 5 lettres du nom + rang (`411TAIEB001`).
- Codes analytiques **proposés par l'application** : préfixe choisi +
  T_Prefixes[Code suivant] (plus grand numéro + 1 ; 1 chiffre axe 1 `ACT.4`,
  3 chiffres axe 2 `MAN.008`) ; l'utilisateur ne saisit que le libellé.
  T_Prefixes[Axe] : 1 = axe 1, 2 = axe 2. Statut T_Axe2[Actif] : 0 Non
  affecté, 1 En cours, 2 Terminé.
- Paramètres nommés dans Paramètres!D3:F16 (P_DebutExercice, P_FinExercice,
  P_DateCloture, P_DernierMvtClos, P_CompteVirement 580000, P_CompteAttente
  470000, P_Dossier, P_ReleveB1).
- Toute modification est inscrite dans l'onglet Journal des modifications
  (T_Journal).
- Colonnes « Libellé Axe1/Axe2 » à côté de tout code affiché ; « Code
  introuvable » si le code est inconnu.
- Saisie : cellules jaunes, texte bleu ; formats `₪ #,##0.00`, `jj/mm/aaaa` ;
  messages en français.
- Écriture ajoutée hors saisie guidée : fond coloré + commentaire (date,
  origine, motif), comme les lignes Isracard (Mvt 412 à 421).

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
