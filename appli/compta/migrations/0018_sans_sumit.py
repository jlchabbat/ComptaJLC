# L'ancien logiciel n'est plus mentionné : réglage « hébergeur des liens » vidé, documents renommés.

from django.db import migrations


def nettoyer(apps, schema_editor):
    Reglage, Justificatif = apps.get_model("compta", "Reglage"), apps.get_model("compta", "Justificatif")
    Reglage.objects.filter(cle="hebergeur_liens", valeur__iexact="SUMIT").delete()          # absent = pas de lien
    Reglage.objects.filter(cle="hebergeur_liens").update(description="Site qui héberge des justificatifs gardés en lien (nom du site) ; vide : pas de lien")
    Justificatif.objects.filter(nom="Document SUMIT").update(nom="Document en ligne")


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0017_reglage_valeur_longue"),
    ]

    operations = [migrations.RunPython(nettoyer, migrations.RunPython.noop)]
