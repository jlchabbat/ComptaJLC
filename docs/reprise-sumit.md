# Reprise de l'extrait SUMIT (remise à zéro de la base)

L'extrait SUMIT (`EXTRACT_SUMIT_*.xlsx`, données définitives 2026) remplace
toute la comptabilité du site. L'application et ses formats de fichiers ne
changent pas : le classeur SUMIT est converti en **export complet** (.zip),
le format que la page *Base de données* sait déjà recharger.

## 1. Produire le fichier (poste ou console PythonAnywhere)

```
python src/reprise_sumit.py EXTRACT_SUMIT_27092026.xlsx Exports
```

Le script charge l'extrait dans une base neuve et temporaire, vérifie les
contrôles de l'application et la balance SUMIT compte par compte, puis écrit
`Export_complet_SUMIT_<date>.zip`. Code de sortie 1 en cas d'anomalie.

Adaptations aux structures de la base :

| SUMIT | Base |
|---|---|
| codes `ACT1`, `COT2`… (axe 1) | `ACT.1`, `COT.2`… |
| `BIL1` | `BIL.1` (classes 1-2), `BIL.4` (tiers), `BIL.5` (trésorerie) |
| codes `MAN7`, `SOC4`… (axe 2) ; ligne sans axe 2 | `MAN.007`, `SOC.004`… ; `GEN.001` |
| pièce `B3-001` (2 lignes) | un Mvt, numéroté dans l'ordre des dates ; Pièce = N° de la Base SUMIT (repris dans le commentaire avec source, statut et catégorie) |
| opérations de montant nul (N° 396, 400, 403) | écartées |
| journaux AN, B1, B2, B3, CA, OD | idem, plus VT et HA (saisie guidée) |
| Lexique HE-FR | traductions du relevé |
| Rappro Mizrahi CC | relevé B1 (134 lignes), pointé comme dans SUMIT |

L'exercice 2026 commence le 31/12/2025 : 9 recettes Rallye (BIT) sont datées
de ce jour dans SUMIT et font partie de 2026 ; leurs dates sont gardées.

## 2. Recharger sur le site

*Base de données › Remettre à zéro et recharger* : choisir le .zip, case
« Fichiers modifiés » **décochée**. Une sauvegarde est faite juste avant ; les
comptes utilisateurs sont gardés, tout le reste (écritures, tiers, pointages,
fiches, historique, paramètres) est remplacé.

## Résultat attendu (extrait du 27/09/2026)

408 mouvements, 816 lignes, 1 434 462,58 ₪ au débit et au crédit (= balance
SUMIT). Relevé B1 entièrement pointé ; reste une écriture non pointée
(N° 367 WEBER, 200 ₪, absente du relevé). À vérifier : compte d'attente
470000 soldé à 1 575 ₪ (régularisation année précédente et saisie « TEST »).
