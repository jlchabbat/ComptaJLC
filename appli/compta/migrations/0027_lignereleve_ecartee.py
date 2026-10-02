from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("compta", "0026_profils_utilisateurs")]

    operations = [
        migrations.AddField(
            model_name="lignereleve",
            name="ecartee",
            field=models.BooleanField(default=False, help_text="Ligne volontairement laissée sans écriture ni lien.",
                                      verbose_name="écartée"),
        ),
    ]
