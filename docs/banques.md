# Banques de l'association

Toutes les banques (et la caisse) arrivent dans l'application par **un seul fichier** `Banque.xlsx`,
préparé en amont par l'administrateur (Power Query, dossier `Telechgt` du PC) : l'application ne lit aucun
format propre à une banque (plus de PDF Mizrahi, plus de fichier Bit particulier).

| Colonne | Contenu |
|---------|---------|
| `Journ` | code du journal de la banque ou de la caisse (B1, B2, B3…) |
| `Date` | date de l'opération |
| `Libelle` | libellé de la banque, dans sa langue d'origine (hébreu conservé) |
| `Debit` | **sortie** d'argent du compte, point de vue de la banque (ou vide) |
| `Credit` | **entrée** d'argent sur le compte (ou vide) |
| `Etat` | `TERMINE` (ou vide) : la ligne est importée ; toute autre valeur : ligne ignorée, pas encore définitive |

Le montant en devise d'origine n'est pas repris (comptabilité en une seule devise), et il n'y a pas de colonne de solde.

Une ligne déjà importée (même journal, date, libellé et montant ; deux lignes identiques le même jour comptent pour deux) n'est jamais ajoutée deux
fois : un relevé qui chevauche le précédent se recharge sans doublon. Changer de banque ne change rien
à l'application, seulement à la préparation du fichier.
