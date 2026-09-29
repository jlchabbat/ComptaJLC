# Ouvrir une comptabilité reprise de Ciel Compta (site séparé)

Comptabilité tenue en euros, un seul axe analytique, journaux en ₪ et en $ avec leur montant d'origine,
axes de comptes du plan Ciel (RubDecl, RubCh, RubType, Cat, RubrCat, Groupe…) combinables.

## 1. Préparer les fichiers (sur le poste de développement)

```
python src/reprise_ciel.py Plan.xlsx RImport.txt --traductions Traduction.xlsx
```

Produit `Imports/reprise_ciel.zip` : Reglages (un seul axe), Exercices, Axe1, PlanComptable, AxesComptes,
Journaux (compte de trésorerie et devise), Ecritures (Mvt 1, 2, 3… ; pièce = n° Ciel ; montant d'origine ;
lettrage), Traductions, et `Rapport.txt` (équilibre, soldes par compte à comparer à la balance Ciel).

## 2. Créer le site

1. Nouveau compte PythonAnywhere (un site par dossier).
2. Onglet Web › Add a new web app › Manual configuration › Python 3.12.
3. Télécharger le ZIP de ComptaBB (branche en service sur GitHub), l'envoyer dans Files.
4. Console Bash : `unzip -qo ComptaBB-*.zip -d ~/inst && bash ~/inst/*/appli/deploiement/installer.sh`
   (détail : `docs/installation.html`).
5. Ouvrir le site : code d'installation affiché par l'installateur, premier administrateur.
6. « Premier démarrage » : nom, devise **€**, exercice, **« Mes propres fichiers »**.

## 3. Charger la reprise

Administration › Imports / Exports › déposer `reprise_ciel.zip` › **Tout importer**.
Contrôle › Contrôles doit afficher OK ; la balance doit donner les soldes de `Rapport.txt`.

## 4. Au quotidien

- **Relevés** : Banque › Relevés à passer en compta › journal › importer le fichier :
  Revolut (CSV, frais compris, opérations en attente ignorées), Isracard (xlsx : deux cartes, date de
  prélèvement, montant débité en sortie, « (SUR montant d'achat) » au libellé, sans solde),
  Mizrahi (PDF). Pointage automatique sur le montant d'origine ; pour une ligne restante, le compte déjà
  utilisé pour ce libellé est proposé (« Reprendre toutes les propositions »), puis Enregistrer : l'écriture
  est créée en euros au cours BCE du jour, montant d'origine gardé.
- **Appli Banque** : son `Ecrt.csv` (ou `RImport.xlsx`) se dépose dans Imports / Exports › Tout importer :
  écritures créées (Npiece = montant d'origine), déjà présentes ignorées, relevés pointés.
- **Lexique** de l'appli Banque (`Fichiers\Lexique.xlsx`) : renommé `Traductions.xlsx`, il s'importe tel quel.
- **Cours BCE** : pris au besoin ; `python manage.py taux_bce` en tâche planifiée. Si la BCE est
  injoignable depuis l'hébergement, réglage `cours_ILS` / `cours_USD` (unités pour 1 €).
- **Analyse par axes de comptes** (menu Consulter) : un axe en lignes, un en colonnes, filtres sur les autres.
- **Justificatifs** : sur la fiche de l'écriture, ou en masse (Administration › Justificatifs existants).

## 5. Licence

Site créé par l'assistant : essai de 60 jours, puis lecture seule. L'éditeur délivre la licence
(`python manage.py licence --site <adresse> --fin AAAA-MM-JJ`, clé privée hors dépôt).
