# ComptaJLC : spécification des fichiers (version de travail du 02/10/2026)

Objet : une gestion d'association **sans TVA**, **mono-devise**, confiée à des **bénévoles néophytes** en informatique et en
comptabilité. Tous les échanges se font par fichiers **Excel (.xlsx, .xlsm en import) ou .csv**, avec **la même structure à l'import et à l'export**.
Le reste de l'application (écrans, fenêtres, fonctions) est conservé.

## 1. Règles communes à tous les fichiers

| Règle | Choix |
|---|---|
| Format | **Excel `.xlsx` ou `.xlsm`** (format principal ; les macros et requêtes Power Query de l'administrateur servent à adapter les fichiers d'autres horizons : l'application lit seulement les valeurs, jamais les macros) ; si le classeur a plusieurs feuilles, celle qui porte le nom du fichier voulu (Ecritures, Banque1…), sinon la première. `.csv` accepté aussi (séparateur `;`, UTF-8 avec BOM). Les exports sont des `.xlsx` |
| Première ligne | exactement les noms de rubriques ci-dessous |
| Noms de rubriques | abréviations sans espace ni accent : `Mvt`, `Jnl`, `Compte`, `LibelCompte`, `Libelle`… |
| Dates | `jj/mm/aaaa` |
| Montants | nombres avec virgule décimale, sans symbole, un seul de `Debit` / `Credit` par ligne |
| Import | tout ou rien ; sauvegarde automatique avant ; messages d'erreur en français, avec n° de ligne et correction proposée |
| Rubriques inconnues | ligne refusée avec le nom attendu |

## 2. Les fichiers

### Plan comptable (`PLA`) : un compte = une ligne
`Compte`, `LibelCompte`, `Anal1`, `LibelAnal1`, `Utilise`, `Lettrable`
- `Anal1` = nature du compte (axe 1), toujours attaché au compte ; `LibelAnal1` est recopié, pas saisi.
- `Utilise` (O/N) : compte proposé ou non en saisie ; `Lettrable` (O/N) : comptes de tiers.
- Plus aucune rubrique TVA.

### Axe 1 (`AN1`) : liste à choisir pour chaque compte
`Anal1`, `LibelAnal1`
- Alimente la **liste déroulante** de l'écran du plan comptable. Un compte ne peut recevoir qu'un code de cette liste.

### Axe 2 (`AN2`) : manifestations et projets, indépendant du plan
`Anal2`, `LibelAnal2`, `Statut` (0 non affecté, 1 en cours, 2 terminé)
- Choisi **seulement** à la saisie d'une écriture ou lors du rapprochement d'un relevé bancaire (liste déroulante).
- Les codes sont proposés par l'application (préfixe + numéro suivant) ; le bénévole ne saisit que le libellé.

### Journaux (`JNL`) : définissent le nombre de banques et de caisses
`Jnl`, `LibelJnl`, `Type`, `Compte`, `Utilise`
- Types : `AN` à-nouveaux, `BQ` banque, `CA` caisse, `OD` opérations diverses, `HA` achats, `VE` ventes.
- Autant de lignes `BQ` que de banques (B1, B2, B3…), autant de `CA` que de caisses ; `Compte` = compte de trésorerie du journal.
- Un journal `AN`, `OD`, `HA` et `VE` est obligatoire et ne peut pas être supprimé.

### Écritures (`ECR`) : une ligne = un débit ou un crédit
`Mvt`, `Jnl`, `Date`, `Compte`, `LibelCompte`, `Libelle`, `Debit`, `Credit`, `Anal1`, `LibelAnal1`, `Anal2`, `LibelAnal2`, `Lien`, `Let`
- **Pas de numéro de pièce.** Un `Mvt` = une opération équilibrée (débit = crédit).
- `Anal1`, `LibelAnal1`, `LibelCompte` : informations d'affichage, **reprises du plan** à l'import (le plan fait foi).
- `Lien` : adresse du document justificatif (ou nom du fichier rattaché sur le site).
- `Let` : code de lettrage de **3 lettres majuscules** (`AAA`, `AAB`…), vide hors comptes lettrables ; les lignes d'un même compte portant le même code se compensent (facture et règlement d'un membre).

### Relevés bancaires (`BQE`) : un fichier par banque ou par import
`Jnl`, `Date`, `Libelle`, `Debit`, `Credit`
- `Jnl` = code du journal de banque ; `Libelle` = texte de la banque **dans sa langue d'origine** (hébreu conservé) ; `Debit` = entrée, `Credit` = sortie ; `Solde` **facultatif** (Bit n'en donne pas) : s'il est présent, il sert à déduire le solde d'ouverture du premier import et à contrôler le relevé. Plus de référence.
- La traduction et le rapprochement (pointage, affectation, `Anal2`) se font dans l'écran Rapprochement, comme aujourd'hui.

### Utilisateurs (`USR`)
`Util`, `Nom`, `Profil`, `Actif`
- Le **mot de passe n'est jamais dans un fichier** (ni en clair ni chiffré) : il se crée et se change dans l'application ; un nouvel utilisateur reçoit un mot de passe provisoire à changer à la première connexion.

| Profil | Peut faire |
|---|---|
| Administration | tout : utilisateurs, plan comptable, axes, journaux, imports, exercices, clôture, sauvegardes, suppression d'écritures |
| Gestion | saisie, modification et suppression d'écritures, rapprochements, justificatifs, tiers, éditions |
| Consultation | voir et éditer (PDF, Excel) ; aucune modification |

## 3. Ce qui change dans l'application existante

| Sujet | Aujourd'hui | Cible |
|---|---|---|
| Format d'échange | un .xlsx par format (15 fichiers) | .csv, même structure en import et en export |
| Moteurs d'import/export | 4 chemins (Imports/Exports, Paramètres Excel, Base de données, Référentiels) | un seul moteur |
| Pièce | `Pièce` dans les écritures | supprimée |
| Rubriques | `Anal1`/`Anal2` mal nommées selon les écrans | `Anal1`, `LibelAnal1`, `Anal2`, `LibelAnal2` partout |
| Devise | une devise par journal, cours BCE (#17) | **mono-devise** : retrait |
| TVA | colonne dans le modèle du plan | retirée |
| Axe 1 des comptes | modifiable via l'administration Django | liste déroulante dans l'écran du plan comptable |
| Journaux, comptes, axes | écran d'administration Django (« Référentiels ») | écrans de l'application, avec « Retour » |
| Utilisateurs | groupes Django | 3 profils (Administration, Gestion, Consultation) |

## 4. Pour des bénévoles néophytes

- Chaque écran : un titre, une phrase d'aide, un bouton « Retour » ; aucun vocabulaire comptable non expliqué (« Débit » = « Entrée ou sortie d'argent » en infobulle).
- Listes déroulantes partout où le choix est fermé (comptes, axes, journaux, profils) ; jamais de code à retaper.
- Erreurs d'import en clair : « Ligne 12 : le compte 512300 n'existe pas. Ajoutez-le dans le plan comptable. »
- Sauvegarde automatique avant tout import et à chaque clôture ; bouton « Revenir à la sauvegarde ».
- Journal des modifications visible, avec l'auteur.

## 5. Plan de réalisation (une pull request par étape, tests au vert à chaque étape)

1. Noms de rubriques et suppression de `Pièce`, de la TVA et de la devise (avec migration des données existantes).
2. Un seul moteur d'import/export CSV pour les 6 fichiers (`PLA`, `AN1`, `AN2`, `JNL`, `ECR`, `BQE`).
3. Écrans de l'application pour plan comptable (liste déroulante `Anal1`), axes, journaux ; le lien vers l'administration Django disparaît du menu.
4. Utilisateurs et 3 profils d'autorisation.
5. Import des relevés `BQE` et rapprochement sur la nouvelle structure.
6. Aide intégrée et mode d'emploi pour les bénévoles.

## 6. Points à confirmer

1. ~~Lettrage~~ : **décidé le 02/10/2026** : rubrique `Let` conservée en dernière colonne des écritures.
2. ~~Compte et axe 1~~ : **décidé** : à l'import, le plan fait foi, avec un avertissement en cas de différence.
3. ~~Mot de passe~~ : **décidé** : jamais dans un fichier, création et changement dans l'application.
4. ~~Données existantes~~ : **décidé** : une conversion unique de la base actuelle vers la nouvelle structure, avec sauvegarde avant.
5. ~~Mono-devise~~ : **décidé et réalisé** (étape 1) : devise par journal, montants d'origine et cours de change retirés.

## 6 bis. Compléments du 02/10/2026

### Fichiers venus d'une autre application
Aucun format d'une application tierce n'est lu par ComptaJLC : les fichiers issus de **n'importe quelle autre application de
comptabilité** sont **adaptés par l'administrateur** à la structure définie ci-dessus (modèles dans `Imports/modeles/csv/`),
puis importés. Un message d'erreur en français indique la ligne et la rubrique à corriger.

### Rôle des fichiers d'import et réimport
- Les fichiers d'import servent **à l'ouverture d'une comptabilité** à partir d'une comptabilité existante ; ils ne sont pas faits pour un usage courant.
- S'ils sont **réimportés**, l'application n'ajoute **aucun doublon** et **détecte les modifications** :
  - un élément déjà présent et identique est compté « inchangé » ;
  - un élément dont le fichier change une valeur est « mis à jour » (tracé dans le Journal des modifications) ; les écritures modifiées sont listées par n° de Mvt ;
  - une écriture déjà en compta sous un autre numéro (même date, journal, comptes et montants) est **écartée** et signalée, sans bloquer le reste du fichier ;
  - rien n'est jamais supprimé par un import ; une erreur de structure ou de contenu refuse tout le fichier (tout ou rien).
- Les relevés bancaires gardent en plus leur historique d'importation (une ligne déjà importée n'est jamais ajoutée deux fois).

### Utilisateur type
L'administrateur est lui aussi un **bénévole néophyte** : tout ce qui est réservé à l'administration (imports, utilisateurs, plan, journaux, clôture) passe par des écrans guidés, avec un résumé de ce qui va changer avant d'enregistrer et une sauvegarde automatique.

### Relevés bancaires et historique d'importation
- Le relevé s'importe **dans la langue d'origine** (`Banque.csv` : `Jnl`, `Date`, `Libelle`, `Debit`, `Credit`, `Solde` facultatif).
- Chaque import est gardé dans un **historique** (fichier, date, journal, lignes ajoutées, doublons ignorés) ; une ligne déjà importée (même journal, date, libellé et montant ; deux lignes identiques le même jour comptent pour deux) n'est jamais ajoutée deux fois, même si le même relevé est redéposé ou chevauche le précédent.

### Lexique de traduction
- Nouveau fichier **Lexique** (`Lexique.csv`) : `LibelBanque`, `LibelTrad`, `Compte` (compte habituellement affecté à ce libellé, facultatif).
- Dans Rapprochement, **le survol du libellé de la banque** affiche sa traduction ; le libellé proposé pour l'écriture peut être **modifié** avant la validation, et c'est lui qui est enregistré dans l'écriture rapprochée. La traduction modifiée peut aussi être ajoutée au lexique.
- Le fichier actuel `Lexique.xlsx` (description des formats d'échange) est renommé `Structure` pour éviter la confusion.

### Dossier de travail `AppliBB`
- Un dossier unique `D:\OneDrive\AppliBB\` avec `Imports` et `Exports`, **paramétrable dans l'application** (Administration › Paramètres).
- ⚠ L'application étant en ligne, **le site ne peut pas écrire sur le disque du PC** : les exports se téléchargent (le navigateur les range dans le dossier choisi) et les imports se déposent par le bouton « Déposer ». Le réglage mémorise le dossier habituel et l'affiche dans les consignes ; le site garde sa propre copie datée.
- Aucun chemin absolu en dur dans le code : tout vient du réglage.

### Exports datés
- Tout export est nommé `Nom_AAAA-MM-JJ_HHMM.csv` (par exemple `Ecritures_2026-10-02_1530.csv`) : jamais d'écrasement d'un export précédent.

## 7. Modèles CSV

Un modèle de chaque fichier, avec quelques lignes d'exemple neutres, est dans `Imports/modeles/csv/` :
`Plan.csv`, `Anal1.csv`, `Anal2.csv`, `Journaux.csv`, `Ecritures.csv`, `Banque.csv`, `Utilisateurs.csv`.
Ordre d'import conseillé : Anal1, Anal2, Plan, Journaux, Utilisateurs, Ecritures, Banque.
