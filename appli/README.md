# ComptaBB — application web

Application web (Django) de la comptabilité de l'association.

L'application est utilisée **en ligne** sur PythonAnywhere
(https://comptabb.pythonanywhere.com ; mise à jour :
`docs/ComptaBB_protocole_mise_a_jour.pdf`, script `deploiement/maj.sh`).
L'ancien programme du PC (`ComptaBB.exe`) est abandonné et retiré du dépôt.

Données (hors Git) : dossier `comptabb-data` du site (`comptabb.sqlite3`,
`secret.txt`, justificatifs, Imports, Exports, sauvegardes).

## Rôles

| Rôle | Droits |
|---|---|
| Administrateur | tous les droits, dont le paramétrage de base : Référentiels (plan comptable, journaux, préfixes, types de tiers, moyens de paiement, modèles d'opération, natures et modes des fiches, réglages), Paramètres (Excel), codes d'axe 1, paramètres des relevés, utilisateurs, base de données |
| Trésorier | l'usage courant : saisie, tiers, consultation, banque, éditions, exports (ni paramétrage, ni imports, ni base de données) |
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
Un bénévole se connecte au site avec son propre identifiant (rôle Bénévole).

## Rapprochement bancaire (W3)

Par journal de trésorerie (B1, B2, B3, CA) :

- **Import du relevé** : PDF Mizrahi en hébreu, Excel ou CSV (modèle
  `Imports/modeles/10_releve_B1.csv`). Les lignes déjà importées sont
  ignorées (clé : date, référence, montant, rang dans la journée). Au premier
  import, un solde d'ouverture est déduit du premier solde du relevé.
  Les opérations sont traduites (Banque › Traductions du relevé).
- **Relevés à passer en compta** (menu Banque) : seulement les lignes
  téléchargées sans écriture (à partir de la date de reprise). Pour chacune :
  compte de contrepartie et code axe 2 (listes cherchables par code ou
  libellé), puis **Créer les écritures** : un Mvt banque / contrepartie par
  ligne, aussitôt relié à la ligne (`releves.creer_ecriture`).
- **Pas de doublon** : une ligne reliée sort de la liste et n'accepte plus
  d'écriture ; si une écriture de banque non reliée de même montant existe à
  ± tolérance (réglage `tolerance_rapprochement`), elle est proposée
  (« C'est la même » la relie sans rien créer) et la création demande de
  cocher « nouvelle écriture ».
- Plus de pointage automatique ou manuel ni d'état de rapprochement à l'écran.

## Tiers et suivi des membres (W5)

- **Fiches tiers** (menu Tiers) : une par compte de tiers de chaque type
  (membres 411, fournisseurs 401, autres types des Référentiels), créées
  automatiquement et à chaque nouveau tiers (Codes › Nouveau tiers) ;
  adresse, code postal, ville, téléphone, e-mail ; pour les membres : adhésion,
  statut (actif, honoraire, démissionnaire), cotisation attendue ; import du
  modèle `Imports/modeles/07_membres.csv`.
- **Fiche membre** : facturé, réglé, solde dû, historique.
- **Justificatifs** (page d'un mouvement) : scans PDF ou photos joints au mouvement (plusieurs par
  mouvement, 10 Mo au plus chacun, photo directe sur téléphone) ; consultables par tous les rôles qui voient
  la comptabilité, suppression par le trésorier seulement et jamais dans un exercice clos ; colonne 📎 et
  filtre « avec / sans justificatif » dans Écritures ; fichiers dans `<données>/Justificatifs/<année>/`,
  repris par l'export complet.
- **Corriger ou supprimer une écriture** (trésorier) : Saisie › Modifier une écriture (n° de Mvt), ou boutons Modifier /
  Supprimer de la fiche du mouvement ; l'avant et l'après restent dans l'historique. Refusé dans un exercice clos et
  pour les à-nouveaux. Une suppression dépointe les lignes, efface les justificatifs du mouvement et remet à reporter
  la ligne de fiche bénévole d'origine.
- **Justificatifs existants** (menu Saisie › Justificatifs, administrateur et trésorier) : dépôt en masse (ZIP ou
  fichiers), rattachement proposé d'après le nom du fichier (n° de Mvt en tête suivi d'une espace, « 389 facture.pdf » :
  seul cas coché d'office ; « Mvt 389 », « Pièce 739 », numéro seul,
  date + montant), vérification et correction dans un tableau, puis rattachement ; les documents non
  rattachés restent « à classer » ; la page d'un mouvement permet de les y rattacher (liste des documents déposés). En ligne de commande :
  `python manage.py importer_justificatifs <dossier|zip> [--rattacher]`.
  Un **extrait Excel** (un lien par ligne) déposé sur la même page fournit des **liens** (documents restés en ligne),
  proposés au mouvement de même date et même montant ; seuls les nouveaux liens sont repris. Un Excel fait à la main
  (colonne Mvt ou Pièce + lien) convient aussi ; un lien peut être collé sur la page du mouvement. Les documents des liens
  sont copiés sur le site (aussitôt, ou bouton « Les enregistrer sur le site », ou
  `python manage.py rapatrier_justificatifs`) .
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

## Documentation intégrée

**Éditions › Présentation (PDF)** et **Mode d'emploi (PDF)** servent les fichiers de `compta/documentation/`, livrés avec
le code. Sources : `docs/presentation.html` et `docs/mode-emploi.html`. Après un changement visible, régénérer captures
et PDF (poste de développement, Playwright et Chromium) : `python deploiement/documentation.py` (base de démonstration
fictive, captures dans `docs/images`, PDF dans `compta/documentation` et `docs/`).

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
