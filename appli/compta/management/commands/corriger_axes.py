"""Corrige les anomalies résiduelles des règles d'axes (voir Contrôles, RG-02) ; sans --appliquer, ne fait que les lister.

    python manage.py corriger_axes [--appliquer]

- écriture dont l'axe 2 est un code d'axe 1, ou sur un compte de bilan : code axe 2 retiré ;
- compte sans code d'axe 1 : code repris d'un compte voisin (même début de numéro : 3, puis 2, puis 1 chiffres),
  sinon laissé à renseigner (Saisie › Plan comptable) ;
- compte de projet dont une écriture n'a pas de code axe 2 : signalé seulement (le code dépend de l'opération).
Chaque correction est inscrite dans l'Historique."""

from django.core.management.base import BaseCommand
from django.db import transaction

from compta.models import Compte, Ligne, Modification


class Command(BaseCommand):
    help = "Corrige les écritures et comptes qui ne respectent pas les règles d'axes (aperçu sans --appliquer)."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true", help="Enregistrer les corrections (sinon : aperçu).")

    @transaction.atomic
    def handle(self, *args, appliquer=False, **o):
        e = self.stdout.write
        mauvais = Ligne.objects.filter(anal2__isnull=False).exclude(anal2__axe=2)
        bilan = (Ligne.objects.filter(anal2__isnull=False).exclude(compte__numero__startswith="6")
                 .exclude(compte__numero__startswith="7"))
        e(f"Écritures avec un code d'axe 1 en axe 2 : {mauvais.count()} ; code axe 2 sur un compte de bilan : {bilan.count()}")
        corrigees = 0
        if appliquer:
            corrigees = mauvais.update(anal2=None) + bilan.exclude(pk__in=mauvais.values("pk")).update(anal2=None)
        sans1 = list(Compte.objects.filter(anal1__isnull=True).order_by("numero"))
        reste = []
        for c in sans1:
            voisin = next((v for n in (3, 2, 1) for v in [Compte.objects.filter(numero__startswith=c.numero[:n], anal1__isnull=False)
                                                           .exclude(numero=c.numero).first()] if v), None)
            if voisin:
                e(f"  compte {c.numero} {c.libelle} : axe 1 {voisin.anal1_id} (repris de {voisin.numero})")
                if appliquer:
                    c.anal1 = voisin.anal1
                    c.save(update_fields=["anal1"])
                    corrigees += 1
            else:
                reste.append(c.numero)
        if reste:
            e("  à renseigner à la main (Plan comptable) : " + ", ".join(reste))
        projet = Ligne.objects.filter(compte__projet=True, anal2__isnull=True).values_list("mouvement__numero", flat=True)
        if projet:
            e("Écritures d'un compte de projet sans code axe 2 (à compléter par « Modifier une écriture ») : Mvt "
              + ", ".join(str(n) for n in sorted(set(projet))))
        if appliquer and corrigees:
            Modification.objects.create(auteur="corriger_axes", lot="Contrôles", action="Correction des axes",
                                        objet=f"{corrigees} correction(s)", apres="codes axe 2 invalides retirés ; axe 1 des comptes complété")
            e(f"{corrigees} correction(s) enregistrée(s).")
        elif appliquer:
            e("Rien à corriger.")
        else:
            e("Aperçu seulement : relancer avec --appliquer pour enregistrer.")
