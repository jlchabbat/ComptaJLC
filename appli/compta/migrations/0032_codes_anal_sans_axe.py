import django.db.models.deletion
from django.db import migrations, models


def supprimer_axe2(apps, schema_editor):
    """Un seul axe : les codes et préfixes d'axe 2 disparaissent (leurs références ont été retirées en 0031)."""
    schema_editor.execute("DELETE FROM compta_codeanalytique WHERE axe = 2")      # SQL direct : pas de cascade ORM
    schema_editor.execute("DELETE FROM compta_prefixe WHERE axe = 2")


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0031_un_seul_axe_anal"),
    ]

    operations = [
        migrations.RunPython(supprimer_axe2, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name="budget",
            options={"ordering": ["exercice", "nature", "compte", "anal1"]},
        ),
        migrations.AlterModelOptions(
            name="codeanalytique",
            options={
                "ordering": ["code"],
                "verbose_name": "code analytique",
                "verbose_name_plural": "codes analytiques",
            },
        ),
        migrations.AlterModelOptions(
            name="prefixe",
            options={"ordering": ["prefixe"], "verbose_name": "préfixe"},
        ),
        migrations.RemoveField(
            model_name="codeanalytique",
            name="axe",
        ),
        migrations.RemoveField(
            model_name="codeanalytique",
            name="statut",
        ),
        migrations.RemoveField(
            model_name="compte",
            name="projet",
        ),
        migrations.RemoveField(
            model_name="prefixe",
            name="axe",
        ),
        migrations.AlterField(
            model_name="budget",
            name="anal1",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="compta.codeanalytique",
                verbose_name="Anal",
            ),
        ),
        migrations.AlterField(
            model_name="compte",
            name="anal1",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="comptes",
                to="compta.codeanalytique",
                verbose_name="Anal",
            ),
        ),
        migrations.AddConstraint(
            model_name="budget",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("anal1__isnull", True), ("compte__isnull", False)),
                    models.Q(("anal1__isnull", False), ("compte__isnull", True)),
                    _connector="OR",
                ),
                name="budget_une_cible",
            ),
        ),
    ]
