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
    return dossier() / j.chemin


def type_mime(j):
    return mimetypes.guess_type(j.nom)[0] or "application/octet-stream"


def _nom_sur(nom):
    nom = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    nom = re.sub(r"[^A-Za-z0-9._-]+", "_", nom).strip("._") or "document"
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
    if fichier.exists():
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


def proposer(nom):
    """Mouvement proposé d'après le nom du fichier : (mouvement ou None, raison, sûr)."""
    import datetime as dt
    from django.db.models import Q
    from .models import Ligne, Mouvement
    base = nom.rsplit(".", 1)[0]
    m = re.search(r"(?i)(?:^|[^a-z])mvt[\s_.\-n°o]*(\d{1,6})", base)
    if m:
        mv = Mouvement.objects.filter(numero=int(m.group(1))).first()
        return (mv, f"« Mvt {m.group(1)} » dans le nom", True) if mv else (None, f"Mvt {m.group(1)} inconnu", False)
    m = re.search(r"(?i)(?:^|[^a-z])(?:piece|pce|pc|pj)[\s_.\-n°o]*(\d{1,6})", base)
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
                return qs.first(), f"date {date:%d/%m/%Y} et montant {montant} dans le nom", True
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
            return piece, f"{n} = n° de pièce", True
        if mvt:
            return mvt, f"{n} = n° de Mvt (à vérifier)", False
    return None, indice or "aucun numéro, date ou montant reconnu", False


def a_classer():
    """Fichiers déposés en attente, avec la proposition de rattachement."""
    res = []
    for f in sorted(a_classer_dossier().iterdir(), key=lambda p: p.name.lower()):
        if f.is_file():
            mv, raison, sur = proposer(re.sub(r"__doublon_[b-z]", "", f.name))
            res.append({"nom": f.name, "affiche": nom_affiche(f.name), "taille": f.stat().st_size, "mouvement": mv,
                        "raison": raison, "sur": sur})
    return res


def fichier_a_classer(nom):
    f = a_classer_dossier() / nom
    if "/" in nom or "\\" in nom or nom.startswith(".") or not f.is_file():
        raise ValueError("Fichier introuvable.")
    return f


def nom_affiche(nom):
    """Nom du document sans les dossiers du ZIP ni le suffixe de doublon."""
    nom = re.sub(r"__doublon_[b-z](?=\.[^.]*$|$)", "", nom)          # « facture__doublon_b.pdf » → facture.pdf
    return nom.split("__")[-1]


def rattacher(nom, mouvement, description="", auteur=""):
    from django.core.files import File
    f = fichier_a_classer(nom)
    with open(f, "rb") as flux:
        j = ajouter(mouvement, File(flux, name=nom_affiche(nom)), description, auteur)
    f.unlink()
    return j


def ecarter(nom):
    fichier_a_classer(nom).unlink()
