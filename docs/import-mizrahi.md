# Modèle d'import — Banques 1 et 2 (Mizrahi-Tefahot)

Banque 1 et Banque 2 utilisent le même modèle : le relevé PDF exporté depuis
le site de Mizrahi-Tefahot (fichier de référence : `tnuot.pdf`,
« תנועות » = mouvements).

## Document

- PDF A4, en hébreu (lecture de droite à gauche), généré par le site de la banque
  (titre `מזרחי-טפחות`). Le texte est extractible : pas besoin d'OCR.
- Titre : `עובר ושב - יתרה ותנועות בחשבון` (compte courant — solde et mouvements).

### En-tête (page 1)

| Libellé hébreu                                | Sens                        | Exemple                  |
|-----------------------------------------------|-----------------------------|--------------------------|
| `הדפסה בוצעה בתאריך … בשעה …`                 | Date et heure d'impression  | 26/09/2026 09:21         |
| `חשבון מספר`                                  | Numéro de compte            | `732-182029`             |
| (ligne suivante)                              | Titulaire                   | `לשכת בוני ישראל של בני בר` |
| `תנועות בחשבון מתאריך … עד …`                 | Période                     | 25/10/2025 → 26/09/2026  |
| `יתרה קודמת נכון ל- … : ₪…`                   | Solde d'ouverture et sa date | 24/10/2025 : ₪38 053,70 |

Le numéro de compte permet de savoir s'il s'agit de Banque 1 ou de Banque 2.

### Tableau des mouvements

L'en-tête du tableau est répété en haut de chaque page. Colonnes, de droite à gauche :

| Colonne hébreu | Sens              | Format / règle                                                  |
|----------------|-------------------|-----------------------------------------------------------------|
| `תאריך`        | Date d'opération  | `jj/mm/aa` (ex. `28/10/25`)                                      |
| `תאריך ערך`    | Date de valeur    | `jj/mm/aa`, le plus souvent vide                                 |
| `סוג תנועה`    | Type d'opération  | texte hébreu (voir ci-dessous)                                   |
| `זכות/חובה`    | Montant           | signé, séparateur de milliers `,` et décimal `.` : positif = crédit (entrée), négatif = débit (sortie) |
| `יתרה בש"ח`    | Solde en ₪        | affiché seulement sur la **dernière ligne de chaque date** ; vide sinon |
| `אסמכתה`       | Référence         | numéro (ex. `99012`, `2890052` = n° de chèque)                   |

Une icône en forme de flèche signale les lignes qui ont un détail dans
l'interface web : elle n'est pas reprise dans le PDF et peut être ignorée.
Pied de la dernière page : `(י)` = opération faite en ligne, `(פ)` = opération
faite par un employé de la banque.

## Règles pour l'import

- La monnaie est le shekel (₪) ; les montants ne sont pas des euros.
- Pour chaque ligne : solde précédent + montant = solde affiché (quand il y en a un).
  L'import doit vérifier cette chaîne depuis le solde d'ouverture ; sur le fichier
  de référence, les 156 lignes se contrôlent sans écart et donnent le solde final
  ₪64 908,23.
- Les suffixes `(י)` / `(פ)` et le symbole `<` (icône de chèque) ne font pas
  partie du libellé utile.
- Un relevé peut chevaucher le précédent : dédoublonner sur
  (date, montant, référence, type).

## Types d'opération rencontrés

| Hébreu                                  | Français                                  |
|-----------------------------------------|-------------------------------------------|
| `פירעון שיק`                            | Chèque émis encaissé (réf. = n° de chèque) |
| `הפקדת שיק` / `הפקדת שיק בסלולר`        | Remise de chèque (au guichet / par mobile) |
| `הפקדת מזומן`                           | Versement d'espèces                        |
| `ב.הפועלים-ביט`                         | Virement reçu de Bit (voir Banque 3)       |
| `זיכוי מידי-…` / `זיכוי - בנק …`         | Virement reçu (immédiat / d'une autre banque) |
| `העברה באינטרנט`                        | Virement internet (entrant ou sortant selon le signe) |
| `העברה לבנק אחר` / `העברה לחשבון אחר`   | Virement vers une autre banque / un autre compte |
| `העברה מחשבון בסניף אחר`                | Virement depuis un compte d'une autre agence |
| `יומן זכות`                             | Écriture de crédit                         |
| `ישראכרט`                               | Prélèvement carte Isracard                 |
| `עמלת מסלול`, `מסלול-ע.פעולה ע"י פקיד`, `מסלול-ע.ערוץ ישיר`, `עמלת הפקת פנקסי שיקים` | Frais bancaires |
| `עמלת העברה לחו"ל/מחו"ל`, `עמלת העברת ש"ח ל/מחו"ל`, `הוצאות סוויפט` | Frais de virement international |
| `העברת שקלים מחו"ל`                     | Shekels reçus de l'étranger                |
| `המרת מטח לש"ח` / `רכישת מטח נגד ש"ח`   | Change devises → ₪ / achat de devises      |
| `פצפ שבוע-המשך`, `פצפ לחודש`, `ליצ י קבועה שנה` | Dépôts à terme (placement / retour) |
| `ריבית פקמ`                             | Intérêts de dépôt                          |
| `פק הבטחת עיקול`                        | Dépôt de garantie (saisie)                 |
| `החזרת זיכוי מסב`                       | Retour d'un virement Masav                 |

Les placements `פצפ שבוע-המשך` apparaissent par paires qui s'annulent
(ex. +3 029,54 puis −3 029,58 le même jour, avec `ריבית פקמ` entre les deux).

## Lien avec Banque 3 (Bit)

Les lignes Bit `BANQUE - BANQUE - VIREMENT BIT VERS BANQUE` se retrouvent ici
en `ב.הפועלים-ביט`, à la même date et pour le même montant (ex. 11/01/2026,
6 820). C'est un virement interne : il ne doit pas être compté deux fois.
