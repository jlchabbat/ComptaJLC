# Fusion des branches : justificatifs (0010-0011) et rôles / dossiers (0010-0012).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0011_justificatifs_liens"),
        ("compta", "0012_dossiers_pc"),
    ]

    operations = []
