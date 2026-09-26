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
| Bénévole | fiches de liaison (lot suivant) |

Les comptes se créent dans Référentiels › Utilisateurs, avec leur groupe.

## Pages (socle W0)

Tableau de bord (produits, charges, résultat, trésorerie par journal,
résultat par axe 1 et 2, état des contrôles) · Écritures (filtres journal,
compte, axe 2, recherche) · Mouvement · Grand livre (solde cumulé) ·
Balance · Analytique · Contrôles (RG-01 à RG-04, comptes de liaison) ·
Journal des modifications (repris du classeur).

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
