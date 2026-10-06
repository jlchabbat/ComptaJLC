import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Plus de fiches bénévoles ni de tiers provisoires ; « Membre » devient « Tiers » (sans adhésion, statut ni cotisation)."""

    dependencies = [
        ("compta", "0032_codes_anal_sans_axe"),
    ]

    operations = [
        migrations.DeleteModel(name="DocumentFiche"),
        migrations.DeleteModel(name="LigneFiche"),
        migrations.DeleteModel(name="Fiche"),
        migrations.DeleteModel(name="TiersProvisoire"),
        migrations.DeleteModel(name="NatureFiche"),
        migrations.DeleteModel(name="ModeFiche"),
        migrations.RemoveField(model_name="membre", name="utilisateur"),
        migrations.RemoveField(model_name="membre", name="date_adhesion"),
        migrations.RemoveField(model_name="membre", name="statut"),
        migrations.RemoveField(model_name="membre", name="cotisation"),
        migrations.RenameModel(old_name="Membre", new_name="Tiers"),
        migrations.AlterField(
            model_name="tiers",
            name="compte",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                primary_key=True,
                related_name="tiers",
                serialize=False,
                to="compta.compte",
            ),
        ),
        migrations.AlterField(
            model_name="mouvement",
            name="origine",
            field=models.CharField(
                choices=[
                    ("import", "Reprise"),
                    ("saisie", "Saisie"),
                    ("correction", "Correction"),
                    ("cloture", "À-nouveaux de clôture"),
                ],
                default="saisie",
                max_length=12,
            ),
        ),
    ]
