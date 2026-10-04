from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0028_ligne_axe2_facultatif"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tiersprovisoire",
            name="remarque",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="tiersprovisoire",
            name="telephone",
            field=models.CharField(blank=True, max_length=40, verbose_name="téléphone"),
        ),
        migrations.AddField(
            model_name="tiersprovisoire",
            name="email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="e-mail"),
        ),
    ]
