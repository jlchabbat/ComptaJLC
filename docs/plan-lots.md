# Plan de réalisation par lots — proposition à valider

Étape 2 de la méthode du cahier des charges (§0) : présenter un plan par
lots et **attendre la validation** avant de toucher au classeur.

Ce plan s'appuie sur le cahier des charges et sur l'inventaire du classeur
`Fusion.xlsm` (`docs/inventaire.md`).

## Principe directeur : 100 % formules (réponse Q5)

Aucune macro, aucun Office Script. Tout ce que le cahier décrit comme une
action (« valider », « mettre à jour », « journaliser ») devient donc :

1. **une formule qui prépare** le résultat et affiche s'il est acceptable ;
2. **un geste manuel** de l'utilisateur : copier puis *Collage spécial ›
   Valeurs* à l'endroit indiqué, ou choix dans une liste déroulante ;
3. **un contrôle a posteriori** dans l'onglet Contrôles, qui signale tout
   ce que le geste manuel aurait mal fait.

Conséquences à accepter (voir « Arbitrages demandés » plus bas) :

| Exigence du cahier | Ce qu'une formule ne peut pas faire | Proposition |
|---|---|---|
| §4 Validation : « ajout en bas de T_Ecritures » | écrire dans une autre table | zone « Lignes à reporter » : n'affiche les lignes que si tous les contrôles bloquants sont OK, sinon un message en français ; l'utilisateur les colle en valeurs sous T_Ecritures |
| §4 Statut Anal2 : « la validation met à jour T_Axe2 et journalise auteur, date, ancien et nouveau statut » | modifier T_Axe2, connaître l'auteur, figer une date | le statut se change directement dans T_Axe2 (liste 0/1/2) ; l'écran prépare la ligne de journal (date du jour, code, ancien → nouveau) à coller en valeurs dans Journal des modifications, l'auteur étant choisi dans une liste |
| §4 « confirmation requise avant modification d'un code déjà utilisé » | bloquer une saisie | avertissement visible « code utilisé dans N écritures » à côté du choix, + ligne de Contrôles |
| §6 Pointage : identifiant stocké côté relevé et côté écriture | écrire dans deux tables | une table **T_Pointage** saisie à la main (identifiant, clé de la ligne de relevé, Mvt/ligne d'écriture), pré-remplie par les propositions automatiques ; relevé et écritures l'affichent par colonne calculée |
| §7 Verrouillage des périodes clôturées | refuser une saisie | validation de données sur les dates (Saisie et T_Ecritures) + contrôle RG-04 ; le collage contourne la validation, d'où le contrôle |
| §7 Archivage et §9 sauvegarde datée | copier un classeur | procédure écrite pas à pas dans le Compte rendu |

**Pourquoi T_Pointage plutôt qu'une colonne ajoutée à côté du relevé :** une
colonne saisie à la main à côté d'une table Power Query reste attachée à la
position de ligne, pas à la ligne elle-même ; au rafraîchissement suivant,
elle se décale. Une table séparée, indexée sur une clé stable de la ligne de
relevé (date + montant + référence + rang), ne bouge pas.

## Lot 0 — Préparation (branche `lot-0-preparation`)

- Inventaire du classeur → `docs/inventaire.md` (fait).
- **Sortir le grand livre de l'ancien logiciel.** T_Ecritures, T_PlanComptable,
  T_Journaux, T_Axe1, T_Axe2 et T_Prefixes sont rechargées par Power Query
  depuis les exports CSV de l'ancien logiciel ; un « Actualiser tout »
  effacerait les lignes Isracard (constat 1 de l'inventaire). Ces six
  tables sont **dissociées de leur requête** (Excel : Création de tableau ›
  Dissocier) : elles deviennent de simples tables, avec les mêmes noms, les
  mêmes colonnes et les mêmes données, et les requêtes correspondantes sont
  supprimées. Les CSV d'origine sont conservés dans `Imports/reprise/` pour
  l'historique. Aucune écriture n'est modifiée ; totaux vérifiés avant et
  après.
- **Chemins relatifs.** `Requête1` lit le chemin du relevé dans Paramètres,
  exprimé relativement au dossier du classeur (dossier calculé par
  formule, transmis à Power Query par une table de paramètres).
- Photographie des totaux de référence (`src/controles.py`) : nombre de
  lignes et de Mvt, Σ débit, Σ crédit, résultat, totaux par journal et par
  classe. Celle du classeur reçu est dans
  `tests/reference/2026-09-26-fusion.json`.
- Nommage des hypothèses (RG-06) : P_Debut, P_Fin, P_DebutExercice,
  P_FinExercice, P_DateCloture, P_Tolerance… dans Paramètres.
- Colonnes « Libellé Axe1 » / « Libellé Axe2 » dans toutes les tables et
  vues qui affichent un code (§3), avec « Code introuvable ».
- Exports de reprise dans `Imports/reprise/` et modèles dans
  `Imports/modeles/` (§6).

## Lot 1 — Saisie guidée (branche `lot-1-saisie`)

- **T_ModelesOperation** avec les 12 types minimum du §4. Les types à deux
  temps (cotisation puis règlement, virement interne 512x → 580000 →
  512y) génèrent deux Mvt.
- **Onglet Saisie** : cellules jaunes à texte bleu, listes déroulantes
  alimentées par les tables (types, tiers 411/401, journaux B1/B2/B3/CA,
  tous les codes T_Axe2 quel que soit leur statut), info-bulles.
- Numérotation proposée : `MAX(T_Ecritures[Mvt])+1`,
  `MAX(T_Ecritures[Pièce])+1`, et le suivant pour un second Mvt.
- Aperçu débit/crédit (tableau dynamique) + contrôles bloquants :
  équilibre, compte / journal / Anal2 existants, montant > 0, date dans
  l'exercice ouvert. Zone « Lignes à reporter » vide tant qu'un contrôle
  échoue.
- **Création de codes** : prochain code proposé = préfixe + (numéro
  maximal existant + 1) sur trois chiffres (ex. `MAN.013`), contrôle
  anti-doublon ; nouveau membre = compte `411` + 5 premières lettres du nom
  + rang sur trois chiffres (schéma existant : `411TAIEB001`) + ligne de
  fiche membre à coller.
- **Statut Anal2** : liste 0/1/2 dans T_Axe2, avertissement si code
  utilisé, ligne de journal préparée.
- **Journal des modifications** : table T_Journal (date, auteur, action,
  objet, ancien, nouveau).
- Tests : une saisie de chaque type d'opération, totaux inchangés hors
  écritures nouvelles.

## Lot 2 — Membres (branche `lot-2-membres`)

- **T_Membres** (compte 411, nom, prénom, téléphone, e-mail, adhésion,
  statut, cotisation attendue), initialisée depuis les 43 comptes 411.
- **Fiche membre** : facturé, réglé, solde dû, historique (FILTER),
  ancienneté des impayés 0–30 / 31–90 / > 90 jours.
- **États** : impayés triés par montant (SORT), cotisations de l'année
  attendues / reçues / taux de recouvrement, texte de relance prêt à
  copier.
- **Lettrage** : proposition de code lettre pour les couples facture /
  règlement de même montant, saisie manuelle dans Let ; contrôle « solde
  lettré = 0 ».

## Lot 3 — Rapprochement (branche `lot-3-rapprochement`)

- Requête Power Query générique (fonction paramétrée par journal et par
  chemin lu dans Paramètres) pour B2, B3 et la caisse, même structure que
  T_Banque1. **Requête1 / T_Banque1 ne sont pas modifiées** tant que la
  nouvelle requête ne reproduit pas le rapprochement Banque 1 à
  l'identique.
- T_Pointage + propositions automatiques (montant exact, date ± P_Tolerance
  jours), regroupements (une remise = plusieurs règlements ; frais
  mensuels groupés).
- État de rapprochement à date : solde relevé, solde comptable, non
  pointés des deux côtés, écart expliqué = 0 ; écart par mois.
- Depuis une ligne de relevé non pointée : écriture proposée via
  T_ModelesOperation, à reporter comme au Lot 1.
- Analyse de l'existant : écart Banque 1 de 2 910,00 (Mvt 285, Mvt 177),
  virement de 20 917 daté différemment, solde B3 négatif.

## Lot 4 — Clôture et états (branche `lot-4-cloture`)

- Paramètres d'exercice et verrouillage (RG-04).
- Balance, grand livre, compte de résultat par nature et par Anal1 /
  Anal2, bilan simplifié, comparaison N / N-1.
- T_Budget, budget vs réalisé, écarts en %.
- À-nouveaux préparés (journal AN, classes 1 à 5, résultat en 110000 ou
  12x), à reporter en valeurs ; contrôle bilan équilibré avant / après ;
  procédure d'archivage.

## Livraison de chaque lot

Sauvegarde du classeur → Contrôles = OK → `src/controles.py` sans
anomalie et totaux identiques à la photographie précédente (hors écritures
nouvelles) → README, CLAUDE.md, Compte rendu et Journal des modifications
à jour → pull request vers main → fusion après votre validation.

## Arbitrages demandés

0. **Dissocier les six tables de leur requête** (Lot 0 ci-dessus) : c'est
   le passage de relais de l'ancien logiciel à Excel. Après cela, l'ancien
   logiciel ne doit plus être utilisé pour saisir, sinon les deux
   divergent. D'accord ?
1. **Q1 — exercices.** Les soldes d'ouverture sont passés au 01/01/2026
   en B1 et CA contre 110000, sans journal AN, et 52 lignes datent d'avant
   (du 25/10 au 31/12/2025). Lecture proposée : ces 52 lignes forment un
   premier exercice court, clos au 31/12/2025, et l'exercice 2026 va du
   01/01 au 31/12/2026. Deux points à confirmer : les soldes d'ouverture de
   B1 et CA tiennent-ils déjà compte de ces 52 lignes ? Faut-il réaliser
   la clôture 2025 dès maintenant (ce qui avancerait une partie du Lot 4) ?
2. **Q2 — Isracard.** Lecture proposée : chaque dépense carte en 6xx
   contre 580000 ; le prélèvement mensuel Isracard en 580000 contre 512.
   580000 se solde ainsi à chaque relevé. Est-ce bien cela ? Les cinq
   paiements Isracard déjà intégrés (Mvt 412 à 416) sont passés en 600000
   contre 512000, compte que l'onglet « Écritures à passer » dit
   « validé » : faut-il les laisser ainsi, ou les reclasser (ce qui
   modifie des écritures existantes) ?
3. **Q3 — mise en attente.** Sur quel compte : 470000 « CPTES
   D'ATTENTE » (existe déjà), ou le 580000 ?
4. **Q5 — limites du 100 % formules** (tableau plus haut) : acceptez-vous
   le copier-coller en valeurs pour reporter les écritures, le statut et
   la ligne de journal ?
5. **Q6 — plusieurs saisisseurs.** Proposition : un mode consultation =
   onglets protégés sans mot de passe ; un saisisseur externe travaille
   sur une copie et transmet sa zone « Lignes à reporter », que le
   trésorier colle après vérification. Suffisant ?
6. **Q4 — libellés Anal2** : toujours à fournir.
