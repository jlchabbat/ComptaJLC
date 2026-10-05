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


# ---------------------------------------------------------------- traduction automatique par l'API de Claude

MODELE_CLAUDE = "claude-haiku-4-5-20251001"
LOT = 40


def cle_api():
    """Clé d'API : variable ANTHROPIC_API_KEY, ou fichier cle-claude.txt du dossier de données (jamais dans la base ni dans les exports)."""
    import os

    from django.conf import settings
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"].strip()
    fichier = settings.DATA_DIR / "cle-claude.txt"
    return fichier.read_text(encoding="utf-8").strip() if fichier.is_file() else ""


def traduire_par_claude(libelles):
    """{libellé hébreu: traduction française} pour au plus LOT libellés (seul le texte du libellé est envoyé : ni montant ni nom de banque).
    Lève ValueError avec un message lisible si la clé manque ou si l'appel échoue."""
    import json
    import urllib.error
    import urllib.request

    cle = cle_api()
    if not cle:
        raise ValueError("Clé d'API Claude absente : voir Administration › Principes de fonctionnement (PDF), « Traduction automatique ».")
    libelles = list(dict.fromkeys(libelles))[:LOT]
    if not libelles:
        return {}
    consigne = ("Tu traduis des libellés d'opérations de relevés bancaires israéliens (hébreu) pour la comptabilité d'une association française. "
                "Pour chaque libellé, donne une traduction française courte (2 à 6 mots), en gardant tels quels les chiffres, dates et noms propres latins ; "
                "translittère les noms de personnes ou d'enseignes hébreux en lettres latines majuscules. "
                "Réponds uniquement par un tableau JSON de chaînes, dans le même ordre et de même longueur que la liste reçue.")
    corps = {"model": MODELE_CLAUDE, "max_tokens": 2000, "system": consigne,
             "messages": [{"role": "user", "content": json.dumps(libelles, ensure_ascii=False)}]}
    requete = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(corps).encode("utf-8"), method="POST",
                                     headers={"x-api-key": cle, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(requete, timeout=60) as r:
            reponse = json.load(r)
    except urllib.error.HTTPError as e:
        raise ValueError(f"Service de traduction refusé (code {e.code}) : vérifier la clé d'API et le crédit du compte.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ValueError("Service de traduction injoignable (réseau ou accès sortant non autorisé par l'hébergement).") from e
    texte = "".join(b.get("text", "") for b in reponse.get("content", []) if b.get("type") == "text")
    debut, fin = texte.find("["), texte.rfind("]")
    try:
        valeurs = json.loads(texte[debut:fin + 1])
    except ValueError as e:
        raise ValueError("Réponse du service de traduction illisible.") from e
    if not isinstance(valeurs, list) or len(valeurs) != len(libelles):
        raise ValueError("Réponse du service de traduction incomplète.")
    return {h: str(t).strip()[:120] for h, t in zip(libelles, valeurs) if str(t).strip()}
