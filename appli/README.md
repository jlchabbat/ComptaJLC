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
| Trésorier | tout, y compris les référentiels (menu Référentiels) |
| Bureau, Vérificateur | consultation : tableau de bord, écritures, grand livre, balance, analytique, contrôles, journal |
| Bénévole | ses fiches bénévoles seulement : saisie des lignes, nouveaux tiers provisoires, transmission |

Les comptes se créent dans Référentiels › Utilisateurs, avec leur groupe ;
un bénévole se crée aussi depuis Fiches bénévoles › Nouveau bénévole.

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

1. Le trésorier crée la fiche : **Activité** (code axe 2 fixé d'avance) ou
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
