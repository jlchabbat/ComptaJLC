# Fichier de liaison pour un bénévole à distance

`ComptaJLC_Liaison.xlsx`, produit par
`python src/classeur_liaison.py ComptaJLC.xlsm ComptaJLC_Liaison.xlsx`.

Le bénévole ne fait pas de comptabilité : il remplit des listes, et le
fichier génère les écritures selon les conventions du classeur maître. Le
fichier ne contient pas le grand livre.

## Onglets

| Onglet | Qui | Contenu |
|---|---|---|
| Accueil | tous | Mode d'emploi. |
| **Activité** | trésorier puis bénévole | Le trésorier choisit d'avance le code Axe2 de l'activité (C3). Le bénévole note les **recettes** et les **dépenses** de l'activité. Recettes : date, membre ou autre payeur, nombre de personnes, nature (participation par défaut, don, sponsor, autre), montant, mode (espèces, chèque, virement, Bit, non payé). Dépenses : date, bénéficiaire, nature, montant, payé par (espèces, chèque, virement, Bit, carte Isracard, avance d'un membre), justificatif. En haut : nombre de participants, recettes, dépenses, résultat. |
| **Gestion** | bénévole puis trésorier | Dons ou aides **reçus** ou **versés**. Le bénévole note la date, qui, la nature, le montant et une remarque. Le trésorier complète ensuite le **mode de paiement** (virement Mizrahi, virement BIT, espèces), le **compte de contrepartie** (un compte suggéré s'affiche selon la nature) et le **code Axe2**. |
| **Tiers** | bénévole, trésorier | Membres existants (recherche par filtre, ou en tapant le début du nom dans les listes). Un **nouveau tiers** s'ajoute sur une ligne vide, sans compte : il est **provisoire**. Le trésorier crée le compte dans ComptaJLC (Codes › Nouveau membre) puis l'inscrit ici. |
| **Export** | trésorier | Statut, puis les lignes d'écritures dans les colonnes de T_Ecritures, à coller dans l'onglet **Transmission** du maître. |
| Listes | trésorier | Correspondances modifiables : modes de paiement → journal et compte, natures → compte et libellé, schémas d'écritures, codes Axe2, comptes, dates d'exercice. |

Chaque ligne a une colonne **Contrôle**. L'export reste vide tant qu'une ligne
est signalée : date hors exercice, montant, nature, mode, membre inconnu, tiers
provisoire, colonnes du trésorier à compléter.

## Écritures générées

| Cas | Écritures (un Mvt) |
|---|---|
| Recette d'un membre payée | 411 D / 7xx C + trésorerie D / 411 C (journal du paiement) |
| Recette d'un membre non payée | 411 D / 7xx C (VT) : reste dû par le membre |
| Recette d'un autre payeur | trésorerie D / 7xx C |
| Dépense payée | 6xx D / trésorerie C ; carte Isracard : 6xx D / 580000 C (OD) |
| Dépense avancée par un membre | 6xx D / 411 du membre C (OD) : dette envers le membre |
| Gestion | trésorerie D / compte choisi C (reçu) ; compte choisi D / trésorerie C (versé) |

## Circuit

1. Le trésorier prépare un fichier par activité : il choisit le code dans
   Activité!C3, enregistre une copie et la partage (OneDrive, « Peut
   modifier »).
2. Le bénévole remplit les onglets et enregistre.
3. Le trésorier complète les colonnes « trésorier » de Gestion et attribue
   un compte aux tiers provisoires.
4. Export › copier les lignes → ComptaJLC, Transmission, A7, Collage spécial
   › Valeurs → report sous Écritures (voir l'onglet Transmission).
5. Vider ou archiver le fichier de liaison.

## Vérifications (LibreOffice, `tests/recette_liaison.py`)

Tous les cas sont conformes :

| Cas | Résultat |
|---|---|
| Fichier complet (activité MAN.001 + gestion) | 7 opérations, 16 lignes attendues ; activité : 3 participants, 450 ₪ de recettes, 290 ₪ de dépenses, résultat 160 ₪ |
| Colonnes du trésorier vides en Gestion | export bloqué avec le motif |
| Tiers provisoire sans compte | export bloqué, « compte à attribuer par le trésorier » |
| Export collé dans Transmission | Mvt définitifs 422 à 428, prêt à reporter |

À vérifier dans Excel : les listes déroulantes, dont la recherche en tapant.
