from django.db import migrations

NOUVEAUX = {"Administrateur": "Administration", "Trésorier": "Gestion", "Bureau": "Consultation"}


def renommer(apps, schema_editor):
    """Trois profils : Administration, Gestion, Consultation (les utilisateurs gardent leur rôle) ; Bénévole inchangé."""
    Group = apps.get_model("auth", "Group")
    for ancien, nouveau in NOUVEAUX.items():
        if Group.objects.filter(name=ancien).exists() and not Group.objects.filter(name=nouveau).exists():
            Group.objects.filter(name=ancien).update(name=nouveau)


class Migration(migrations.Migration):
    dependencies = [("compta", "0025_lettrage_trois_lettres"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(renommer, migrations.RunPython.noop)]
