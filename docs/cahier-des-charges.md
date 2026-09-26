# Cahier des charges – application « ComptaBB »

Version 1.1 – 26/09/2026 – cahier des charges final pour Claude Code.
Transcription de la feuille « CDC ComptaBB » du classeur `Fusion.xlsm`.
En cas de divergence, la feuille Excel fait foi.

## 0. Consigne pour Claude

| | |
|---|---|
| Mission | Concevoir et construire, dans ce classeur Excel, l'application ComptaBB permettant de poursuivre la comptabilité de l'association (Loge Bnei Brith) à partir des données et onglets existants décrits ci-dessous. |
| Méthode | 1) Lire ce cahier et inventorier le classeur ; 2) présenter un plan par lots et attendre validation ; 3) construire lot par lot en vérifiant chaque étape (formules sans erreur, totaux égaux avant/après) ; 4) mettre à jour les onglets Accueil (menu) et Compte rendu. |
| Interdits | Ne jamais modifier ni supprimer une écriture existante sans accord ; ne pas coder de valeurs métier en dur dans les formules ; ne pas casser les tables T_* ni la requête Power Query du relevé Banque 1. |

## 1. Contexte et objectifs

| | |
|---|---|
| Contexte | Association en Israël, comptes en shekels (₪). Comptabilité jusqu'ici tenue dans un logiciel externe puis exportée (écritures du 25/10/2025 au 24/09/2026, environ 416 mouvements, 1 534 lignes). Le classeur a été nettoyé, fiabilisé et enrichi (synthèse, contrôles, tableau de bord, rapprochement Banque 1). |
| Objectif | Tenir désormais la comptabilité directement dans Excel : saisie simple par des bénévoles non comptables, suivi des membres, rapprochement de toutes les banques et de la caisse, états annuels et clôture. |
| Utilisateurs | Trésorier (saisie, rapprochement), Président / bureau (consultation, tableau de bord), vérificateur aux comptes (contrôles, états). |
| Environnement | Excel Microsoft 365 pour ordinateur (Windows), fichier sur OneDrive (`D:\OneDrive\Compta Bnei Brith`). Interface en français ; relevés bancaires en hébreu (PDF Mizrahi Tefahot). |

## 2. Périmètre

| | |
|---|---|
| Inclus | Lot 1 saisie guidée ; Lot 2 suivi des membres ; Lot 3 rapprochement bancaire ; Lot 4 clôture et états annuels ; maintien du tableau de bord et des contrôles existants. |
| Exclus | Paie, TVA, facturation électronique, envoi automatique d'e-mails, multi-devises (hors frais de change constatés en ₪), accès simultané multi-utilisateurs. |

## 3. Données existantes (à réutiliser)

| | |
|---|---|
| T_Ecritures (onglet Écritures) | Date, Jnl, Mvt (n° de mouvement unique), Pièce, Compte, Intitulé (calculé), Libellé, Débit, Crédit, Solde (inutilisé), Anal1 (calculé depuis le plan), Anal2 (événement/projet), Let (lettrage, vide), Classe (calculée), Contrôle (calculé). Dans toutes les tables, listes et vues qui affichent un code Anal1 ou Anal2, ajouter une colonne calculée « Libellé Axe1 » ou « Libellé Axe2 » alimentée respectivement depuis T_Axe1 ou T_Axe2. Si le code est vide, laisser le libellé vide ; si le code n'existe pas dans le référentiel, afficher « Code introuvable ». |
| T_PlanComptable | 83 comptes : classe 1 (110000 report à nouveau, 1541xx provisions), 2 (213000 dépôt de garantie), 4 (401 fournisseurs, 411xxx = 43 comptes membres, 420–490), 5 (512000 Mizrahi CC, 512100 Mizrahi épargne, 512200 BIT, 530000 caisse, 580000 virements internes), 6 (600000–695000), 7 (700000 cotisations, 710000 manifestations, 720000 opérations, 725000 dons reçus, 740000 subventions, 750000 intérêts). Chaque compte porte son code Anal1. |
| T_Journaux | AN à-nouveaux, B1 Mizrahi CC, B2 Mizrahi épargne, B3 BIT, CA caisse, HA achats, OD / OD1 opérations diverses, VT ventes. |
| T_Axe1 / T_Axe2 / T_Prefixes | Axe 1 = nature (ACT, BIL, COT, DON, FRA, PRO, PRV, SUB) ; Axe 2 = événement/projet (GEN, MAN, PJT, REG, SOC) ; T_Prefixes donne le « code suivant » pour créer un nouveau code. Dans T_Axe2, la colonne Actif est obligatoire et contrôlée par une liste déroulante : 0 = Non affecté, 1 = En cours, 2 = Terminé ; la liste source est maintenue dans l'onglet Axe 2 - Anal2 (F2:F4). |
| T_Banque1 (onglet ImportBanque) | Relevé Banque 1 chargé par Power Query (requête « Requête1 », PDF tnuot.pdf) + colonnes calculées Solde recalculé, Contrôle solde, En compta. Traductions hébreu → français dans T_TradBanque (onglet Paramètres). |
| Onglets de restitution | Accueil (période P_Debut / P_Fin, menu), Tableau de bord, Synthèse, Contrôles, Consultation, Jnl Banque B1/B2/B3, Jnl Caisse, Banque1 (rapprochement), Compte rendu. |
| Conventions actuelles | Une opération = un Mvt équilibré ; opération type à 4 lignes : facture (6xx/7xx contre 411) puis règlement (411 contre 512/530). Remboursements = recettes au débit ou dépenses au crédit (admis). |

## 4. Lot 1 – Saisie guidée des opérations

| | |
|---|---|
| Écran de saisie | Onglet « Saisie » : date, type d'opération (liste), tiers / membre (liste), montant, moyen de paiement (journal B1, B2, B3, CA), Anal2 (liste), libellé, n° de pièce proposé. Aperçu des lignes débit/crédit générées avant validation. Dans Écritures et dans l'écran de saisie, le code Anal2 doit être modifiable manuellement par liste déroulante contenant tous les codes de T_Axe2, quel que soit leur statut. |
| Modèles d'opérations | Table T_ModelesOperation (paramétrable) : type, compte débit, compte crédit, journal par défaut, besoin d'un tiers (O/N), libellé type. Types minimum : Cotisation membre (411 / 700000 puis règlement), Facture manifestation membre (411 / 710000), Règlement membre (512/530 / 411), Don reçu (512/530 / 725000), Subvention (512 / 740000), Dépense directe (6xx / 512/530), Facture fournisseur (6xx / 401), Règlement fournisseur (401 / 512), Frais bancaires et cartes (600100 ou 600000 / 512), Intérêts (512 / 750000), Virement interne (512x / 580000 puis 580000 / 512y), Remboursement (écriture inverse). |
| Numérotation | Mvt = MAX(T_Ecritures[Mvt]) + 1 ; Pièce = MAX(Pièce) + 1 ; jamais de doublon. |
| Validation | Contrôles bloquants avant ajout : équilibre, compte / journal / Anal2 existants, montant > 0, date dans l'exercice ouvert. Ajout en bas de T_Ecritures (bouton : Office Script ou VBA au choix, à justifier ; alternative sans macro : zone de lignes générées à copier-coller en valeurs). |
| Création de codes | Nouveau membre (compte 411 + fiche membre) et nouvel Anal2 à partir de T_Prefixes (code suivant). Lors de la création ou de la modification d'un code Anal2, renseigner le statut Actif via cette liste (0/1/2), sans valeur libre. Le système doit proposer automatiquement le prochain numéro d'ordre disponible lors de la création d'un code Axe1 ou Axe2 : préfixe sélectionné + numéro séquentiel maximal existant augmenté de 1, formaté sur trois chiffres (ex. MAN.013), avec contrôle anti-doublon avant validation. L'interface doit aussi permettre de modifier le statut du code Anal2 sélectionné par liste déroulante (0 = Non affecté, 1 = En cours, 2 = Terminé) ; la validation met à jour la ligne unique correspondante dans T_Axe2, répercute immédiatement le statut dans toutes les vues et journalise l'auteur, la date, l'ancien et le nouveau statut. Une confirmation est requise avant modification d'un code déjà utilisé dans T_Ecritures. |

## 5. Lot 2 – Suivi des membres

| | |
|---|---|
| Données | Table T_Membres : compte 411, nom, prénom, téléphone, e-mail, date d'adhésion, statut (actif, honoraire, démissionnaire), cotisation annuelle attendue. |
| Fiche membre | Choix d'un membre : facturé, réglé, solde dû, historique des écritures (spill), ancienneté des impayés (0–30, 31–90, > 90 jours). |
| États | Liste des impayés triée par montant ; cotisations de l'année attendues / reçues / taux de recouvrement ; texte de relance généré (à copier dans un e-mail). |
| Lettrage | Utiliser la colonne Let de T_Ecritures pour lettrer facture et règlement d'un même membre (code lettre commun) ; solde lettré = 0. |

## 6. Lot 3 – Rapprochement bancaire

| | |
|---|---|
| Import | Généraliser la requête Power Query à B2, B3 et à la caisse (un fichier par banque, chemin dans Paramètres) ; même structure de sortie que T_Banque1. Claude Code doit définir et créer le dossier `Applications/comptaBB/Imports`, destiné à l'initialisation d'une nouvelle comptabilité ou à la reprise de la ComptaBB existante. Ce dossier doit contenir : (1) les modèles d'import documentés pour le plan comptable, les journaux, Axe1, Axe2, les membres/tiers, les écritures, les paramètres et les relevés bancaires ; (2) les exports complets des données existantes dans ces mêmes formats ; (3) un README précisant noms de fichiers, colonnes obligatoires, types, formats de dates et de montants, ordre d'import, règles de mapping, contrôles, gestion des doublons et procédure de reprise/annulation. Les chemins doivent être relatifs au dossier `Applications/comptaBB` et paramétrables, sans chemin utilisateur codé en dur. |
| Pointage | Correspondance automatique montant + date (± tolérance paramétrable), puis manuelle ; gestion des regroupements (une remise de chèques = plusieurs règlements ; frais mensuels regroupés) ; identifiant de rapprochement stocké côté relevé et côté écriture. |
| État de rapprochement | À une date donnée : solde relevé, solde comptable, écritures non pointées, lignes du relevé non pointées, écart expliqué = 0. Écart par mois (déjà dans Banque1). |
| Création d'écritures | Depuis une ligne du relevé non pointée (frais, carte, intérêts) : proposer l'écriture via les modèles du Lot 1, à valider. |
| Existant | Écart Banque 1 résiduel de 2 910,00 au 24/09/2026 à analyser (Mvt 285 : −2 000 ; Mvt 177 : −1 500) ; solde BIT (B3) négatif à expliquer. |

## 7. Lot 4 – Clôture et états annuels

| | |
|---|---|
| Exercice | Paramètre date de début / fin d'exercice (à confirmer : 01/01–31/12 ?). Verrouillage des périodes clôturées (saisie refusée). |
| États | Compte de résultat par nature (classes 6 / 7) et par Anal1 / Anal2 ; bilan simplifié (classes 1 à 5) ; balance générale ; grand livre ; comparaison N / N-1. |
| Budget | Table T_Budget par compte ou Anal1 / Anal2 ; budget vs réalisé et écarts en % sur la période. |
| Clôture | Génération des à-nouveaux (journal AN) : soldes des classes 1 à 5 reportés, résultat affecté en 110000 (ou 12x à créer) ; contrôle bilan équilibré avant / après ; archivage de l'exercice (copie figée en valeurs). |

## 8. Règles et contrôles transverses

| | |
|---|---|
| RG-01 | Chaque Mvt est équilibré (Σ débit = Σ crédit). |
| RG-02 | Compte, journal, Anal1, Anal2 obligatoirement présents dans les tables de référence. |
| RG-03 | Une ligne a soit un débit soit un crédit, jamais les deux. |
| RG-04 | Aucune saisie dans une période clôturée. |
| RG-05 | Les écritures ajoutées hors logiciel ou par correction sont repérées (couleur + commentaire : date, origine, motif) comme les écritures Isracard des lignes 1526–1535. |
| RG-06 | Tout montant affiché est calculé par formule traçable ; hypothèses dans des cellules nommées. |
| RG-07 | L'onglet Contrôles reste la référence : état général « OK » requis avant clôture et avant diffusion des états. |

## 9. Exigences non fonctionnelles

| | |
|---|---|
| Ergonomie | Menu Accueil, liens de retour sur chaque onglet, cellules à saisir en jaune / texte bleu, messages d'erreur en français, formats ₪ #,##0.00, dates jj/mm/aaaa. |
| Robustesse | Tables structurées (références qui s'étendent), pas de plages fixes ; fonctionnement jusqu'à 20 000 lignes d'écritures ; recalcul < 5 s. |
| Sécurité / traçabilité | Protection des onglets de référence et des formules (sans mot de passe par défaut) ; onglet Journal des modifications (date, auteur, action) ; sauvegarde datée avant chaque clôture. |
| Documentation | Mode d'emploi dans le Compte rendu (section Utilisation) et info-bulles sur les cellules de saisie. |

## 10. Points ouverts à trancher avec le trésorier

Réponses portées dans la feuille au 26/09/2026.

| | Question | Réponse |
|---|---|---|
| Q1 | Dates de l'exercice comptable | 01/01/2026 ; date de la première clôture : 31/12/2025 |
| Q2 | Compte de charge définitif des paiements carte Isracard (600000 provisoire) | Un compte de virement interne : 580000 |
| Q3 | Traitement de l'écart Banque 1 de 2 910,00 (Mvt 285 et 177) et du virement de 20 917 daté différemment | Doit être mis en attente d'éclaircissements |
| Q4 | Libellés réels des codes Anal2 (MANIFESTATION1, GEN.2, …) | — |
| Q5 | Macros autorisées (VBA / Office Scripts) ou solution 100 % formules | 100 % formules |
| Q6 | Saisie par une ou plusieurs personnes ; besoin d'un mode consultation seule | Oui, ou bien envoi des données comptables dans un fichier à modifier et à valider |

## 11. Livrables et critères d'acceptation

| | |
|---|---|
| Phasage | Lot 1 → Lot 2 → Lot 3 → Lot 4, chaque lot validé avant le suivant. |
| Acceptation | Aucune erreur de formule ; Contrôles = OK ; totaux débit / crédit et résultat identiques avant et après chaque lot (hors écritures nouvelles) ; test de saisie de chaque type d'opération ; rapprochement Banque 1 reproduit à l'identique ; Accueil et Compte rendu à jour. |

## 12. Remise à Claude Code et gestion du projet Git

| | |
|---|---|
| Dossier projet | Créer le projet dans `Applications/comptaBB`. Le classeur de référence, le présent cahier des charges et le dossier Imports doivent être accessibles depuis cette racine. Utiliser exclusivement des chemins relatifs et paramétrables. |
| Contexte Claude Code | Créer à la racine un fichier CLAUDE.md concis décrivant le contexte métier, l'architecture, les commandes de test, les conventions, les interdits du présent cahier et les critères d'acceptation. Le versionner avec le projet. |
| Structure minimale | README.md ; CLAUDE.md ; .gitignore ; docs/ ; Imports/modeles/ ; Imports/reprise/ ; Imports/README.md ; src/ ; tests/. Ne jamais versionner de secrets, jetons, mots de passe, fichiers temporaires Excel ni données personnelles non nécessaires. |
| Gestion Git | Initialiser un dépôt Git dans `Applications/comptaBB`, branche principale main. Réaliser chaque lot sur une branche dédiée (lot-1-saisie, lot-2-membres, lot-3-rapprochement, lot-4-cloture), avec commits courts et explicites, puis revue et fusion après validation. |
| Dépôt distant | Créer un dépôt privé GitHub nommé comptaBB, rattacher origin et pousser main. Protéger main : changements par pull request, revue avant fusion et contrôles automatiques obligatoires lorsque disponibles. |
| Sauvegarde des données | Le code, les modèles d'import anonymisés et la documentation sont versionnés. Les exports réels du dossier Imports/reprise ne sont versionnés que dans un dépôt privé autorisé ; sinon les exclure via .gitignore et conserver une sauvegarde chiffrée séparée. |
| Livraison par lot | Avant chaque fusion : sauvegarde du classeur, Contrôles = OK, tests documentés, comparaison des totaux avant/après, mise à jour du README, du CLAUDE.md si nécessaire, du Compte rendu et du journal des modifications. |
| Acceptation finale | Le dépôt doit permettre à un poste neuf de reconstruire ou reprendre ComptaBB en suivant uniquement README.md et Imports/README.md, sans chemin absolu ni donnée manquante. Une version Git étiquetée v1.0.0 est créée après recette finale. |

## 13. Procédure pratique de démarrage

| | |
|---|---|
| Prérequis | Installer Git for Windows et GitHub CLI, disposer d'un compte Claude Code compatible et d'un compte GitHub autorisé à créer un dépôt privé. |
| Installer Claude Code | Dans PowerShell : `winget install Anthropic.ClaudeCode`, `claude --version`, `claude doctor` |
| Ouvrir le projet | Dans PowerShell : `cd "D:\OneDrive\Applications\comptaBB"` puis `claude` |
| Initialiser Claude | Dans la session Claude Code, lancer /init afin de créer ou améliorer CLAUDE.md. Vérifier avec /context que CLAUDE.md est bien chargé. |
| Consigne initiale | Lis CLAUDE.md, le classeur de référence et le cahier des charges. Inventorie le projet et les données. Présente un plan détaillé par lots sans modifier les écritures existantes, puis attends ma validation avant de commencer le lot 1. Pour chaque lot, crée une branche Git, teste les contrôles et les totaux, documente les changements et prépare une pull request. |
| Initialiser Git localement | Depuis `Applications/comptaBB` : `git init -b main`, `git add .`, `git commit -m "Initialisation du projet ComptaBB"` |
| Créer le dépôt GitHub | `gh repo create comptaBB --private --source=. --remote=origin --push`. Ne pas préinitialiser séparément le dépôt distant avec README, licence ou .gitignore si ces fichiers existent déjà localement. |
| Travailler par lot | `git switch -c lot-1-saisie` ; réaliser et tester le lot ; `git add .` ; `git commit -m "Lot 1 : saisie guidée"` ; `git push -u origin lot-1-saisie` ; créer ensuite une pull request vers main et ne fusionner qu'après validation. |
| Protéger main | Dans GitHub, activer une règle de protection de la branche main : pull request obligatoire, revue avant fusion et contrôles automatiques requis lorsque disponibles. |
| Données sensibles | Conserver le dépôt privé. Ne jamais committer les secrets, jetons, fichiers temporaires Excel ni données personnelles non nécessaires. Si les exports réels de reprise ne sont pas autorisés dans Git, ajouter Imports/reprise/ au .gitignore et les sauvegarder séparément de manière chiffrée. |
| Clôturer une version | `git switch main` ; `git pull` ; `git tag -a v1.0.0 -m "Version initiale validée de ComptaBB"` ; `git push origin v1.0.0` |
| Références | Claude Code – installation : code.claude.com/docs/en/setup · CLAUDE.md et /init : code.claude.com/docs/en/memory · GitHub – création d'un dépôt : docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository |
