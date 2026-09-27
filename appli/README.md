# ComptaBB — application web

Application web (Django) de la comptabilité de l'association. **Pour
l'instant elle tourne sur le PC du trésorier** : `ComptaBB.exe` démarre
l'application et ouvre le navigateur ; les données sont dans le dossier
`data` à côté du programme. Le jour où un hébergeur sera choisi, la même
application y sera installée pour l'accès à distance (bureau, bénévoles).

## Installer sur le PC

1. Récupérer le dossier `ComptaBB` produit par GitHub Actions (onglet
   Actions › « Application ComptaBB » › Run workflow › Artifacts) et le
   placer dans `D:\OneDrive\Applications\ComptaBB\appli`.
2. Double-cliquer `ComptaBB.exe`. Au premier lancement :
   - créer l'identifiant et le mot de passe du trésorier ;
   - indiquer le classeur `ComptaBB.xlsm` à reprendre (chemin complet).
3. Le navigateur s'ouvre sur `http://127.0.0.1:8765`. Fermer la fenêtre noire
   arrête l'application.

Données : `data\comptabb.sqlite3` (à sauvegarder), `data\secret.txt` (ne pas
partager). Hors de Git.

## Rôles

| Rôle | Droits |
|---|---|
| Administrateur | tous les droits, dont le paramétrage de base : Référentiels (plan comptable, journaux, préfixes, types de tiers, moyens de paiement, modèles d'opération, natures et modes des fiches, réglages), Paramètres (Excel), codes d'axe 1, paramètres des relevés, utilisateurs, base de données |
| Trésorier | tout, sauf le paramétrage de base |
| Bureau | consultation seule : tableau de bord, écritures, grand livre, balance, analytique, contrôles, journal |
| Bénévole | la liaison seulement : ses fiches bénévoles (saisie des lignes, nouveaux tiers provisoires, transmission) |

Il n'y a pas d'autre rôle. Chacun change son identifiant (un nom ou une
adresse e-mail) et son mot de passe dans **Mon compte** (clic sur son nom en
haut à droite) ; on se connecte avec l'identifiant ou l'e-mail enregistré.
L'administrateur crée les comptes dans Administration › Utilisateurs ;
un bénévole se crée aussi depuis Fiches bénévoles › Nouveau bénévole, en choisissant un membre (fiche tiers).

## Pages (socle W0)

Tableau de bord (produits, charges, résultat, trésorerie par journal,
résultat par axe 1 et 2, état des contrôles) · Écritures (filtres journal,
compte, axe 2, recherche) · Mouvement · Grand livre (solde cumulé) ·
Balance · Analytique · Contrôles (RG-01 à RG-04, comptes de liaison) ·
Journal des modifications (repris du classeur).

## Saisie (W1)

Saisie guidée d'une opération (aperçu des écritures, 11 contrôles bloquants,
un ou deux Mvt) · Codes (nouveau code analytique d'après le préfixe, nouveau
membre, statut d'un code axe 2). Toutes les listes se cherchent en tapant une
partie du code ou du libellé.

## Fiches bénévoles (W2)

Remplacent le fichier de liaison Excel (même conventions d'écritures, voir
`compta/fiches.py`).

1. Le trésorier crée la fiche : **Activité** (code axe 2 fixé d'avance, choisi ou créé sur place) ou
   **Gestion** (dons et aides reçus ou versés), et lui attribue un ou
   plusieurs bénévoles.
2. Le bénévole se connecte, note ses recettes et dépenses ; il cherche un
   membre existant ou crée un **nouveau tiers provisoire** ; puis il
   **transmet** la fiche.
3. Le trésorier attribue un compte aux tiers provisoires (Tiers provisoires),
   complète en Gestion le mode de paiement, le compte de contrepartie et le
   code axe 2, puis **reporte** : un Mvt par ligne (origine « Fiche
   bénévole »). Le report est refusé tant qu'une ligne est signalée ; les
   lignes reportées sont verrouillées.

Natures et modes de paiement des fiches : Référentiels (modifiables).
Tant que l'application tourne seulement sur le PC du trésorier, un bénévole
à distance n'y a pas accès : le trésorier saisit pour lui, ou l'accès distant
arrive avec l'hébergement.

## Rapprochement bancaire (W3)

Par journal de trésorerie (B1, B2, B3, CA) :

- **Import du relevé** : PDF Mizrahi en hébreu, Excel ou CSV (modèle
  `Imports/modeles/10_releve_B1.csv`). Les lignes déjà importées sont
  ignorées (clé : date, référence, montant, rang dans la journée). Au premier
  import, un solde d'ouverture est déduit du premier solde du relevé.
  Les opérations sont traduites (Rapprochement › Traductions).
- **Rapprochement automatique** : même montant, date à ± tolérance
  (réglage `tolerance_rapprochement`, 7 jours repris du classeur) ;
  l'à-nouveau est pointé contre le solde d'ouverture et les lignes du relevé
  antérieures à la date de reprise.
- **Pointage manuel** : cocher à gauche et à droite des lignes de même total
  (remise de chèques, frais regroupés) ; dépointage possible. L'identifiant
  (R…) est stocké côté relevé et côté écriture.
- **Créer l'écriture** depuis une ligne du relevé non pointée : la saisie
  s'ouvre pré-remplie et l'écriture est pointée à l'enregistrement.
- **État de rapprochement** à une date (écart non expliqué = 0) et écart par
  mois. La reprise du classeur reproduit l'onglet Banque1 : écart 2 910,00
  au 24/09/2026, 42 lignes du relevé et 38 écritures non pointées.

## Tiers et suivi des membres (W5)

- **Fiches tiers** (menu Tiers) : une par compte de tiers de chaque type
  (membres 411, fournisseurs 401, autres types des Référentiels), créées
  automatiquement et à chaque nouveau tiers (Codes › Nouveau tiers) ;
  adresse, code postal, ville, téléphone, e-mail ; pour les membres : adhésion,
  statut (actif, honoraire, démissionnaire), cotisation attendue ; import du
  modèle `Imports/modeles/07_membres.csv`.
- **Fiche membre** : facturé, réglé, solde dû, historique.
- Pas de suivi des impayés : le solde du compte tiers suffit ; **cotisations** de l'exercice attendues,
  facturées, reçues et taux de recouvrement (réglage `compte_cotisations`).
- **Lettrage** (colonne Let) : manuel sur des lignes équilibrées, automatique
  (même opération, puis premier règlement de même montant), annulable ;
  journalisé.

## Imports / Exports (administrateur)

Menu **Administration › Imports / Exports** (`compta/echanges.py`), en complément des imports des écrans Tiers
et Rapprochement. Un fichier `.xlsx` par nature de données (Exercices, Reglages, Axe1, Axe2, Prefixes,
PlanComptable, Journaux, Tiers, Traductions, Budget, Ecritures, Banque1, Banque2, Bit, Caisse), de même
structure à l'import et à l'export, décrit dans `Lexique.xlsx` et dans [`Imports/README.md`](../Imports/README.md).
Dossiers : les mêmes `Imports` et `Exports` que Paramètres (Excel), modifiables dans la page (réglages
`dossier_imports`, `dossier_exports`). Import tout ou rien, sauvegarde avant ; fichier rangé dans
`Imports/Importés`. Un relevé PDF Mizrahi se convertit en Banque1.xlsx ou Banque2.xlsx. **Tout réinjecter**
remplace écritures, relevés et budget par les fichiers présents.

## Base de données (administrateur)

Menu **Base** (compte administrateur, créé par `creer_administrateur`) : créer et télécharger des sauvegardes ; **remettre à zéro
et recharger** depuis une sauvegarde `.sqlite3` (tout, utilisateurs compris)
ou depuis le classeur `ComptaBB.xlsm` (plan, journaux, codes, écritures,
exercices, relevé ; utilisateurs gardés ; tiers recréés d'après les comptes,
coordonnées à réimporter avec Tiers.xlsx). Confirmation « REMPLACER » et
sauvegarde automatique juste avant ; journalisé.

## Journaux et historique

- **Journaux** (menu Journaux) : journal de trésorerie (B1, B2, B3, caisse)
  avec recette, dépense, contrepartie et solde progressif ; autres journaux
  (VT, HA, OD, AN) par mouvement ; période au choix, impression, Excel.
- **Historique** : toutes les opérations faites dans l'application (qui,
  quand, quoi), recherche, export Excel ; repris dans l'archive de clôture.

## États annuels et clôture (W4)

- **États** (menu États, exercice au choix, N comparé à N-1) : compte de
  résultat par compte, résultat par axe 1 et par axe 2, bilan simplifié
  (classes 1 à 5 ; résultat de l'exercice et résultats antérieurs non
  reportés), budget et réalisé avec écarts en montant et en %. Impression et
  téléchargement Excel.
- **Budget** : par compte (6 ou 7), par code d'axe 1 ou par code d'axe 2.
- **Clôture** (menu Clôture, trésorier) : exercices clôturés dans l'ordre ;
  blocage si mouvement déséquilibré ou bilan déséquilibré ; avertissements
  (contrôles, fiches non reportées, tiers provisoires). Crée **un** Mvt
  d'à-nouveaux (journal AN, 1er jour de l'exercice suivant) : soldes des
  classes 1 à 5, résultat affecté au compte de report (réglage
  `compte_report_a_nouveau`, 110000 par défaut). Crée l'exercice suivant
  s'il n'existe pas, verrouille l'exercice clos et enregistre une archive
  Excel figée (`data/archives`). Aucune écriture existante n'est modifiée.
- Après une clôture, les soldes des comptes de bilan repartent des
  à-nouveaux ; le rapprochement bancaire ignore ces à-nouveaux.

## Hébergement

Essai sur PythonAnywhere : `docs/hebergement-pythonanywhere.md`
(`python manage.py preparer`, `python manage.py creer_administrateur`,
`deploiement/pythonanywhere_wsgi.py`).

## Développement

```
cd appli
pip install -r requirements.txt
python manage.py migrate
python manage.py importer_classeur ../ComptaBB.xlsm
python manage.py createsuperuser
python manage.py runserver
python manage.py test compta
```

Reprise vérifiée sur les données réelles : 421 mouvements, 1 544 lignes,
débit = crédit = 1 451 040,66 ₪, résultat −47 366,41 ₪, identiques au classeur.
