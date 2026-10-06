# Inventaire du classeur de référence

Classeur analysé : `Fusion.xlsm`, version transmise le 26/09/2026 (587 Ko).
Inventaire établi en lecture seule, avant le Lot 0 ; les changements du Lot 0 sont décrits dans `docs/livraison-lot0.md`.

## Onglets (22)

| Onglet | Rôle | Contenu notable |
|---|---|---|
| Accueil | Menu, période P_Debut / P_Fin (D5:D6), état des contrôles | 20 liens de menu |
| Compte rendu | Travaux, constats, actions | |
| CDC ComptaJLC | Cahier des charges v1.1 | transcrit dans `docs/cahier-des-charges.md` |
| Tableau de bord | Indicateurs et 4 graphiques | 55 formules |
| Synthèse | Résultat par axe, trésorerie, balance | |
| Contrôles | 13 contrôles + lignes signalées | État général « OK – 1 point à vérifier » |
| Consultation | Détail par Compte / Anal1 / Anal2 | liste dépendante `ANCHORARRAY` |
| Jnl Banque B1, B2, B3, Jnl Caisse | Journaux de trésorerie | |
| Banque1 | Rapprochement relevé / compta, écart par mois | 74 formules, 8 mises en forme conditionnelles |
| ImportBanque | T_Banque1 (Power Query « Requête1 ») | 156 lignes de relevé |
| Écritures à passer | T_AJout_Isracard : 10 lignes Isracard | « Oui – ne pas saisir » : déjà intégrées |
| Préfixes | T_Prefixes (13 préfixes, code suivant) | |
| Plan comptable | T_PlanComptable (82 comptes) | |
| Journaux | T_Journaux (9 journaux) | |
| Écritures | T_Ecritures (1 534 lignes) | 9 204 formules, 4 validations |
| Axe 2 - Anal2 | T_Axe2 (34 codes), liste 0/1/2 en F2:F4 | |
| Axe 1 - Anal1 | T_Axe1 (20 codes) | |
| Paramètres | CheminReleveB1 (B3), T_TradBanque (55 traductions) | |
| Feuil1 | vide | à supprimer |

## Tables structurées

| Table | Origine | Colonnes |
|---|---|---|
| T_Ecritures | **Power Query** ← `…\Applications\Compta\Exports\Ecritures-20260925-1927.csv` (tabulations, Windows-1252) | Date, Jnl, Mvt, Pièce, Compte, Intitulé*, Libellé, Débit, Crédit, Solde, Anal1*, Anal2, Let, Classe*, Contrôle, Libellé Axe1*, Libellé Axe2*, État Axe2* |
| T_PlanComptable | **Power Query** ← `Plan-comptable-20260926-0753.csv` | Compte, Libellé compte, Axe 1 (Anal1), Lettrable, Utilisé, Tva, Solde |
| T_Journaux | **Power Query** ← `Journaux-20260926-0752.csv` | Code, Intitulé, Type, Contrepartie, N° de compte, Compte bancaire, Actif |
| T_Axe1 | **Power Query** ← `Axe-1-—-Anal1-20260926-0752.csv` | Code, Libellé, Actif |
| T_Axe2 | **Power Query** ← `Axe-2-—-Anal2-20260926-0752.csv` | Code, Libellé, Actif |
| T_Prefixes | **Power Query** ← `Préfixes-des-codes-analytiques-20260926-0752.csv` | Préfixe, Axe, Libellé, Code suivant |
| T_Banque1 | **Power Query** « Requête1 » ← `D:\OneDrive\Compta Bnei Brith\tnuot.pdf` | Date, Référence, Opération (relevé), Opération (traduction), Montant, Solde relevé, Solde recalculé*, Contrôle solde*, En compta* |
| T_TradBanque | saisie | Opération (hébreu), Traduction |
| T_AJout_Isracard | saisie | 14 colonnes, dont « Présent en compta ? » |

\* colonne calculée dans Excel, à droite des colonnes chargées par la requête.

Le code M des sept requêtes est extrait dans `src/powerquery/`.

## Noms définis

`P_Debut`, `P_Fin` (Accueil D5:D6), `CheminReleveB1` (Paramètres B3),
`L_Anal1`, `L_Anal2`, `L_Compte`, `L_Comptes`, `L_Journaux`. Les listes L_*
sont redéfinies localement sur Jnl Banque B2, B3 et Jnl Caisse.

## Données au 26/09/2026

| | |
|---|---|
| Lignes d'écritures | 1 534 |
| Mouvements | 416 (Mvt 1 à 416), tous équilibrés |
| Pièces | 414 à 827 |
| Période | 25/10/2025 → 24/09/2026 |
| Σ débit = Σ crédit | 1 444 703,68 ₪ |
| Résultat (classes 7 − 6) | −47 366,41 ₪ |
| Lignes par journal | B3 664 · B1 442 · CA 400 · OD 24 · OD1 4 |
| Lignes débit ET crédit | 0 |
| Lettrage (Let) | vide partout |
| Erreurs de formule | aucune |
| Contrôles | tout OK, sauf « solde du plan ≠ solde des écritures » : 2 comptes |

Les deux comptes en écart sont 512000 (−6 336,98) et 600000 (+6 336,98) :
exactement les cinq paiements Isracard ajoutés dans le classeur. La colonne
Solde de T_PlanComptable vient de l'export de l'ancien logiciel, antérieur à
cet ajout. Le contrôle ne signale donc pas d'erreur. Il deviendra sans objet
quand le plan ne sera plus rechargé depuis l'ancien logiciel.

### Autres observations

- **Pas de journal AN.** Les soldes d'ouverture sont passés au 01/01/2026
  dans les journaux B1 (259 683,86, Mvt 390) et CA (2 207,48, Mvt 393)
  contre 110000. Les 52 lignes antérieures au 01/01/2026 (B3 : 36, CA : 12,
  OD1 : 4) portent sur BIT (+6 800 encaissés), la caisse et 471000. BIT
  n'a pas de solde d'ouverture, ce qui peut expliquer son solde négatif
  (§6 du cahier).
- **Comptes membres alphanumériques** : `411` + 5 lettres du nom + rang
  (`411TAIEB001`), 42 comptes plus 411000. Le « prochain compte 411 » du
  Lot 1 suit ce schéma, pas une numérotation continue.
- **Comptes d'attente existants** : 470000 « CPTES D'ATTENTE » et 471000
  « REGLEMENT ? FACTURE FOURNISSEUR » ; 580000 « VIREMENT ».
- Colonnes Lettrable / Utilisé du plan : `oui` ou vide ; Tva : toujours vide.

La numérotation suit l'ordre de l'export, pas celui des dates : le Mvt 1
est daté du 24/09/2026 et le Mvt 411 du 25/10/2025. Les Mvt 412 à 416 sont
les lignes Isracard (lignes 1526 à 1535, fond orangé, commentaire).
`MAX(Mvt)+1` reste valable.

## Constats qui pèsent sur le plan

### 1. Le grand livre est rechargé depuis l'ancien logiciel — bloquant

T_Ecritures et les cinq tables de référence sont des **résultats de
requêtes Power Query** qui relisent les exports CSV de l'ancien logiciel.
Les dix lignes Isracard (Mvt 412 à 416) et tout changement de statut fait
dans T_Axe2 n'existent **que dans le classeur**. Un « Actualiser tout »
(que l'Accueil recommande pour le relevé Banque 1) aurait deux effets
possibles :

- l'export est toujours là : les tables reviennent à l'état de l'export et
  **les lignes Isracard disparaissent** ;
- le chemin n'existe pas (autre poste, dossier déplacé) : erreur
  d'actualisation.

Tant que ces tables restent des requêtes, ni la saisie du Lot 1 ni aucun
ajout manuel n'est durable. **Les dissocier de leur requête est le
préalable du Lot 1.**

### 2. Chemins absolus

Les sept requêtes codent en dur `D:\OneDrive\...`. `Requête1` ignore même
le nom `CheminReleveB1` qui existe dans Paramètres. Les chemins doivent
devenir relatifs au dossier du classeur (§6 et §12 du cahier).

### 3. Classeur .xlsm sans macro

Le projet VBA ne contient aucun code (modules vides). Avec la réponse Q5
« 100 % formules », un enregistrement en `.xlsx` retirerait l'alerte de
sécurité des macros. À décider, sans urgence.

### 4. Codes Anal2 sans libellé

16 des 34 codes de T_Axe2 ont un libellé vide, tous au statut 0 : MAN.008 à
MAN.012, PJT.002 à PJT.006 et SOC.005 à SOC.010. Trois d'entre eux sont
**utilisés** dans des écritures : SOC.005 (4 lignes), SOC.006 (24) et
SOC.007 (8). Au Lot 0, les 13 autres ont été supprimés ; les trois
utilisés attendent leur libellé.

### 4 bis. Compte de virement interne

580000 porte un solde débiteur de 149 655,84 : 101 033,34 venus de B1,
38 122,50 de B3 et 10 500 de CA. Les virements internes ne sont passés que
d'un côté, et B2 (épargne) n'a aucune écriture. À rapprocher au Lot 3.

### 5. Modification du classeur hors d'Excel

Le classeur contient Power Query (partie `customXml`), des commentaires à
thread, des validations de données étendues, 4 graphiques et un
complément Office. Les bibliothèques Python courantes (openpyxl) perdent
une partie de ces éléments à l'enregistrement : **aucune modification ne
doit passer par elles**. Le classeur se modifie dans Excel, ou par édition
directe et contrôlée du XML interne.
