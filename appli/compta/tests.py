"""Tests du socle : modèle, contrôles, droits d'accès, reprise d'un classeur.

    python manage.py test compta
"""

import datetime as dt
import tempfile
from decimal import Decimal
from pathlib import Path

import openpyxl
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.table import Table

from . import controles
from .models import CodeAnalytique, Compte, Exercice, Journal, Ligne, Mouvement, Prefixe, Reglage, soldes

D = Decimal


def referentiels():
    CodeAnalytique.objects.create(code="BIL.5", axe=1, libelle="TRESORERIE")
    CodeAnalytique.objects.create(code="COT.2", axe=1, libelle="COTISATIONS")
    CodeAnalytique.objects.create(code="BIL.4", axe=1, libelle="TIERS")
    CodeAnalytique.objects.create(code="GEN.002", axe=2, libelle="COTISATIONS")
    CodeAnalytique.objects.create(code="MAN.001", axe=2, libelle="RALLYE")
    CodeAnalytique.objects.create(code="MAN.007", axe=2, libelle="")
    Compte.objects.create(numero="512000", libelle="BANQUE", anal1_id="BIL.5")
    Compte.objects.create(numero="700000", libelle="COTISATIONS", anal1_id="COT.2")
    Compte.objects.create(numero="411TEST001", libelle="MEMBRE TEST", anal1_id="BIL.4")
    Journal.objects.create(code="B1", intitule="BANQUE 1", compte_id="512000")
    Exercice.objects.create(libelle="2025", debut=dt.date(2025, 10, 1), fin=dt.date(2025, 12, 31), clos=True)
    Exercice.objects.create(libelle="2026", debut=dt.date(2026, 1, 1), fin=dt.date(2026, 12, 31))


def mouvement(numero, date, lignes, origine="saisie"):
    m = Mouvement.objects.create(numero=numero, date=date, journal_id="B1", piece=numero, origine=origine)
    for i, (compte, d, c) in enumerate(lignes):
        Ligne.objects.create(mouvement=m, ordre=i, compte_id=compte, libelle="TEST", debit=D(d), credit=D(c), anal2_id="GEN.002")
    return m


class Modele(TestCase):
    def setUp(self):
        referentiels()

    def test_soldes_et_resultat(self):
        mouvement(1, dt.date(2026, 2, 1), [("411TEST001", 400, 0), ("700000", 0, 400), ("512000", 400, 0), ("411TEST001", 0, 400)])
        self.assertEqual(soldes(Ligne.objects.all())[:2], (D("800.00"), D("800.00")))
        self.assertEqual(soldes(Ligne.objects.filter(compte_id="512000"))[2], D("400.00"))
        self.assertEqual(soldes(Ligne.objects.filter(compte__numero__startswith="7"))[2], D("-400.00"))

    def test_debit_et_credit_refuses(self):
        m = mouvement(1, dt.date(2026, 2, 1), [])
        with self.assertRaises(IntegrityError):
            Ligne.objects.create(mouvement=m, compte_id="512000", libelle="X", debit=D(1), credit=D(1), anal2_id="GEN.002")

    def test_code_suivant(self):
        Prefixe.objects.create(prefixe="MAN.", axe=2)
        Prefixe.objects.create(prefixe="COT.", axe=1)
        Prefixe.objects.create(prefixe="PJT.", axe=2)
        self.assertEqual(Prefixe.objects.get(prefixe="MAN.").code_suivant(), "MAN.008")
        self.assertEqual(Prefixe.objects.get(prefixe="COT.").code_suivant(), "COT.3")
        self.assertEqual(Prefixe.objects.get(prefixe="PJT.").code_suivant(), "PJT.001")

    def test_numerotation(self):
        mouvement(41, dt.date(2026, 2, 1), [("512000", 1, 0), ("700000", 0, 1)])
        self.assertEqual((Mouvement.prochain_numero(), Mouvement.prochaine_piece()), (42, 42))


class Controles(TestCase):
    def setUp(self):
        referentiels()
        Reglage.objects.create(cle="compte_virement", valeur="512000")

    def statut(self, libelle):
        return next(r for r in controles.executer() if r.libelle.startswith(libelle)).statut

    def test_equilibre(self):
        mouvement(1, dt.date(2026, 2, 1), [("512000", 100, 0), ("700000", 0, 100)])
        self.assertEqual(self.statut("Mouvements déséquilibrés"), "OK")
        mouvement(2, dt.date(2026, 2, 2), [("512000", 100, 0), ("700000", 0, 90)])
        self.assertEqual(self.statut("Mouvements déséquilibrés"), "Anomalie")
        self.assertEqual(controles.etat_general()[0], "2 anomalie(s)")

    def test_periode_close(self):
        mouvement(1, dt.date(2025, 11, 1), [("512000", 100, 0), ("700000", 0, 100)], origine="import")
        self.assertEqual(self.statut("Écritures nouvelles dans un exercice clos"), "OK")
        mouvement(2, dt.date(2025, 11, 2), [("512000", 100, 0), ("700000", 0, 100)])
        self.assertEqual(self.statut("Écritures nouvelles dans un exercice clos"), "Anomalie")

    def test_compte_de_liaison(self):
        mouvement(1, dt.date(2026, 2, 1), [("512000", 100, 0), ("700000", 0, 100)])
        self.assertEqual(self.statut("Compte de virement interne"), "À vérifier")


class Droits(TestCase):
    def setUp(self):
        referentiels()
        call_command("migrate", verbosity=0)   # crée les rôles (post_migrate)

    def client_pour(self, role):
        u = User.objects.create_user(role, password="motdepasse-test")
        u.groups.add(Group.objects.get(name=role))
        self.client.force_login(u)

    def test_pages_bureau(self):
        mouvement(1, dt.date(2026, 2, 1), [("512000", 100, 0), ("700000", 0, 100)])
        self.client_pour("Bureau")
        for url in ("/", "/ecritures/", "/mouvement/1/", "/grand-livre/?compte=512000", "/balance/", "/analytique/",
                    "/controles/", "/modifications/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_benevole_refuse(self):
        self.client_pour("Bénévole")
        self.assertEqual(self.client.get("/").status_code, 403)

    def test_anonyme_redirige(self):
        self.assertEqual(self.client.get("/").status_code, 302)


class Reprise(TestCase):
    def classeur(self):
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        def table(nom, entetes, lignes):
            ws = wb.create_sheet(nom)
            ws.append(entetes)
            for l in lignes:
                ws.append(l)
            ws.add_table(Table(displayName=nom, ref=f"A1:{openpyxl.utils.get_column_letter(len(entetes))}{len(lignes) + 1}"))
            return ws

        table("T_Axe1", ["Code", "Libellé", "Actif"], [["BIL.5", "TRESORERIE", 1], ["COT.2", "COTIS", 1]])
        table("T_Axe2", ["Code", "Libellé", "Actif"], [["GEN.002", "COTISATIONS", 1]])
        table("T_Prefixes", ["Préfixe", "Axe", "Libellé", "Code suivant"], [["GEN.", 2, "General", "GEN.003"]])
        table("T_PlanComptable", ["Compte", "Libellé compte", "Axe 1 (Anal1)", "Lettrable"],
              [["512000", "BANQUE", "BIL.5", ""], ["700000", "COTISATIONS", "COT.2", ""]])
        table("T_Journaux", ["Code", "Intitulé", "Type", "N° de compte", "Actif"], [["B1", "BANQUE 1", "BQ", 512000, 1]])
        e = ["Date", "Jnl", "Mvt", "Pièce", "Compte", "Libellé", "Débit", "Crédit", "Anal2", "Let"]
        table("T_Ecritures", e, [[dt.datetime(2026, 2, 1), "B1", 1, 1, "512000", "COT", 50.5, 0, "GEN.002", None],
                                 [dt.datetime(2026, 2, 1), "B1", 1, 1, "700000", "COT", 0, 50.5, "GEN.002", None],
                                 [dt.datetime(2025, 11, 1), "B1", 2, 2, "512000", "COT", 10, 0, "GEN.002", None],
                                 [dt.datetime(2025, 11, 1), "B1", 2, 2, "700000", "COT", 0, 10, "GEN.002", None]])
        p = wb.create_sheet("Paramètres")
        for r, (n, v) in enumerate((("P_DebutExercice", dt.datetime(2026, 1, 1)), ("P_FinExercice", dt.datetime(2026, 12, 31)),
                                    ("P_DateCloture", dt.datetime(2025, 12, 31)), ("P_CompteVirement", "580000")), start=1):
            p.cell(r, 2, v)
            wb.defined_names[n] = DefinedName(n, attr_text=f"Paramètres!$B${r}")
        chemin = Path(tempfile.mkdtemp()) / "test.xlsx"
        wb.save(chemin)
        return chemin

    def test_reprise(self):
        call_command("importer_classeur", str(self.classeur()), stdout=open("/dev/null", "w"))
        self.assertEqual(Mouvement.objects.count(), 2)
        self.assertEqual(soldes(Ligne.objects.all())[:2], (D("60.50"), D("60.50")))
        self.assertEqual(Journal.objects.get(code="B1").compte_id, "512000")
        self.assertEqual(list(Exercice.objects.values_list("clos", flat=True)), [True, False])
        self.assertEqual(Reglage.lire("compte_virement"), "580000")
        self.assertEqual(controles.etat_general()[0], "OK")
