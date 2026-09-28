# Un site par association (étape 1) : réglages propres à l'association. Un site qui a déjà des écritures ou des
# journaux (celui de la Loge) reçoit ses valeurs actuelles ; une base neuve reçoit les valeurs neutres.

from django.db import migrations, models

# clé, description, valeur neutre, valeur des sites existants
REGLAGES = [
    ("nom_association", "Nom de l'association (en-tête des pages, situation, éditions)", "", "Loge Bnei Brith"),
    ("devise", "Symbole de la devise des montants (₪, €, $…)", "€", "₪"),
    ("releves_mizrahi", "Journaux dont le relevé PDF est au format Mizrahi-Tefahot (hébreu), séparés par des virgules ; "
                        "vide : relevés en Excel ou CSV seulement", "", "B1,B2"),
    ("releve_bit", "Journal du relevé Bit (format imposé, remplace le précédent) ; vide : pas de Bit", "", "B3"),
    ("carte_bancaire", "Nom de la carte de paiement réglée par la banque le mois suivant (passe par le compte de "
                       "virement interne) ; vide : pas de carte", "", "Isracard"),
    ("hebergeur_liens", "Site qui héberge des justificatifs gardés en lien (ex. SUMIT) ; vide : pas de lien", "", "SUMIT"),
    ("traductions_releve", "Traduire les libellés du relevé (hébreu → français) : oui ou non", "non", "oui"),
]


def creer(apps, schema_editor):
    Reglage, Journal, Mouvement = (apps.get_model("compta", m) for m in ("Reglage", "Journal", "Mouvement"))
    existant = Mouvement.objects.exists() or Journal.objects.exists()
    ancien = Reglage.objects.filter(cle="association").first()
    for cle, description, neutre, loge in REGLAGES:
        valeur = loge if existant else neutre
        if cle == "nom_association" and ancien and ancien.valeur:
            valeur = ancien.valeur
        if valeur and valeur != neutre:             # absent = valeur neutre (Paramètres.xlsx les montre toutes)
            Reglage.objects.get_or_create(cle=cle, defaults={"valeur": valeur, "description": description})


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0015_sans_programme_pc"),
    ]

    operations = [
        migrations.AlterField(model_name="reglage", name="valeur", field=models.CharField(blank=True, max_length=200)),
        migrations.RunPython(creer, migrations.RunPython.noop),
    ]
