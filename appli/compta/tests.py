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


# ---------------------------------------------------------------- W1 : saisie guidée (scénarios de la recette Excel du Lot 1)

from . import saisie as moteur  # noqa: E402
from .models import ModeleOperation, MoyenPaiement  # noqa: E402


def referentiels_saisie():
    for code, lib in (("BIL.5", "TRESORERIE"), ("BIL.4", "TIERS"), ("COT.2", "COTISATIONS"), ("FON.1", "FONCTIONNEMENT")):
        CodeAnalytique.objects.create(code=code, axe=1, libelle=lib)
    for code, lib in (("GEN.001", "GENERAL"), ("GEN.002", "COTISATIONS"), ("GEN.004", "BANQUE"), ("MAN.001", "RALLYE"),
                      ("SOC.006", "BOURSES")):
        CodeAnalytique.objects.create(code=code, axe=2, libelle=lib)
    comptes = [("512000", "MIZRAHI", "BIL.5"), ("512100", "MIZRAHI EPARGNE", "BIL.5"), ("512200", "BIT", "BIL.5"),
               ("530000", "CAISSE", "BIL.5"), ("580000", "VIREMENTS INTERNES", "BIL.5"), ("411TAIEB001", "TAIEB JEANNE", "BIL.4"),
               ("401000", "FOURNIS DIVERS", "BIL.4"), ("600000", "ACHATS", "FON.1"), ("600100", "FRAIS BANCAIRES", "FON.1"),
               ("610000", "SERVICES", "FON.1")]
    comptes += [(n, "PRODUIT", "COT.2") for n in ("700000", "710000", "720000", "725000", "740000", "750000")]
    for n, lib, a1 in comptes:
        Compte.objects.create(numero=n, libelle=lib, anal1_id=a1)
    for code, compte in (("B1", "512000"), ("B2", "512100"), ("B3", "512200"), ("CA", "530000"), ("VT", None), ("HA", None), ("OD", None)):
        Journal.objects.create(code=code, intitule=code, compte_id=compte)
    Exercice.objects.create(libelle="court", debut=dt.date(2025, 10, 25), fin=dt.date(2025, 12, 31), clos=True)
    Exercice.objects.create(libelle="2026", debut=dt.date(2026, 1, 1), fin=dt.date(2026, 12, 31))
    Reglage.objects.create(cle="compte_virement", valeur="580000")
    moteur.initialiser_parametres()
    m = Mouvement.objects.create(numero=421, date=dt.date(2026, 9, 24), journal_id="B1", piece=421, origine="import")
    Ligne.objects.create(mouvement=m, ordre=0, compte_id="411TAIEB001", libelle="FACTURE 40013 - TAIEB JEANNE", debit=D(400),
                         anal2_id="MAN.001")
    Ligne.objects.create(mouvement=m, ordre=1, compte_id="710000", libelle="FACTURE 40013 - TAIEB JEANNE", credit=D(400),
                         anal2_id="MAN.001")


def operation(date=dt.date(2026, 10, 15), modele=None, tiers=None, montant=400, paiement=None, vers=None, anal2=None, compte=None,
              remboursement=False, libelle=""):
    mp = lambda lib: MoyenPaiement.objects.get(libelle=lib) if lib else None  # noqa: E731
    return moteur.Operation(date=date, modele=ModeleOperation.objects.get(type=modele) if modele else None,
                            tiers=Compte.objects.get(numero=tiers) if tiers else None, montant=D(montant), paiement=mp(paiement),
                            vers=mp(vers), anal2=CodeAnalytique.objects.get(code=anal2) if anal2 else None,
                            compte=Compte.objects.get(numero=compte) if compte else None, remboursement=remboursement,
                            libelle=libelle)


SCENARIOS = {
    "cotisation_reglee": (dict(modele="Cotisation membre", tiers="411TAIEB001", paiement="BIT", anal2="GEN.002"),
                          [("B3", 1, "411TAIEB001", 400, 0), ("B3", 1, "700000", 0, 400), ("B3", 1, "512200", 400, 0),
                           ("B3", 1, "411TAIEB001", 0, 400)], set()),
    "cotisation_non_reglee": (dict(modele="Cotisation membre", tiers="411TAIEB001", paiement="Non réglé", anal2="GEN.002"),
                              [("VT", 1, "411TAIEB001", 400, 0), ("VT", 1, "700000", 0, 400)], set()),
    "frais_bancaires": (dict(modele="Frais bancaires", montant=25, paiement="Mizrahi compte courant", anal2="GEN.004"),
                        [("B1", 1, "600100", 25, 0), ("B1", 1, "512000", 0, 25)], set()),
    "virement_interne": (dict(modele="Virement interne", montant=1000, paiement="Mizrahi compte courant", vers="BIT", anal2="GEN.001"),
                         [("B1", 1, "580000", 1000, 0), ("B1", 1, "512000", 0, 1000), ("B3", 2, "512200", 1000, 0),
                          ("B3", 2, "580000", 0, 1000)], set()),
    "isracard": (dict(modele="Paiement carte Isracard", montant=500, paiement="Mizrahi compte courant", anal2="GEN.004"),
                 [("OD", 1, "600000", 500, 0), ("OD", 1, "580000", 0, 500), ("B1", 2, "580000", 500, 0),
                  ("B1", 2, "512000", 0, 500)], set()),
    "remboursement": (dict(modele="Cotisation membre", tiers="411TAIEB001", paiement="BIT", anal2="GEN.002", remboursement=True),
                      [("B3", 1, "411TAIEB001", 0, 400), ("B3", 1, "700000", 400, 0), ("B3", 1, "512200", 0, 400),
                       ("B3", 1, "411TAIEB001", 400, 0)], set()),
    "facture_fournisseur_caisse": (dict(modele="Facture fournisseur", tiers="401000", paiement="Caisse (espèces)", anal2="MAN.001",
                                        compte="610000"),
                                   [("CA", 1, "610000", 400, 0), ("CA", 1, "401000", 0, 400), ("CA", 1, "401000", 400, 0),
                                    ("CA", 1, "530000", 0, 400)], set()),
    "fournisseur_sans_compte": (dict(modele="Facture fournisseur", tiers="401000", paiement="Caisse (espèces)", anal2="MAN.001"),
                                None, {"Compte"}),
    "date_close_et_mauvais_tiers": (dict(date=dt.date(2025, 12, 15), modele="Cotisation membre", tiers="401000", paiement="BIT",
                                         anal2="GEN.002"), None, {"Date", "Tiers"}),
    "depense_classe_7": (dict(modele="Dépense directe", paiement="BIT", anal2="GEN.001", compte="700000"), None, {"Compte"}),
    "paiement_manquant": (dict(modele="Frais bancaires", anal2="GEN.004"), None, {"Moyen de paiement"}),
    "virement_meme_compte": (dict(modele="Virement interne", paiement="BIT", vers="BIT", anal2="GEN.001"), None, {"Virement"}),
    "deja_enregistree": (dict(date=dt.date(2026, 9, 24), modele="Facture manifestation (membre)", tiers="411TAIEB001",
                              paiement="Mizrahi compte courant", anal2="MAN.001", libelle="FACTURE 40013 - TAIEB JEANNE"),
                         None, {"Déjà enregistrée ?"}),
}


class Saisie(TestCase):
    def setUp(self):
        referentiels_saisie()

    def test_scenarios(self):
        for nom, (entrees, attendu, erreurs) in SCENARIOS.items():
            with self.subTest(nom):
                r = moteur.controler(operation(**entrees))
                self.assertEqual(set(r.erreurs), erreurs, r.erreurs)
                if attendu:
                    obtenu = [(l.journal.code, l.mvt, l.compte.numero, l.debit, l.credit) for l in r.lignes]
                    self.assertEqual(obtenu, [(j, m, c, D(d), D(cr)) for j, m, c, d, cr in attendu])

    def test_enregistrer(self):
        u = User.objects.create_user("t")
        crees = moteur.enregistrer(operation(**SCENARIOS["virement_interne"][0]), u)
        self.assertEqual([(m.numero, m.piece, m.journal_id) for m in crees], [(422, 422, "B1"), (423, 423, "B3")])
        self.assertEqual(soldes(Ligne.objects.filter(mouvement__numero__gte=422))[:2], (D(2000), D(2000)))
        self.assertEqual(Ligne.objects.filter(mouvement__numero=422).first().libelle, "VIREMENT INTERNE")
        with self.assertRaises(ValueError):   # même opération : doublon
            moteur.enregistrer(operation(**SCENARIOS["virement_interne"][0]), u)
        self.assertEqual(len(moteur.enregistrer(operation(**SCENARIOS["virement_interne"][0]), u, forcer_doublon=True)), 2)

    def test_initialiser_idempotent(self):
        n = ModeleOperation.objects.count()
        moteur.initialiser_parametres()
        self.assertEqual((n, ModeleOperation.objects.count()), (14, 14))


class Ecrans(TestCase):
    def setUp(self):
        referentiels_saisie()
        call_command("migrate", verbosity=0)
        self.u = User.objects.create_user("tresorier", password="x")
        self.u.groups.add(Group.objects.get(name="Trésorier"))
        self.client.force_login(self.u)

    def formulaire(self, **k):
        e = SCENARIOS["cotisation_reglee"][0]
        data = {"date": "2026-10-15", "modele": ModeleOperation.objects.get(type=e["modele"]).pk, "tiers": e["tiers"], "montant": "400",
                "paiement": MoyenPaiement.objects.get(libelle=e["paiement"]).pk, "anal2": e["anal2"]}
        data.update(k)
        return data

    def test_pages_et_listes_cherchables(self):
        for url in ("/saisie/", "/codes/", "/ecritures/", "/grand-livre/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertContains(r, "data-cherchable", msg_prefix=url)
            self.assertContains(r, "compta/liste.js", msg_prefix=url)
        self.assertContains(self.client.get("/saisie/"), "411TAIEB001 – TAIEB JEANNE")
        self.assertContains(self.client.get("/codes/"), "SOC.006 – BOURSES")

    def test_apercu_puis_enregistrement(self):
        r = self.client.post("/saisie/", self.formulaire(apercu="1"))
        self.assertContains(r, "Tous les contrôles sont OK")
        self.assertFalse(Mouvement.objects.filter(numero=422).exists())
        r = self.client.post("/saisie/", self.formulaire(enregistrer="1"))
        self.assertRedirects(r, "/mouvement/422/")
        self.assertEqual(Mouvement.objects.get(numero=422).cree_par, self.u)
        r = self.client.post("/saisie/", self.formulaire(enregistrer="1"))
        self.assertContains(r, "Déjà enregistrée ?")
        self.assertRedirects(self.client.post("/saisie/", self.formulaire(enregistrer="1", forcer="on")), "/mouvement/423/")

    def test_saisie_refusee_au_bureau(self):
        b = User.objects.create_user("bureau")
        b.groups.add(Group.objects.get(name="Bureau"))
        self.client.force_login(b)
        self.assertEqual(self.client.get("/saisie/").status_code, 403)
        self.assertEqual(self.client.get("/codes/").status_code, 403)

    def test_codes(self):
        Prefixe.objects.create(prefixe="SOC.", axe=2, libelle="Social")
        r = self.client.post("/codes/", {"code-prefixe": "SOC.", "code-libelle": "aide aux familles", "code-statut": "1",
                                         "creer_code": "1"})
        self.assertRedirects(r, "/codes/")
        self.assertEqual(CodeAnalytique.objects.get(code="SOC.007").libelle, "AIDE AUX FAMILLES")
        self.client.post("/codes/", {"membre-nom": "Taïeb", "membre-prenom": "Paul", "creer_membre": "1"})
        self.assertTrue(Compte.objects.filter(numero="411TAIEB002", libelle="TAÏEB PAUL").exists())
        r = self.client.post("/codes/", {"statut-code": "MAN.001", "statut-statut": "2", "changer_statut": "1"})
        self.assertContains(r, "cocher la confirmation")
        self.client.post("/codes/", {"statut-code": "MAN.001", "statut-statut": "2", "statut-confirmation": "on", "changer_statut": "1"})
        self.assertEqual(CodeAnalytique.objects.get(code="MAN.001").statut, 2)
