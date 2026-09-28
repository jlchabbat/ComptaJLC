from django.db import migrations

DOSSIERS = {
    "dossier_exports": (r"D:\OneDrive\Applications\ComptaBB\Exports", "Dossier où l'application écrit ses exports"),
    "dossier_sauvegardes": (r"D:\OneDrive\Applications\ComptaBB\Exports\Sauvegardes",
                            "Dossier des sauvegardes de la base (copies .sqlite3)"),
}


def dossiers_pc(apps, schema_editor):
    """Dossiers du PC de l'association ; ignorés sur le site (chemin Windows), où les dossiers par défaut servent."""
    Reglage = apps.get_model("compta", "Reglage")
    for cle, (valeur, description) in DOSSIERS.items():
        r = Reglage.objects.filter(cle=cle).first()
        if r is None or not r.valeur.strip():
            Reglage.objects.update_or_create(cle=cle, defaults={"valeur": valeur, "description": description})


class Migration(migrations.Migration):

    dependencies = [("compta", "0011_role_administrateur")]

    operations = [migrations.RunPython(dossiers_pc, migrations.RunPython.noop)]
