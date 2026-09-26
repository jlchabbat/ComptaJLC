# Livraison du Lot 1 (1re partie) — saisie guidée, codes, statuts (26/09/2026)

Classeur livré : `ComptaBB.xlsm`, produit par
`python src/lot0_preparation.py Fusion.xlsm lot0.xlsm` puis
`python src/lot1_saisie.py lot0.xlsm ComptaBB.xlsm`. 100 % formules : rien
n'est écrit dans les écritures tant que le trésorier ne colle pas.

## Trois onglets nouveaux

| Onglet | Rôle |
|---|---|
| **Saisie** (après Accueil) | 10 cases jaunes : date, type d'opération, tiers, montant, moyen de paiement, « vers » pour un virement, événement (Anal2), compte si différent, remboursement, libellé. 11 contrôles bloquants, aperçu des écritures, puis les **lignes à reporter**, en vert quand tout est OK. |
| **Codes** | A. Nouveau code analytique : on choisit le préfixe, le code est proposé, on saisit le libellé. B. Nouveau membre : le compte `411` + 5 lettres du nom + rang est proposé. C. Statut d'un code Anal2, avec confirmation s'il est utilisé. Chaque bloc prépare sa ligne pour la table concernée et pour le Journal des modifications. |
| **Modèles** (après Paramètres) | T_ModelesOperation (14 types), T_Schemas (lignes générées), T_Paiements (banques et caisse), T_TypesTiers (411 membre, 401 fournisseur). Un nouveau type = une ligne, sans formule à retoucher. |

## Types d'opérations et écritures générées

Les schémas reprennent les conventions des 421 mouvements existants.

| Type | Écritures |
|---|---|
| Cotisation, facture manifestation, recette d'opération, don d'un membre | 411 D / 7xx C, puis, si réglé, trésorerie D / 411 C — un seul Mvt de 4 lignes dans le journal du paiement ; non réglé : 2 lignes en VT |
| Règlement d'un membre | trésorerie D / 411 C |
| Don sans tiers, subvention, intérêts | trésorerie D / 7xx C |
| Dépense directe, frais bancaires | 6xx D / trésorerie C |
| Facture fournisseur | 6xx D / 401 C, puis, si réglé, 401 D / trésorerie C ; non réglé : 2 lignes en HA |
| Règlement fournisseur | 401 D / trésorerie C |
| Virement interne | Mvt 1 : 580000 D / banque source C ; Mvt 2 : banque qui reçoit D / 580000 C |
| Paiement carte Isracard | Mvt 1 (OD) : 6xx D / 580000 C ; Mvt 2 : 580000 D / banque C |
| Remboursement = Oui | toutes les lignes inversées, libellé « REMBOURSEMENT … » |

Numérotation : Mvt = MAX(Mvt) + 1 et Pièce = MAX(Pièce) + 1 ; +1 encore pour le
second Mvt d'un virement ou d'un paiement Isracard.

## Contrôles bloquants

Date dans l'exercice ouvert et après la période close · type connu · montant
positif · tiers présent et du bon type (membre ou fournisseur) · moyen de
paiement quand il est obligatoire · virement vers un autre compte · code Anal2
connu · compte connu et de la bonne classe · comptes et journaux générés
connus · équilibre · opération déjà présente dans Écritures (même date,
libellé et montant).

## Vérifications faites

- Structure du paquet : OK ; `src/controles.py` : OK, totaux inchangés
  (rien n'est ajouté aux écritures).
- **15 scénarios recalculés par LibreOffice** (`tests/recette_lot1.py`),
  tous conformes :
  - cotisation réglée ou non, frais bancaires, virement interne,
    paiement Isracard, remboursement, facture fournisseur en caisse ;
  - erreurs attendues : compte manquant, date close, mauvais tiers,
    compte de mauvaise classe, paiement manquant, virement vers le même
    compte, opération déjà reportée ;
  - nouveau membre `Taïeb Paul` → `411TAIEB002` ; changement de statut
    refusé sans confirmation, accepté avec.
- LibreOffice ne connaît pas FILTER, SORT ni LET. La liste déroulante des
  tiers et le code proposé du bloc A se vérifient donc **dans Excel**.

## Recette dans Excel

1. Onglet **Saisie** : saisir une vraie opération, par exemple une
   cotisation réglée. Vérifier les contrôles et l'aperçu.
2. Suivre l'instruction de la partie 4 : copier les lignes vertes, puis
   Écritures, première ligne vide, Collage spécial › Valeurs avec
   **« Blancs non compris »**.
3. **Point à vérifier** : les colonnes Intitulé et Anal1 des nouvelles
   lignes doivent se remplir seules, parce que la table s'agrandit avec ses
   formules. Sinon, les recopier depuis la ligne du dessus (Ctrl+D) et me
   le signaler : j'adapterai la méthode de report.
4. Onglet Contrôles : « OK ». Dans Saisie, le contrôle « Déjà reportée ? »
   passe en Erreur : c'est voulu, cela évite de coller deux fois.
5. Onglet **Codes** : vérifier que la liste des tiers de Saisie et le code
   proposé (bloc A) s'affichent.

## Reste du Lot 1 (2e partie)

- Classeur de saisie externe `ComptaBB_Saisie.xlsx` et zone
  « Transmission » du classeur maître (accès à distance, Q6).
- Colonnes « Libellé Axe1 / Axe2 » dans les vues qui n'en ont pas encore.
- Protection des onglets de référence et des formules (sans mot de passe).
