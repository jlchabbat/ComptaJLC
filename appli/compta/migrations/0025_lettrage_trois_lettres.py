import re

from django.db import migrations


def trois_lettres(apps, schema_editor):
    """Codes de lettrage d'origine (A, B… AA…) : recodés AAA, AAB… compte par compte, dans l'ordre des anciens codes."""
    Ligne = apps.get_model("compta", "Ligne")
    for numero in Ligne.objects.exclude(lettrage="").values_list("compte_id", flat=True).distinct():
        codes = sorted(set(Ligne.objects.filter(compte_id=numero).exclude(lettrage="").values_list("lettrage", flat=True)),
                       key=lambda c: (len(c), c))
        anciens = [c for c in codes if not re.fullmatch(r"[A-Z]{3}", c)]
        if not anciens:
            continue
        pris = {c for c in codes if re.fullmatch(r"[A-Z]{3}", c)}
        libres = ("".join(chr(65 + n // 26 ** i % 26) for i in (2, 1, 0)) for n in range(26 ** 3))
        for ancien in anciens:
            nouveau = next(c for c in libres if c not in pris)
            pris.add(nouveau)
            Ligne.objects.filter(compte_id=numero, lettrage=ancien).update(lettrage=nouveau)


class Migration(migrations.Migration):
    dependencies = [("compta", "0024_historique_imports_releves")]
    operations = [migrations.RunPython(trois_lettres, migrations.RunPython.noop)]
