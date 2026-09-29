"""Cours de change de la BCE (même source que l'application Banque : app/sources/bce.py).

La BCE publie chaque jour ouvré la série EUR/devise (unités de devise pour 1 €). Les cotations sont gardées dans
TauxChange ; seuls les jours manquants sont redemandés. Un jour sans cotation (week-end, jour férié) prend la dernière
cotation connue. La BCE injoignable n'est pas une erreur : on travaille sur les cotations déjà gardées."""

import csv
import datetime as dt
import io
import urllib.error
import urllib.request
from decimal import Decimal

from .models import Journal, TauxChange

URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.{devises}.EUR.SP00.A?startPeriod={depuis}&format=csvdata"
DELAI = 10


def devises_suivies():
    """Devises des journaux du site (ILS, USD…)."""
    return sorted({d for d in Journal.objects.exclude(devise="").values_list("devise", flat=True) if d != "EUR"})


def telecharger(devises, depuis):
    url = URL.format(devises="+".join(devises), depuis=depuis.isoformat())
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ComptaBB"}), timeout=DELAI) as r:
        brut = r.read().decode("utf-8")
    res = []
    for l in csv.DictReader(io.StringIO(brut)):
        v, p = (l.get("OBS_VALUE") or "").strip(), (l.get("TIME_PERIOD") or "").strip()
        if v and p:
            try:
                res.append((dt.date.fromisoformat(p), l["CURRENCY"], Decimal(v)))
            except (ValueError, KeyError, ArithmeticError):
                continue
    return res


def actualiser(depuis=None):
    """Ajoute les cotations manquantes ; renvoie un message d'état (jamais d'exception)."""
    devises = devises_suivies()
    if not devises:
        return "aucun journal en devise"
    dernier = TauxChange.objects.order_by("-jour").values_list("jour", flat=True).first()
    connues = set(TauxChange.objects.values_list("devise", flat=True).distinct())
    if dernier and set(devises) <= connues:
        depuis = max(depuis or dernier, dernier) if depuis and depuis > dernier else dernier + dt.timedelta(days=1)
    else:
        depuis = depuis or dt.date(dt.date.today().year - 1, 1, 1)
    if depuis > dt.date.today():
        return f"cours BCE à jour ({dernier:%d/%m/%Y})"
    try:
        cotations = telecharger(devises, depuis)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
        return f"BCE injoignable ({getattr(e, 'reason', e)}) : cours déjà gardés" + (f" jusqu'au {dernier:%d/%m/%Y}" if dernier else "")
    ajouts = 0
    for jour, devise, valeur in cotations:
        _, cree = TauxChange.objects.update_or_create(jour=jour, devise=devise, defaults={"taux": valeur})
        ajouts += cree
    dernier = TauxChange.objects.order_by("-jour").values_list("jour", flat=True).first()
    return f"cours BCE au {dernier:%d/%m/%Y}" + (f", {ajouts} cotation(s) ajoutée(s)" if ajouts else "") if dernier else \
        "la BCE n'a rien renvoyé"


def taux(devise, jour, actualiser_si_besoin=True):
    """Unités de devise pour 1 € au jour donné (dernière cotation connue à cette date) ; None si inconnu."""
    t = TauxChange.objects.filter(devise=devise, jour__lte=jour).order_by("-jour").values_list("taux", flat=True).first()
    if t is None or (actualiser_si_besoin and not TauxChange.objects.filter(devise=devise, jour__gte=jour).exists()
                     and jour <= dt.date.today()):
        if actualiser_si_besoin:
            actualiser(depuis=jour - dt.timedelta(days=10))
            return taux(devise, jour, actualiser_si_besoin=False)
    return t
