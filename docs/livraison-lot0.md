# Livraison du Lot 0 — préparation du classeur (26/09/2026)

Classeur livré : `ComptaBB.xlsm`, produit à partir de `Fusion.xlsm` par
`python src/lot0_preparation.py Fusion.xlsm ComptaBB.xlsm`. Le script
réédite le XML du classeur pièce par pièce, sans bibliothèque qui le
réécrive. Il peut être relancé à l'identique sur le classeur d'origine.

## Ce qui a changé

| # | Changement | Détail |
|---|---|---|
| 1 | **Fin de l'ancien logiciel** | T_Ecritures, T_PlanComptable, T_Journaux, T_Axe1, T_Axe2 et T_Prefixes sont dissociées de leurs requêtes. Les 6 requêtes et leurs connexions sont supprimées. Seule reste `Requête1` (relevé Banque 1). |
| 2 | **Chemin relatif** | `Requête1` lit `CheminReleveB1` (Paramètres!B3), calculé ainsi : dossier de l'application + `Releves\tnuot.pdf`. |
| 3 | **Paramètres nommés** | Paramètres!D3:F16 : `P_DebutExercice` 01/01/2026, `P_FinExercice` 31/12/2026, `P_DateCloture` 31/12/2025, `P_DernierMvtClos` 421, `P_CompteVirement` 580000, `P_CompteAttente` 470000, `P_Dossier`, `P_ReleveB1`. |
| 4 | **Isracard (décision Q2)** | Mvt 412 à 416 (B1) : la ligne 600000 devient 580000, soit 580000 contre 512000. Nouveaux Mvt 417 à 421 (OD, pièces 828 à 832) : 600000 contre 580000, mêmes dates, montants et codes Anal2. Lignes en orangé et commentées (RG-05). |
| 5 | **Codes Anal2** | 13 codes sans libellé et jamais utilisés sont supprimés. SOC.005, SOC.006 et SOC.007 sont conservés (36 lignes d'écritures). SOC.005 reçoit son libellé « ENFANTS MALADES » ; ceux de SOC.006 et SOC.007 restent à saisir. |
| 6 | **Calculs** | T_PlanComptable[Solde] = solde des écritures. T_Prefixes[Code suivant] = préfixe + (plus grand numéro existant + 1), sur 1 chiffre pour l'axe 1 (`ACT.4`) et 3 chiffres pour l'axe 2 (`MAN.008`). |
| 7 | **Contrôles** | La ligne 18 devient RG-04 (écritures nouvelles dans la période close) ; l'ancien contrôle « solde du plan ≠ écritures » est sans objet. M20:P23 suit les comptes de liaison 580000 et 470000. |
| 8 | **Traçabilité** | Nouvel onglet **Journal des modifications** (table T_Journal, 39 lignes), lien depuis l'Accueil. Compte rendu : section 6 et actions à jour. |
| 9 | **Recalcul** | Excel recalcule tout le classeur à l'ouverture. |

## Vérifications faites

| Vérification | Résultat |
|---|---|
| Structure du paquet (XML, relations, types, en-têtes de tables) | OK |
| `src/controles.py` (RG-01 à RG-04, pièces, erreurs) | OK |
| Totaux Mvt 1 à 416 (débit, crédit, lignes) | identiques ; le résultat de ces Mvt baisse de 6 336,98, montant de la charge déplacée vers les Mvt 417 à 421 |
| Écritures nouvelles | 10 lignes, 6 336,98 au débit et au crédit, effet sur le résultat : 0 |
| Résultat total, soldes par classe | inchangés (−47 366,41) |
| Recalcul LibreOffice avant / après | Banque1, ImportBanque, journaux B1/B2/B3/Caisse **identiques** ; nouvelles lignes et soldes du plan justes |

LibreOffice ne connaît pas certaines fonctions d'Excel 365 (LET,
ANCHORARRAY) : il sert ici de comparaison, pas de recette. **La recette se
fait dans Excel.**

## À faire à la première ouverture dans Excel

1. Enregistrer le fichier sous `D:\OneDrive\Applications\ComptaBB\ComptaBB.xlsm`.
2. Déplacer le relevé : `D:\OneDrive\Compta Bnei Brith\tnuot.pdf` →
   `D:\OneDrive\Applications\ComptaBB\Releves\tnuot.pdf`.
3. Ouvrir, activer les données externes si Excel le demande, laisser le
   recalcul se terminer.
4. **Paramètres, E13 à E15** : E15 doit afficher
   `D:\OneDrive\Applications\ComptaBB`. Si E13 commence par `https://`,
   c'est normal : E14 (racine OneDrive) sert alors de base.
5. **Données › Actualiser tout.** Si Excel affiche une erreur
   « Formula.Firewall », ouvrir Données › Obtenir des données › Options de
   requête › Classeur actif › Confidentialité, puis cocher « Ignorer les
   niveaux de confidentialité ». Actualiser à nouveau.
6. **Contrôles** : l'état général doit être « OK – 0 point(s) à
   vérifier ».
7. Si Excel annonce qu'il a « trouvé un problème dans le contenu » :
   **ne pas enregistrer**, noter le message et me le transmettre.
8. Enregistrer.

## Points ouverts

- Libellés de SOC.006 et SOC.007 (SOC.005 = ENFANTS MALADES, reçu le 26/09/2026).
- **580000 : solde débiteur de 149 655,84.** Les virements internes ne sont
  passés que d'un côté : 101 033,34 venus de B1, 38 122,50 de B3 et 10 500 de CA,
  alors que B2 (épargne) n'a aucune écriture. À traiter au Lot 3 avec le
  relevé B2.
- **Mise en attente sur 470000 (décision Q3)** : aucune écriture passée pour
  l'instant. L'écart Banque 1 de 2 910,00 ne se réduit pas aux Mvt 285
  (2 000) et 177 (1 500), qui totalisent 3 500 : il reste 590 à
  expliquer. Les écritures d'attente seront proposées au Lot 3, une fois
  l'écart détaillé ligne à ligne.
- Ouverture 2026 : le solde d'ouverture de B1 (259 683,86) est confirmé par
  le relevé (Compte rendu, ligne 31). Restent CA, qui a 12 lignes en 2025 et
  un solde d'ouverture de 2 207,48, et B3, qui a 36 lignes en 2025 et aucun
  solde d'ouverture : à trancher pour la clôture 2025 (Lot 4).
