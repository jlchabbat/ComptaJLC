"""Justificatifs (scans, photos) rattachés aux mouvements.

Fichiers rangés dans <dossier des données>/Justificatifs/<année>/Mvt<n°>_<rang>_<nom>, hors du code : ils survivent
aux mises à jour. Ajouter un justificatif ne change pas la comptabilité ; le supprimer est refusé dans un exercice clos.
Chaque ajout ou suppression est inscrit dans l'historique."""

import mimetypes
import re
import unicodedata

from django.conf import settings

from .models import Exercice, Justificatif, Modification

EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tif", ".tiff")
TAILLE_MAXI = 10 * 1024 * 1024          # 10 Mo par fichier


def dossier():
    d = settings.DATA_DIR / "Justificatifs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def chemin(j):
    return dossier() / j.chemin if j.chemin else None


def type_mime(j):
    return mimetypes.guess_type(j.nom)[0] or "application/octet-stream"


def _nom_sur(nom):
    nom = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    nom = re.sub(r"[^A-Za-z0-9._+ -]+", "_", nom)            # espaces et « + » gardés : « 389+412 facture.pdf »
    nom = re.sub(r" {2,}", " ", nom).strip("._ ") or "document"
    return nom[-80:]


def verifier(fichier):
    """Message d'erreur, ou '' si le fichier est accepté."""
    nom = fichier.name or ""
    if not nom.lower().endswith(EXTENSIONS):
        return f"« {nom} » : format non accepté (PDF ou image : JPG, PNG, HEIC…)."
    if fichier.size > TAILLE_MAXI:
        return f"« {nom} » : fichier trop volumineux ({fichier.size // (1024 * 1024)} Mo ; 10 Mo au plus)."
    if fichier.size == 0:
        return f"« {nom} » : fichier vide."
    return ""


def ajouter(mouvement, fichier, description="", auteur=""):
    """Enregistre le fichier (objet UploadedFile ou File) et renvoie le Justificatif. Lève ValueError si refusé."""
    erreur = verifier(fichier)
    if erreur:
        raise ValueError(erreur)
    rang = mouvement.justificatifs.count() + 1
    relatif = f"{mouvement.date:%Y}/Mvt{mouvement.numero}_{rang}_{_nom_sur(fichier.name)}"
    while Justificatif.objects.filter(chemin=relatif).exists() or (dossier() / relatif).exists():
        rang += 1
        relatif = f"{mouvement.date:%Y}/Mvt{mouvement.numero}_{rang}_{_nom_sur(fichier.name)}"
    cible = dossier() / relatif
    cible.parent.mkdir(parents=True, exist_ok=True)
    with open(cible, "wb") as sortie:
        for morceau in fichier.chunks():
            sortie.write(morceau)
    j = Justificatif.objects.create(mouvement=mouvement, chemin=relatif, nom=fichier.name[:150],
                                    description=description[:150], taille=cible.stat().st_size, ajoute_par=auteur)
    Modification.objects.create(auteur=auteur, lot="Justificatifs", action="Ajout d'un justificatif",
                                objet=f"Mvt {mouvement.numero}", apres=f"{j.nom} ({j.taille // 1024} Ko) {description}"[:300])
    return j


def ajouter_lien(mouvement, lien, nom="", description="", auteur=""):
    """Rattache un document resté en ligne (SUMIT…) : on garde son lien. Lève ValueError si refusé."""
    lien = (lien or "").strip()
    if not re.match(r"^https://", lien):
        raise ValueError(f"Lien refusé (adresse https:// attendue) : {lien[:80]}")
    if mouvement.justificatifs.filter(lien=lien).exists():
        raise ValueError(f"Ce lien est déjà joint au mouvement {mouvement.numero}.")
    j = Justificatif.objects.create(mouvement=mouvement, lien=lien[:500], nom=(nom or "Document en ligne")[:150],
                                    description=description[:150], ajoute_par=auteur)
    Modification.objects.create(auteur=auteur, lot="Justificatifs", action="Ajout d'un lien de justificatif",
                                objet=f"Mvt {mouvement.numero}", apres=f"{j.nom} {description} {lien}"[:300])
    if getattr(settings, "RAPATRIER_LIENS", True):
        try:
            rapatrier(j, auteur)                          # le document est aussitôt copié sur le site si possible
        except ValueError:
            pass                                          # sinon le lien reste ; « Enregistrer sur le site » réessaiera
    return j


# ---------------------------------------------------------------- documents en ligne copiés sur le site

SIGNATURES = ((b"%PDF", ".pdf"), (b"\xff\xd8\xff", ".jpg"), (b"\x89PNG", ".png"), (b"GIF8", ".gif"),
              (b"II*\x00", ".tif"), (b"MM\x00*", ".tif"))


def _extension(contenu):
    for debut, ext in SIGNATURES:
        if contenu.startswith(debut):
            return ext
    if contenu[:4] == b"RIFF" and contenu[8:12] == b"WEBP":
        return ".webp"
    if contenu[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        return ".heic"
    return None


def telecharger(lien):
    """(contenu, nom proposé par le serveur ou '') du document à l'adresse lien. Lève ValueError si impossible."""
    import urllib.error
    import urllib.request
    from email.message import Message
    requete = urllib.request.Request(lien, headers={"User-Agent": "Mozilla/5.0 (ComptaBB)"})
    try:
        with urllib.request.urlopen(requete, timeout=30) as r:
            contenu = r.read(TAILLE_MAXI + 1)
            entete = Message()
            entete["content-disposition"] = r.headers.get("Content-Disposition", "")
            nom = entete.get_filename() or ""
    except urllib.error.HTTPError as e:
        raise ValueError(f"le site du document répond « {e.code} {e.reason} »") from None
    except (urllib.error.URLError, OSError) as e:
        raise ValueError("site du document injoignable depuis ComptaBB "
                         f"({getattr(e, 'reason', e)} ; offre gratuite PythonAnywhere : seuls certains sites sont permis)") from None
    if len(contenu) > TAILLE_MAXI:
        raise ValueError("document de plus de 10 Mo")
    return contenu, nom


def rapatrier(j, auteur=""):
    """Copie sur le site le document d'un justificatif « lien » ; le justificatif devient un fichier et le lien est
    oublié (gardé dans l'historique). Lève ValueError si le document ne peut pas être récupéré."""
    if not j.lien:
        return j
    contenu, nom = telecharger(j.lien)
    ext = _extension(contenu)
    if not ext:
        debut = contenu[:500].lower()
        if b"<html" in debut or b"<!doctype" in debut:
            raise ValueError("le lien renvoie une page web (connexion à SUMIT demandée ?), pas le document")
        raise ValueError("le lien ne renvoie ni un PDF ni une image")
    base = nom.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if nom else f"SUMIT_Mvt{j.mouvement.numero}"
    if not base.lower().endswith(EXTENSIONS):
        base = base.rsplit(".", 1)[0] + ext if "." in base else base + ext
    m = j.mouvement
    rang = m.justificatifs.count()
    relatif = f"{m.date:%Y}/Mvt{m.numero}_{rang}_{_nom_sur(base)}"
    while Justificatif.objects.filter(chemin=relatif).exists() or (dossier() / relatif).exists():
        rang += 1
        relatif = f"{m.date:%Y}/Mvt{m.numero}_{rang}_{_nom_sur(base)}"
    cible = dossier() / relatif
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_bytes(contenu)
    ancien = j.lien
    j.chemin, j.lien, j.taille = relatif, "", len(contenu)
    if j.nom in ("Document en ligne", "Document SUMIT") or j.nom.startswith(("DEPENSES", "Liens")) or " du " in j.nom or "(lien)" in j.nom:
        j.nom = base[:150]
    j.save()
    Modification.objects.create(auteur=auteur, lot="Justificatifs", action="Document en ligne enregistré sur le site",
                                objet=f"Mvt {m.numero}", avant=ancien[:300], apres=f"{j.nom} ({j.taille // 1024} Ko)"[:300])
    return j


def rapatrier_tous(auteur="", limite=None):
    """Copie sur le site les documents encore en ligne. Renvoie (nombre copié, erreurs, nombre restant)."""
    faits, erreurs = 0, []
    liens = Justificatif.objects.exclude(lien="").select_related("mouvement").order_by("mouvement__numero", "pk")
    for j in (liens[:limite] if limite else liens):
        try:
            rapatrier(j, auteur)
            faits += 1
        except ValueError as e:
            erreurs.append(f"Mvt {j.mouvement.numero} : {e}.")
    return faits, erreurs, Justificatif.objects.exclude(lien="").count()


def copier(j, mouvement, auteur=""):
    """Joint aussi le document du justificatif j à un autre mouvement (copie du fichier, ou même lien)."""
    if mouvement.pk == j.mouvement_id:
        raise ValueError(f"Ce document est déjà joint au mouvement {mouvement.numero}.")
    if j.lien:
        return ajouter_lien(mouvement, j.lien, j.nom, j.description, auteur)
    from django.core.files import File
    source = chemin(j)
    if not source or not source.exists():
        raise ValueError(f"Fichier de « {j.nom} » introuvable sur le site.")
    with open(source, "rb") as flux:
        copie = ajouter(mouvement, File(flux, name=j.nom), j.description or f"aussi joint au Mvt {j.mouvement.numero}", auteur)
    return copie


def numeros(texte):
    """N° de Mvt d'une saisie « 389 », « 389+412 », « 389, 412 » (dans l'ordre, sans doublon)."""
    vus = []
    for n in re.findall(r"\d+", texte or ""):
        if int(n) not in vus:
            vus.append(int(n))
    return vus


# ---------------------------------------------------------------- documents des fiches bénévoles

def ajouter_document_fiche(fiche, fichier, ligne=None, description="", auteur=""):
    """Range le reçu d'un bénévole avec sa fiche (Justificatifs/Fiches/<n° de fiche>/) ; ValueError si refusé."""
    from .models import DocumentFiche
    erreur = verifier(fichier)
    if erreur:
        raise ValueError(erreur)
    rang = fiche.documents.count() + 1
    relatif = f"Fiches/{fiche.pk}/{rang}_{_nom_sur(fichier.name)}"
    while DocumentFiche.objects.filter(chemin=relatif).exists() or (dossier() / relatif).exists():
        rang += 1
        relatif = f"Fiches/{fiche.pk}/{rang}_{_nom_sur(fichier.name)}"
    cible = dossier() / relatif
    cible.parent.mkdir(parents=True, exist_ok=True)
    with open(cible, "wb") as sortie:
        for morceau in fichier.chunks():
            sortie.write(morceau)
    d = DocumentFiche.objects.create(fiche=fiche, ligne=ligne, chemin=relatif, nom=fichier.name[:150],
                                     description=description[:150], taille=cible.stat().st_size, ajoute_par=auteur)
    Modification.objects.create(auteur=auteur, lot="Fiches", action="Document joint à une fiche", objet=f"fiche {fiche.pk} {fiche.titre}"[:200],
                                apres=f"{d.nom} ({d.taille // 1024} Ko) {description}"[:300])
    return d


def supprimer_document_fiche(d, auteur=""):
    fichier = dossier() / d.chemin
    Modification.objects.create(auteur=auteur, lot="Fiches", action="Document retiré d'une fiche", objet=f"fiche {d.fiche_id}",
                                avant=d.nom)
    d.delete()
    if fichier.exists():
        fichier.unlink()


def documents_vers_justificatifs(l, mouvement, auteur=""):
    """Au report d'une ligne de fiche : ses documents, et ceux de toute la fiche, deviennent justificatifs du mouvement."""
    from django.core.files import File
    from django.db.models import Q
    n = 0
    for d in l.fiche.documents.filter(Q(ligne=l) | Q(ligne__isnull=True)):
        source = dossier() / d.chemin
        if source.exists():
            with open(source, "rb") as flux:
                ajouter(mouvement, File(flux, name=d.nom), d.description or f"fiche bénévole « {l.fiche.titre} »", auteur)
            n += 1
    return n


def refus_suppression(j):
    if Exercice.date_close(j.mouvement.date):
        return "Mouvement dans un exercice clos : ses justificatifs ne se suppriment plus."
    return ""


def supprimer(j, auteur=""):
    refus = refus_suppression(j)
    if refus:
        raise ValueError(refus)
    fichier = chemin(j)
    Modification.objects.create(auteur=auteur, lot="Justificatifs", action="Suppression d'un justificatif",
                                objet=f"Mvt {j.mouvement.numero}", avant=f"{j.nom} {j.description}"[:300])
    j.delete()
    if fichier and fichier.exists():
        fichier.unlink()


# ---------------------------------------------------------------- documents existants : dépôt, proposition, rattachement

def a_classer_dossier():
    d = dossier() / "_a_classer"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _deposer_un(nom, contenu):
    """Range un fichier dans « à classer » ; renvoie son nom, ou lève ValueError."""
    from django.core.files.base import ContentFile
    erreur = verifier(ContentFile(contenu, name=nom))
    if erreur:
        raise ValueError(erreur)
    base = "__".join(_nom_sur(p) for p in re.split(r"[\\/]+", nom) if p)[-150:]
    racine, point, ext = base.rpartition(".")
    cible, lettres = a_classer_dossier() / base, iter("bcdefghijklmnopqrstuvwxyz")
    while cible.exists():                                   # doublon : suffixe en lettres (un chiffre fausserait la proposition)
        cible = a_classer_dossier() / f"{racine}__doublon_{next(lettres)}{point}{ext}"
    cible.write_bytes(contenu)
    return cible.name


def deposer(nom, contenu):
    """Dépose un fichier ou un ZIP (dossiers compris). Renvoie (déposés, refus)."""
    import io
    import zipfile
    deposes, refus = [], []
    if nom.lower().endswith((".xlsx", ".xlsm")):                  # extrait (SUMIT…) : les liens de ses lignes
        try:
            n = deposer_extrait(contenu)
        except Exception:
            return [], [f"« {nom} » : classeur illisible."]
        return [f"lien {i}" for i in range(n)], ([] if n else [f"« {nom} » : aucun nouveau lien trouvé."])
    if nom.lower().endswith(".zip"):
        try:
            z = zipfile.ZipFile(io.BytesIO(contenu))
        except zipfile.BadZipFile:
            return [], [f"« {nom} » : ZIP illisible."]
        with z:
            for info in z.infolist():
                n = info.filename
                if info.is_dir() or "__MACOSX" in n or n.rsplit("/", 1)[-1].startswith("."):
                    continue
                try:
                    deposes.append(_deposer_un(n, z.read(info)))
                except ValueError as e:
                    refus.append(str(e))
        return deposes, refus
    try:
        deposes.append(_deposer_un(nom, contenu))
    except ValueError as e:
        refus.append(str(e))
    return deposes, refus


def _nombre(texte):
    from decimal import Decimal
    return Decimal(texte.replace(",", "."))


def numeros_en_tete(nom):
    """N° de Mvt en tête du nom, suivis d'une espace : « 389 facture.pdf » → [389] ; « 389+412 x.pdf » → [389, 412].
    Dossiers du ZIP (« dossier__ ») ignorés."""
    m = re.match(r"(\d{1,6}(?:\+\d{1,6})*) ", nom.split("__")[-1])
    return numeros(m.group(1)) if m else []


def proposer(nom):
    """Mouvement proposé d'après le nom du fichier : (mouvement ou None, raison, sûr)."""
    import datetime as dt
    from django.db.models import Q
    from .models import Ligne, Mouvement
    base = nom.rsplit(".", 1)[0]
    en_tete = numeros_en_tete(nom)
    if en_tete:                                             # « 389 facture » ou « 389+412 facture » : n° de Mvt en tête
        mvts = [Mouvement.objects.filter(numero=n).first() for n in en_tete]
        texte = "+".join(map(str, en_tete))
        if all(mvts):
            return mvts[0], f"« {texte} » en tête du nom" + (" (plusieurs mouvements)" if len(mvts) > 1 else ""), True
        return None, "Mvt " + ", ".join(str(n) for n, mv in zip(en_tete, mvts) if not mv) + " inconnu", False
    m = re.search(r"(?i)(?:^|[^a-z])mvt[\s_.\-n°o]*(\d{1,6})", base)
    if m:
        mv = Mouvement.objects.filter(numero=int(m.group(1))).first()
        return (mv, f"« Mvt {m.group(1)} » dans le nom", True) if mv else (None, f"Mvt {m.group(1)} inconnu", False)
    m = re.search(r"(?i)(?:^|[^a-z])(?:pi[eè]ce|pce|pc|pj)[\s_.\-n°o]*(\d{1,6})", base)
    if m:
        mv = Mouvement.objects.filter(piece=int(m.group(1))).first()
        return (mv, f"« pièce {m.group(1)} » dans le nom", True) if mv else (None, f"pièce {m.group(1)} inconnue", False)
    reste = base
    date = None
    for motif, ordre in ((r"(20\d\d)[-_.](\d\d)[-_.](\d\d)", "amj"), (r"(\d\d)[-_.](\d\d)[-_.](20\d\d)", "jma"),
                         (r"(?<!\d)(\d\d)(\d\d)(20\d\d)(?!\d)", "jma"), (r"(?<!\d)(20\d\d)(\d\d)(\d\d)(?!\d)", "amj")):
        d = re.search(motif, reste)
        if d:
            a, b, c = (int(x) for x in d.groups())
            try:
                date = dt.date(a, b, c) if ordre == "amj" else dt.date(c, b, a)
            except ValueError:
                continue
            reste = reste[:d.start()] + " " + reste[d.end():]
            break
    montant = None
    d = re.search(r"(?<![\d.,])(\d{1,7}[.,]\d\d)(?![\d])", reste)
    if d:
        montant = _nombre(d.group(1))
        reste = reste[:d.start()] + " " + reste[d.end():]
    if date:
        qs = Mouvement.objects.filter(date=date)
        if montant is not None:
            qs = qs.filter(pk__in=Ligne.objects.filter(mouvement__date=date).filter(
                Q(debit=montant) | Q(credit=montant)).values("mouvement"))
            if qs.count() == 1:
                return qs.first(), f"date {date:%d/%m/%Y} et montant {montant} dans le nom (à vérifier)", False
        elif qs.count() == 1:
            return qs.first(), f"seul mouvement du {date:%d/%m/%Y} (à vérifier)", False
    indice = ""
    if date:
        n = Mouvement.objects.filter(date=date).count()
        indice = (f"{n} mouvements le {date:%d/%m/%Y}" + (f" (montant {montant} introuvable)" if montant is not None else "")
                  + " : saisir le n° de Mvt") if n else f"aucun mouvement le {date:%d/%m/%Y}"
    for n in re.findall(r"(?<!\d)(\d{1,6})(?!\d)", reste):
        n = int(n)
        piece, mvt = Mouvement.objects.filter(piece=n).first(), Mouvement.objects.filter(numero=n).first()
        if piece and mvt and piece != mvt:
            return piece, f"{n} = n° de pièce (c'est aussi le Mvt {n} : à vérifier)", False
        if piece:
            return piece, f"{n} = n° de pièce (à vérifier)", False
        if mvt:
            return mvt, f"{n} = n° de Mvt (à vérifier)", False
    return None, indice or "aucun numéro, date ou montant reconnu", False


def _fichier_liens():
    return a_classer_dossier() / "liens.json"


def lire_liens():
    import json
    f = _fichier_liens()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def ecrire_liens(liens):
    import json
    f = _fichier_liens()
    if liens:
        f.write_text(json.dumps(liens, ensure_ascii=False, indent=1), encoding="utf-8")
    elif f.exists():
        f.unlink()


def _entetes(rangee):
    return [str(v or "").strip().lower() for v in rangee]


MOTS_DATE = ("תאריך", "date", "date opération")
MOTS_MONTANT = ("סכום", "montant", "amount", "somme")
MOTS_MVT = ("mvt", "mouvement", "n° mvt", "numéro de mvt")
MOTS_PIECE = ("pièce", "piece", "n° pièce", "n° de pièce", "pce", "pc", "pj")


def _numero(v):
    """N° de Mvt ou de pièce d'une cellule (389, « 389 », « Mvt 389 ») ; None sinon."""
    if isinstance(v, (int, float)):
        return int(v) or None
    m = re.search(r"\d+", str(v or ""))
    return int(m.group()) if m else None


def lire_extrait(contenu):
    """Lignes à lien d'un extrait Excel (SUMIT ou tableau fait à la main) : Mvt, pièce, date, montant, description, lien.

    Une feuille est retenue si une de ses premières lignes a une colonne « Mvt », une colonne « Pièce », ou à la fois
    une colonne date (« תאריך », « date ») et une colonne montant (« סכום », « montant », « amount ») ; le lien est
    l'hyperlien d'une cellule de la ligne, ou une adresse https:// écrite dans une cellule."""
    import datetime as dt
    import io
    import openpyxl
    from decimal import Decimal, InvalidOperation
    wb = openpyxl.load_workbook(io.BytesIO(contenu))
    lignes = []

    def colonne(e, mots):
        return next((k for k, t in enumerate(e) if t in mots), None)

    def valeur(r, k):
        return r[k].value if k is not None and k < len(r) else None

    for ws in wb.worksheets:
        rangees = list(ws.iter_rows())
        for i, r in enumerate(rangees[:6]):
            e = _entetes(c.value for c in r)
            col_date, col_somme = colonne(e, MOTS_DATE), colonne(e, MOTS_MONTANT)
            col_mvt, col_piece = colonne(e, MOTS_MVT), colonne(e, MOTS_PIECE)
            if (col_date is not None and col_somme is not None) or col_mvt is not None or col_piece is not None:
                break
        else:
            continue
        ignorees = {col_date, col_somme, col_mvt, col_piece} | {
            k for k, t in enumerate(e) if t in ("סטטוס", "status", "תאריך יצירה", "statut", "card name")}
        for r in rangees[i + 1:]:
            liens = [c.hyperlink.target for c in r if c.hyperlink and c.hyperlink.target]
            liens += [str(c.value).strip() for c in r if not c.hyperlink and str(c.value or "").strip().startswith("https://")
                      and str(c.value).strip() not in liens]              # adresse écrite en texte dans la cellule
            if not liens:
                continue
            date = valeur(r, col_date)
            if isinstance(date, dt.datetime):
                date = date.date()
            try:
                montant = abs(Decimal(str(valeur(r, col_somme))))
            except (InvalidOperation, TypeError):
                montant = None
            mvt, piece = _numero(valeur(r, col_mvt)), _numero(valeur(r, col_piece))
            if not (mvt or piece or (isinstance(date, dt.date) and montant is not None)):
                continue
            texte = [str(c.value).strip() for k, c in enumerate(r) if k not in ignorees and c.value not in (None, "")
                     and not c.hyperlink and not str(c.value).startswith("http")]
            for lien in liens:
                lignes.append({"date": date.isoformat() if isinstance(date, dt.date) else "",
                               "montant": str(montant) if montant is not None else "", "mvt": mvt, "piece": piece,
                               "lien": lien, "feuille": ws.title, "description": " · ".join(texte)[:150]})
    return lignes


def deposer_extrait(contenu):
    """Ajoute aux documents à classer les liens d'un extrait (ceux déjà joints ou déjà en attente sont ignorés)."""
    import uuid
    en_attente = lire_liens()
    connus = {l["lien"] for l in en_attente} | set(Justificatif.objects.exclude(lien="").values_list("lien", flat=True))
    nouveaux = [dict(l, id=uuid.uuid4().hex[:10]) for l in lire_extrait(contenu) if l["lien"] not in connus]
    vus, uniques = set(), []
    for l in nouveaux:
        if l["lien"] not in vus:
            vus.add(l["lien"])
            uniques.append(l)
    ecrire_liens(en_attente + uniques)
    return len(uniques)


def proposer_lien(l):
    """Mouvement d'après le n° de Mvt, le n° de pièce, ou la date et le montant de la ligne : (mouvement, raison, sûr)."""
    import datetime as dt
    from decimal import Decimal
    from django.db.models import Q
    from .models import Ligne, Mouvement
    if l.get("mvt"):
        mv = Mouvement.objects.filter(numero=l["mvt"]).first()
        return (mv, f"Mvt {l['mvt']}", True) if mv else (None, f"Mvt {l['mvt']} inexistant", False)
    if l.get("piece"):
        mvts = list(Mouvement.objects.filter(piece=l["piece"])[:2])
        if len(mvts) == 1:
            return mvts[0], f"pièce {l['piece']}", True
        return None, f"pièce {l['piece']} " + ("sur plusieurs mouvements" if mvts else "inexistante"), False
    if not (l.get("date") and l.get("montant")):
        return None, "ni Mvt, ni pièce, ni date et montant", False
    date, montant = dt.date.fromisoformat(l["date"]), Decimal(l["montant"])
    numeros = sorted(set(Ligne.objects.filter(mouvement__date=date).filter(Q(debit=montant) | Q(credit=montant))
                         .values_list("mouvement__numero", flat=True)))
    if len(numeros) == 1:
        return Mouvement.objects.get(numero=numeros[0]), f"date {date:%d/%m/%Y} et montant {montant}", True
    if numeros:
        return None, f"{len(numeros)} mouvements le {date:%d/%m/%Y} pour {montant} : Mvt " + ", ".join(map(str, numeros)), False
    return None, f"aucun mouvement le {date:%d/%m/%Y} pour {montant}", False


def a_classer():
    """Fichiers déposés et liens d'extraits en attente, avec la proposition de rattachement."""
    res = []
    for l in lire_liens():
        mv, raison, sur = proposer_lien(l)
        res.append({"nom": f"lien:{l['id']}", "affiche": l["description"] or l["lien"], "lien": l["lien"],
                    "date": l["date"], "montant_extrait": l["montant"], "feuille": l["feuille"], "taille": 0,
                    "mouvement": mv, "raison": raison, "sur": sur})
    for f in sorted(a_classer_dossier().iterdir(), key=lambda p: p.name.lower()):
        if f.is_file() and f.name != "liens.json":
            mv, raison, sur = proposer(re.sub(r"__doublon_[b-z]", "", f.name))
            en_tete = numeros_en_tete(re.sub(r"__doublon_[b-z]", "", f.name))
            res.append({"nom": f.name, "affiche": nom_affiche(f.name), "taille": f.stat().st_size, "mouvement": mv,
                        "raison": raison, "sur": sur,
                        "saisie": "+".join(map(str, en_tete)) if mv and len(en_tete) > 1 else ""})
    return res


def liste_a_classer():
    """[(nom, nom affiché)] des documents déposés et liens en attente, sans proposition (liste rapide)."""
    res = [(f"lien:{l['id']}", "🔗 " + (l["description"] or l["lien"])[:80]) for l in lire_liens()]
    res += sorted(((f.name, nom_affiche(f.name)) for f in a_classer_dossier().iterdir()
                   if f.is_file() and f.name != "liens.json"), key=lambda x: x[1].lower())
    return res


def fichier_a_classer(nom):
    f = a_classer_dossier() / nom
    if "/" in nom or "\\" in nom or nom.startswith(".") or nom == "liens.json" or not f.is_file():
        raise ValueError("Fichier introuvable.")
    return f


def nom_affiche(nom):
    """Nom du document sans les dossiers du ZIP ni le suffixe de doublon."""
    nom = re.sub(r"__doublon_[b-z](?=\.[^.]*$|$)", "", nom)          # « facture__doublon_b.pdf » → facture.pdf
    return nom.split("__")[-1]


def _lien_en_attente(nom):
    liens = lire_liens()
    l = next((x for x in liens if f"lien:{x['id']}" == nom), None)
    if not l:
        raise ValueError("Lien introuvable (déjà rattaché ou écarté ?).")
    return l, liens


def rattacher(nom, mouvement, description="", auteur=""):
    from django.core.files import File
    if nom.startswith("lien:"):
        l, liens = _lien_en_attente(nom)
        d = l.get("date") or ""
        j = ajouter_lien(mouvement, l["lien"], f"{l['feuille']} du {d[8:10]}/{d[5:7]}/{d[:4]}" if d else f"{l['feuille']} (lien)",
                         description or l["description"], auteur)
        ecrire_liens([x for x in liens if x is not l])
        return j
    f = fichier_a_classer(nom)
    with open(f, "rb") as flux:
        j = ajouter(mouvement, File(flux, name=nom_affiche(nom)), description, auteur)
    f.unlink()
    return j


def ecarter(nom):
    if nom.startswith("lien:"):
        l, liens = _lien_en_attente(nom)
        ecrire_liens([x for x in liens if x is not l])
        return
    fichier_a_classer(nom).unlink()
