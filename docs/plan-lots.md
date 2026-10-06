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

## Lot 0 — Préparation : **livré le 26/09/2026** (voir `docs/livraison-lot0.md`)

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
- Nommage des hypothèses (RG-06) : P_DebutExercice, P_FinExercice,
  P_DateCloture, P_DernierMvtClos, P_CompteVirement, P_CompteAttente,
  P_Dossier, P_ReleveB1 dans Paramètres (fait).
- Reclassement Isracard, suppression des codes Anal2 vides, soldes et
  « Code suivant » calculés, contrôle RG-04, Journal des modifications
  (fait).
- Reporté au Lot 1 : colonnes « Libellé Axe1 / Axe2 » dans les vues qui
  n'en ont pas encore, exports de reprise dans `Imports/reprise/`.

## Lot 1 — Saisie guidée : **livré le 26/09/2026** (voir `docs/livraison-lot1.md`)

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
- **Création de codes** : l'utilisateur choisit le préfixe et saisit le
  libellé ; le code est proposé par T_Prefixes[Code suivant] (numéro
  maximal existant + 1, sur 1 chiffre pour l'axe 1, 3 pour l'axe 2),
  avec contrôle anti-doublon ; nouveau membre = compte `411` + 5 premières lettres du nom
  + rang sur trois chiffres (schéma existant : `411TAIEB001`) + ligne de
  fiche membre à coller.
- **Statut Anal2** : liste 0/1/2 dans T_Axe2, avertissement si code
  utilisé, ligne de journal préparée.
- **Journal des modifications** : table T_Journal, créée au Lot 0 ; lignes
  de journal préparées par l'écran, à coller.
- **Classeur de saisie externe** `ComptaJLC_Saisie.xlsx` et zone
  « Transmission » du maître (voir « Accès à distance »).
- Modèle d'opération « Paiement carte Isracard » : 6xx contre 580000, puis
  580000 contre 512000 au prélèvement (décision Q2).
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

## Décisions du trésorier (26/09/2026)

| Question | Décision | Où c'est appliqué |
|---|---|---|
| Ancien logiciel | Les 6 tables sont dissociées ; Excel est la seule référence | Lot 0 |
| Q1 — exercices | Exercice court 25/10/2025 → 31/12/2025, à clôturer au 31/12/2025 ; exercice 2026 du 01/01 au 31/12 | Lot 0 (paramètres, verrou RG-04) ; à-nouveaux au Lot 4 |
| Q2 — Isracard | Dépenses en 6xx contre 580000, prélèvement mensuel en 580000 contre 512 ; Mvt 412 à 416 reclassés | Lot 0 (Mvt 417 à 421) ; modèle d'opération au Lot 1 |
| Q3 — attente | Compte 470000 | Lot 0 (P_CompteAttente) ; écritures d'attente au Lot 3 |
| Q4 — codes Anal2 | Codes vides supprimés. **Le code est proposé par l'application d'après le préfixe choisi ; l'utilisateur ne saisit que le libellé.** Colonne Axe de T_Prefixes : 1 = axe 1, 2 = axe 2 | Lot 0 (suppression, « Code suivant » calculé) ; écran de création au Lot 1 |
| Q5 — macros | 100 % formules, report par collage en valeurs | Tous les lots |
| Q6 — saisisseurs | Onglets protégés en consultation ; un saisisseur externe envoie ses lignes au trésorier | Lot 1 (classeur de saisie), voir « Accès à distance » |
| Mode de travail | Le classeur `.xlsm` est modifié directement ; Claude Code sera aussi installé sur le PC (section 13 du cahier) | — |

Points encore ouverts : voir `docs/livraison-lot0.md`.

## Accès à distance : consultation et transmission

**Principe : le dossier `ComptaJLC` n'est jamais partagé en entier**, car il
contient le classeur maître et les relevés bancaires. On ouvre deux accès
distincts par OneDrive, chacun limité à ce qu'il faut. La protection des
onglets (sans mot de passe, §9) évite les erreurs de manipulation. **Ce sont
les droits OneDrive qui contrôlent réellement l'accès.**

### 1. Consultation (bureau, vérificateur) : lecture seule

| | Option A : lien vers le classeur maître | Option B : copie de consultation |
|---|---|---|
| Quoi | Lien OneDrive « Peut afficher » sur `ComptaJLC.xlsm` | `Consultation\ComptaJLC_Consultation.xlsx`, copie figée en valeurs, sans les onglets de données personnelles |
| Fraîcheur | Toujours à jour | Mise à jour par le trésorier (après chaque clôture mensuelle, par exemple) |
| Ouverture | Excel pour le web, dans le navigateur, sans rien installer | Idem |
| Limite | Le lecteur voit tous les onglets (dont les membres au Lot 2) et peut télécharger une copie | Travail manuel : pas de macro d'export (Q5) |

Recommandation : **A pour le bureau tant qu'il n'y a pas de données
personnelles**, puis **B dès le Lot 2** (fiches membres), ou pour toute
personne extérieure au bureau.

Réglages du lien, dans OneDrive › Partager :
- choisir « Personnes spécifiques » (adresses e-mail), jamais « Toute
  personne disposant du lien » ;
- droit « Peut afficher » ;
- date d'expiration, et mot de passe avec un abonnement Microsoft 365
  Personnel ou Famille ;
- retrait à tout moment par « Gérer l'accès ».

### 2. Transmission (saisisseur externe) : dossier partagé en modification

1. Un dossier `Transmissions\` est partagé en « Peut modifier » avec le
   seul saisisseur.
2. Il contient un **classeur de saisie** `ComptaJLC_Saisie.xlsx` (livré au
   Lot 1). On y trouve l'onglet Saisie, les modèles d'opération et les listes
   de référence (comptes, journaux, codes Anal2) copiées en valeurs, mais
   **aucune écriture** du grand livre.
3. Le saisisseur remplit ses opérations ; les contrôles bloquants
   s'appliquent comme dans le maître. OneDrive synchronise à
   l'enregistrement.
4. Le trésorier ouvre le fichier et vérifie. Il colle les lignes prêtes
   dans la zone « Transmission » du classeur maître. **La numérotation
   définitive (Mvt, Pièce) se fait dans le maître** au moment du report, ce
   qui évite les doublons. Le report passe ensuite en valeurs sous
   T_Ecritures.
5. Une ligne est ajoutée au Journal des modifications (« Transmission de …
   du … »), puis le fichier de transmission est archivé et remis à zéro.

**Pourquoi pas la coédition du classeur maître :** l'accès simultané est
exclu par le cahier (§2). Sans macro, rien n'empêcherait non plus un
collage erroné dans T_Ecritures : seuls les contrôles a posteriori le
détecteraient.
