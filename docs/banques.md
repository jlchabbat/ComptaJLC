# Banques de l'association

Toutes les banques (et la caisse) arrivent dans l'application par **un seul fichier** `Banque.xlsx`,
préparé en amont par l'administrateur (Power Query, dossier `Telechgt` du PC) : l'application ne lit aucun
format propre à une banque (plus de PDF Mizrahi, plus de fichier Bit particulier).

| Colonne | Contenu |
|---------|---------|
| `Jnl` | code du journal de la banque ou de la caisse (B1, B2, B3…) |
| `Date` | date de l'opération |
| `Libelle` | libellé de la banque, dans sa langue d'origine (hébreu conservé) |
| `Debit` | entrée d'argent sur le compte (ou vide) |
| `Credit` | sortie d'argent (ou vide) |
| `Solde` | solde après la ligne, **facultatif** (Bit n'en donne pas) ; sert à contrôler le relevé |

Une ligne déjà importée (même journal, date, montants et rang dans la journée) n'est jamais ajoutée deux
fois : un relevé qui chevauche le précédent se recharge sans doublon. Changer de banque ne change rien
à l'application, seulement à la préparation du fichier.
