# Abandon du programme du PC : les chemins Windows (D:\…) des dossiers n'ont plus d'usage.

from django.db import migrations


def effacer_chemins_pc(apps, schema_editor):
    Reglage = apps.get_model("compta", "Reglage")
    for r in Reglage.objects.filter(cle__in=["dossier_imports", "dossier_exports", "dossier_sauvegardes"]):
        v = (r.valeur or "").strip()
        if len(v) > 1 and (v[1] == ":" or v.startswith("\\\\")):
            r.delete()                                      # absent = dossier par défaut du site


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0014_documents_fiches"),
    ]

    operations = [
        migrations.RunPython(effacer_chemins_pc, migrations.RunPython.noop),
    ]
