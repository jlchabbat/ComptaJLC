"""Propositions de traduction des libellés de relevé (hébreu → français), à valider par le trésorier.

Pas de traduction automatique en ligne : un glossaire des termes bancaires et comptables courants, appliqué mot à mot
(avec ou sans préfixe ה/ב/ל/מ/ו). Les traductions déjà validées (Traduction) servent aussi de glossaire : un mot connu seul
dans une traduction est repris. Les mots inconnus restent en hébreu : la proposition est alors « à compléter »."""

import re

from .models import Traduction

GLOSSAIRE = {
    "העברה": "virement", "העברת": "virement", "זיכוי": "crédit", "חיוב": "prélèvement", "משיכה": "retrait", "משיכת": "retrait",
    "מזומן": "espèces", "מזומנים": "espèces", "הפקדה": "dépôt", "הפקדת": "dépôt", "שיק": "chèque", "שיקים": "chèques",
    "עמלה": "commission", "עמלת": "commission", "עמלות": "frais", "ריבית": "intérêts", "הוראת": "ordre", "קבע": "permanent",
    "כרטיס": "carte", "אשראי": "crédit", "ישראכרט": "Isracard", "כאל": "Cal", "מקס": "Max", "ביט": "Bit", "פייבוקס": "PayBox",
    "חשמל": "électricité", "מים": "eau", "ארנונה": "taxe municipale", "ביטוח": "assurance", "לאומי": "Leumi",
    "הכנסה": "revenu", "מס": "impôt", 'מע"מ': "TVA", "מעמ": "TVA", "שכר": "salaire", "שכירות": "loyer", "טלפון": "téléphone",
    "סלולר": "mobile", "בזק": "Bezeq", "אינטרנט": "internet", "תרומה": "don", "תרומות": "dons", "חבר": "membre", "חברים": "membres",
    "דמי": "frais", "החזר": "remboursement", "פרעון": "remboursement", "הלוואה": "prêt", "בנק": "banque", "מזרחי": "Mizrahi",
    "טפחות": "Tefahot", "הפועלים": "Hapoalim", "דיסקונט": "Discount", "ניכוי": "retenue", "ניהול": "gestion", "חשבון": "compte",
    "יתרה": "solde", "פתיחה": "ouverture", "רכישה": "achat", "קניה": "achat", "מכירה": "vente", "תשלום": "paiement",
    "תשלומים": "paiements", "קבלה": "reçu", "חשבונית": "facture", "ספק": "fournisseur", "לקוח": "client", "דואר": "poste",
    "ועד": "comité", "מתנה": "cadeau", "אירוע": "événement", "אולם": "salle", "קייטרינג": "traiteur", "מסעדה": "restaurant",
    "סופר": "supermarché", "שוטף": "courant", "עו\"ש": "compte courant", "עוש": "compte courant", "מט\"ח": "devises", "מטח": "devises",
    "כניסה": "entrée", "יציאה": "sortie", "בינלאומי": "international", "פנסיה": "retraite", "קרן": "fonds", "השתלמות": "formation",
    "חינוך": "éducation", "בריאות": "santé", "רופא": "médecin", "תרופות": "médicaments", "דלק": "carburant", "חניה": "parking",
    "נסיעה": "déplacement", "מלון": "hôtel", "טיסה": "vol", "הדפסה": "impression", "משרד": "bureau", "ציוד": "matériel",
    "תיקון": "réparation", "ניקיון": "nettoyage", "אבטחה": "sécurité", "מנוי": "abonnement", "אגרה": "droit", "אגרת": "droit",
    "רישום": "inscription", "הרשמה": "inscription", "השתתפות": "participation", "כנס": "congrès", "טיול": "voyage", "מועדון": "club",
    "הנהלת": "gestion", "חשבונות": "comptes", "זיכוי": "crédit", "הפרשי": "écarts", "שער": "change", "ערך": "valeur",
}
PREFIXES = "הבלמוכש"
PONCTUATION = re.compile(r"[‎‏‪-‮'’׳.,;:()\[\]/\\-]+")
HEBREU = re.compile(r"[֐-׿]")


def _mot(m):
    """Traduction d'un mot hébreu, ou None."""
    m = m.replace("״", '"')
    if m in GLOSSAIRE:
        return GLOSSAIRE[m]
    if len(m) > 3 and m[0] in PREFIXES and m[1:] in GLOSSAIRE:
        return GLOSSAIRE[m[1:]]
    return None


def _glossaire_valide():
    """Mots hébreux isolés déjà traduits par le trésorier (une traduction d'un seul mot) : {mot: traduction}."""
    return {t.cle: t.traduction for t in Traduction.objects.all() if " " not in t.hebreu.strip() and t.cle}


def proposer(texte):
    """(proposition, complete) : le libellé traduit mot à mot ; complete = plus aucun mot hébreu. ('', False) si rien de reconnu."""
    propres = _glossaire_valide()
    sortie, reconnus, restants = [], 0, 0
    for brut in (texte or "").split():
        mot = PONCTUATION.sub("", brut)
        if not HEBREU.search(mot):
            sortie.append(brut)                                  # nombre, date, nom latin : gardé tel quel
            continue
        t = propres.get(Traduction.cle_de(mot)) or _mot(mot)
        if t:
            sortie.append(t)
            reconnus += 1
        else:
            sortie.append(brut)
            restants += 1
    if not reconnus:
        return "", False
    texte_fr = " ".join(sortie)
    return (texte_fr[:1].upper() + texte_fr[1:])[:120], restants == 0
