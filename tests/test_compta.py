import unittest

from comptajlc import create_app
from comptajlc.models import CodeAxe1, CodeAxe2, Compte, Ecriture, Ligne, db
from comptajlc.vues import en_centimes, fmt_montant


class Base(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})
        self.c = self.app.test_client()
        self.connecter(self.c)
        with self.app.app_context():
            db.session.add_all([Compte(numero="606", libelle="Achats"), Compte(numero="512", libelle="Banque"),
                                Compte(numero="706", libelle="Ventes")])
            db.session.commit()

    def jeton(self, client):
        with client.session_transaction() as s:
            s.setdefault("csrf", "jeton-test")
            return s["csrf"]

    def connecter(self, client):
        j = self.jeton(client)
        client.post("/premier-demarrage", data={"csrf_token": j, "nom": "tresorier",
                                                "mdp": "motdepasse123", "mdp2": "motdepasse123"})

    def post(self, url, **kw):
        kw.setdefault("data", {})["csrf_token"] = self.jeton(self.c)
        return self.c.post(url, **kw)

    def ecriture(self, **extra):
        d = {"date": "2026-01-15", "journal": "OD", "libelle": "Test", "piece": "",
             "compte0": "606", "debit0": "100,50", "compte1": "512", "credit1": "100,50"}
        d.update(extra)
        return self.post("/saisie", data=d)


class TestMontants(unittest.TestCase):
    def test_conversion(self):
        self.assertEqual(en_centimes("1 234,56"), 123456)
        self.assertEqual(fmt_montant(123456), "1 234,56")
        with self.assertRaises(ValueError):
            en_centimes("abc")


class TestSaisie(Base):
    def test_equilibree(self):
        r = self.ecriture()
        self.assertEqual(r.status_code, 302)
        b = self.c.get("/balance").get_data(as_text=True)
        self.assertIn("100,50", b)

    def test_desequilibree_refusee(self):
        r = self.ecriture(credit1="99")
        self.assertEqual(r.status_code, 400)
        self.assertIn("non équilibrée", r.get_data(as_text=True))

    def test_compte_inconnu(self):
        self.assertEqual(self.ecriture(compte1="999").status_code, 400)

    def test_axe2_comptes_6_et_7_seulement(self):
        with self.app.app_context():
            db.session.add_all([CodeAxe2(code="MAN.001", libelle="Conférence", statut=1),
                                CodeAxe2(code="MAN.002", libelle="Terminée", statut=2)])
            db.session.commit()
        self.assertEqual(self.ecriture(axe2_0="MAN.001").status_code, 302)      # compte 606
        r = self.ecriture(axe2_1="MAN.001")                                        # compte 512
        self.assertEqual(r.status_code, 400)
        self.assertIn("classe 6 ou 7", r.get_data(as_text=True))
        self.assertEqual(self.ecriture(axe2_0="MAN.002").status_code, 400)       # Terminé
        self.assertEqual(self.ecriture(axe2_0="XXX").status_code, 400)           # inconnu
        self.assertIn("MAN.001", self.c.get("/analytique/2").get_data(as_text=True))

    def test_compte_inactif_refuse(self):
        with self.app.app_context():
            db.session.get(Compte, "606").actif = False
            db.session.commit()
        r = self.ecriture()
        self.assertEqual(r.status_code, 400)
        self.assertIn("inactif", r.get_data(as_text=True))

    def test_lien_javascript_refuse(self):
        self.assertEqual(self.ecriture(lien="javascript:alert(1)").status_code, 400)
        self.assertEqual(self.ecriture(lien="https://exemple.org/p.pdf").status_code, 302)


def csv_octets(texte, enc="cp1252"):
    import io
    return io.BytesIO(texte.encode(enc))


class TestPlan(Base):
    def test_ajout_et_suppression(self):
        self.post("/plan", data={"numero": "6061", "libelle": "Fournitures"})
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Compte, "6061"))
        self.ecriture(compte0="6061")
        self.post("/plan/6061/supprimer")  # utilisé : refusé
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Compte, "6061"))

    def importer(self, url, texte, enc="cp1252", **extra):
        data = {"fichier": (csv_octets(texte, enc), "f.csv"), **extra}
        return self.post(url, data=data, content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)

    def test_import_axes_et_plan_cp1252(self):
        self.importer("/axes/1/importer", "Code;Libellé;Statut\nACT.1;MANIFESTATIONS;En cours\nDON.1;DONS ÉMIS;Terminé\n")
        self.importer("/axes/2/importer", "Code;Libellé;Statut\nMAN.006;Raclette;Terminé\nSOC.001;Bourses;En cours\n")
        with self.app.app_context():
            self.assertEqual(db.session.get(CodeAxe1, "DON.1").libelle, "DONS ÉMIS")
            self.assertEqual(db.session.get(CodeAxe1, "DON.1").statut, 2)
            self.assertEqual(db.session.get(CodeAxe2, "MAN.006").statut, 2)
        self.importer("/plan/importer", "Compte;Libellé;Axe 1;Lettrable;Actif\n610000;MANIFESTATIONS DEPENSES;ACT.1;Non;Oui\n"
                                        "411000;ADHERENTS;;Oui;Oui\n")
        with self.app.app_context():
            c = db.session.get(Compte, "610000")
            self.assertEqual((c.axe1_code, c.lettrable, c.actif), ("ACT.1", False, True))
            self.assertTrue(db.session.get(Compte, "411000").lettrable)

    def test_import_plan_tout_ou_rien(self):
        r = self.importer("/plan/importer", "Compte;Libellé;Axe 1\n610000;A;INCONNU\n620000;B;\n")
        self.assertIn("Import refusé", r)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Compte, "620000"))
        self.assertIn("Colonne", self.importer("/axes/1/importer", "Truc;Machin\nA;B\n"))

    def test_import_remplacer_inutilises(self):
        self.ecriture()                      # 606 et 512 utilisés
        self.importer("/plan/importer", "Compte;Libellé\n610000;A\n", remplacer="on")
        with self.app.app_context():
            self.assertIsNone(db.session.get(Compte, "706"))        # inutilisé : supprimé
            self.assertIsNotNone(db.session.get(Compte, "606"))     # utilisé : conservé

    def test_changer_axe1_dun_compte(self):
        self.importer("/axes/1/importer", "Code;Libellé\nFRA.1;Frais\n")
        self.post("/plan/606/modifier", data={"libelle": "Achats", "axe1": "FRA.1", "actif": "on"})
        with self.app.app_context():
            self.assertEqual(db.session.get(Compte, "606").axe1_code, "FRA.1")
        self.ecriture()
        self.assertIn("FRA.1", self.c.get("/analytique/1").get_data(as_text=True))


class TestImportEcritures(Base):
    ENTETE = "Mvt;Jnl;Date;Compte;LibelCompte;Libelle;Debit;Credit;Anal1;LibelAnal1;Anal2;LibelAnal2;Lien;Let\n"

    def importer(self, texte):
        data = {"fichier": (csv_octets(self.ENTETE + texte), "e.csv")}
        return self.post("/ecritures/importer", data=data, content_type="multipart/form-data",
                         follow_redirects=True).get_data(as_text=True)

    def prepare(self):
        self.post("/axes/1/importer", data={"fichier": (csv_octets("Code;Libellé\nBIL.4;Tiers\nACT.1;Manif\n"), "a.csv")},
                  content_type="multipart/form-data")
        self.post("/axes/2/importer", data={"fichier": (csv_octets("Code;Libellé\nMAN.007;Rallye\n"), "b.csv")},
                  content_type="multipart/form-data")

    OK = ("7;B3;31/12/2025;512;BANQUE;Rallye Dupont;1 600.00;;;;MAN.007;Rallye;https://exemple.org/p;\n"
          "7;B3;31/12/2025;706;VENTES;Rallye Dupont;;1 600.00;ACT.1;Manif;MAN.007;Rallye;;\n"
          "9;CA;01/01/2026;411DUPON001;DUPONT;Autre;10,50;;BIL.4;Tiers;MAN.007;Rallye;;\n"
          "9;CA;01/01/2026;706;VENTES;Autre;;10,50;ACT.1;Manif;;;;\n")

    def test_import_complet(self):
        self.prepare()
        r = self.importer(self.OK)
        self.assertIn("Import réussi : 2 écritures (4 lignes)", r)
        self.assertIn("1 compte(s) créé(s)", r)
        self.assertIn("2 code(s) Axe 2 ignoré(s)", r)    # sur 512 et 411 (hors 6/7) ; 706 le garde
        with self.app.app_context():
            e = db.session.get(Ecriture, 7)
            self.assertEqual(e.journal_code, "B3")
            self.assertEqual(e.lien, "https://exemple.org/p")
            par = {l.compte_numero: (l.debit, l.credit, l.axe2_code) for l in e.lignes}
            self.assertEqual(par["512"], (160000, 0, None))
            self.assertEqual(par["706"], (0, 160000, "MAN.007"))
            self.assertEqual(db.session.get(Compte, "411DUPON001").axe1_code, "BIL.4")
        self.assertIn("Journal", self.c.get("/journaux").get_data(as_text=True) + "Journal")
        self.ecriture()
        with self.app.app_context():
            self.assertEqual(db.session.query(Ecriture.mvt).order_by(Ecriture.mvt.desc()).first()[0], 10)

    def test_renumeroter_a_la_suite(self):
        self.prepare()
        self.importer(self.OK)                                   # écritures 7 et 9
        data = {"fichier": (csv_octets(self.ENTETE + self.OK), "e.csv"), "renumeroter": "on"}
        r = self.post("/ecritures/importer", data=data, content_type="multipart/form-data",
                      follow_redirects=True).get_data(as_text=True)
        self.assertIn("renumérotées 10 à 11", r)
        with self.app.app_context():
            self.assertEqual([e.mvt for e in Ecriture.query.order_by(Ecriture.mvt)], [7, 9, 10, 11])
            from comptajlc.models import Historique
            self.assertIn("n° 7 dans le fichier", Historique.query.filter_by(mvt=10).one().motif)
            self.assertEqual(db.session.get(Ecriture, 10).libelle, "Rallye Dupont")
        # sans la case, le doublon reste refusé
        self.assertIn("existe déjà", self.importer(self.OK))

    def test_rien_si_erreur(self):
        self.prepare()
        mauvais = self.OK + "11;OD;01/02/2026;512;B;Seul;5;;;;;;;\n"       # déséquilibré
        self.assertIn("non équilibrée", self.importer(mauvais))
        with self.app.app_context():
            self.assertEqual(Ecriture.query.count(), 0)
            self.assertIsNone(db.session.get(Compte, "411DUPON001"))

    def test_numero_existant_et_lien_dangereux(self):
        self.prepare()
        self.importer(self.OK)
        self.assertIn("existe déjà", self.importer(self.OK))
        self.assertIn("http", self.importer(self.OK.replace("https://exemple.org/p", "javascript:alert(1)").replace("7;", "20;").replace("9;", "21;")))
        with self.app.app_context():
            self.assertEqual(Ecriture.query.count(), 2)


class TestCorrection(Base):
    def historique(self):
        from comptajlc.models import Historique
        with self.app.app_context():
            return [(h.action, h.mvt, h.motif, h.utilisateur) for h in Historique.query.order_by(Historique.id)]

    def donnees(self, **extra):
        d = {"date": "2026-02-01", "journal": "OD", "libelle": "Corrigée", "piece": "P1",
             "compte0": "606", "debit0": "50", "compte1": "512", "credit1": "50", "motif": "erreur de montant"}
        d.update(extra)
        return d

    def test_creation_tracee_et_modification(self):
        self.ecriture()
        self.assertEqual(self.historique(), [("création", 1, "", "tresorier")])
        self.assertIn("Modifier l'écriture n° 1", self.c.get("/ecriture/1/modifier").get_data(as_text=True))
        self.assertEqual(self.post("/ecriture/1/modifier", data=self.donnees()).status_code, 302)
        self.assertIn("50,00", self.c.get("/balance").get_data(as_text=True))
        self.assertNotIn("100,50", self.c.get("/balance").get_data(as_text=True))
        self.assertEqual(self.historique()[1], ("modification", 1, "erreur de montant", "tresorier"))
        h = self.c.get("/historique").get_data(as_text=True)
        self.assertIn("100,50", h)   # l'ancienne valeur reste visible
        self.assertIn("erreur de montant", h)

    def test_modification_sans_motif_ou_desequilibree(self):
        self.ecriture()
        self.assertEqual(self.post("/ecriture/1/modifier", data=self.donnees(motif="")).status_code, 400)
        self.assertEqual(self.post("/ecriture/1/modifier", data=self.donnees(credit1="1")).status_code, 400)
        self.assertIn("100,50", self.c.get("/balance").get_data(as_text=True))
        self.assertEqual(len(self.historique()), 1)

    def test_suppression_et_numero_non_reutilise(self):
        self.ecriture()
        self.post("/ecriture/1/supprimer", data={"motif": ""})      # refusé
        self.assertEqual(len(self.historique()), 1)
        self.post("/ecriture/1/supprimer", data={"motif": "doublon"})
        self.assertEqual(self.historique()[-1], ("suppression", 1, "doublon", "tresorier"))
        self.assertNotIn("100,50", self.c.get("/balance").get_data(as_text=True))
        self.ecriture()
        self.assertEqual(self.historique()[-1][:2], ("création", 2))   # 1 n'est pas réutilisé

    def test_inconnue(self):
        self.assertEqual(self.c.get("/ecriture/99/modifier").status_code, 404)


class TestExport(Base):
    def charger(self, url):
        import io
        from openpyxl import load_workbook
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r.mimetype)
        return load_workbook(io.BytesIO(r.data))

    def test_journal_et_balance(self):
        self.ecriture(libelle="=1+1")
        ws = self.charger("/export/journal.xlsx").active
        self.assertEqual(ws["H2"].value, 100.5)
        self.assertEqual(ws["I3"].value, 100.5)
        self.assertEqual(ws["E2"].value, "=1+1")
        self.assertEqual(ws["E2"].data_type, "s")      # texte, pas une formule
        wb = self.charger("/export/balance.xlsx").active
        self.assertEqual(wb["C3"].value, 100.5)   # 606 (512 est en C2)
        self.assertEqual(wb["C4"].value, "=SUM(C2:C3)")

    def test_export_protege(self):
        anonyme = self.app.test_client()
        self.assertEqual(anonyme.get("/export/journal.xlsx").status_code, 302)


class TestRechercheEtSelection(Base):
    def remplir(self):
        self.ecriture(libelle="Loyer janvier", date="2026-01-10")
        self.ecriture(libelle="Cotisation 100%", date="2026-02-10", journal="CA")
        self.ecriture(libelle="Loyer février", date="2026-02-20", compte0="706", compte1="512", debit0="", credit0="5", debit1="5", credit1="")

    def page(self, qs=""):
        return self.c.get("/journal" + qs).get_data(as_text=True)

    def test_filtres(self):
        self.remplir()
        self.assertIn("<strong>3</strong> écriture(s)", self.page())
        self.assertIn("<strong>2</strong> écriture(s)", self.page("?q=loyer"))
        self.assertIn("<strong>1</strong> écriture(s)", self.page("?q=100%25"))        # % est un texte, pas un joker
        self.assertIn("<strong>1</strong> écriture(s)", self.page("?journal=CA"))
        self.assertIn("<strong>1</strong> écriture(s)", self.page("?compte=706"))
        self.assertIn("<strong>2</strong> écriture(s)", self.page("?du=2026-02-01"))
        self.assertIn("<strong>1</strong> écriture(s)", self.page("?du=2026-02-01&au=2026-02-15"))
        self.assertIn("<strong>1</strong> écriture(s)", self.page("?mvt_de=2&mvt_a=2"))
        self.assertIn("Aucune écriture", self.page("?q=zzz"))
        self.assertEqual(self.c.get("/journal?du=pas-une-date&page=abc").status_code, 200)

    def test_pagination(self):
        for i in range(55):
            self.ecriture(libelle=f"E{i}")
        self.assertIn("Page 1 / 2", self.page())
        self.assertIn("Page 2 / 2", self.page("?page=2"))
        self.assertIn("Page 2 / 2", self.page("?page=99"))

    def test_suppression_par_selection(self):
        self.remplir()
        self.post("/ecritures/supprimer", data={"mvt": ["1", "2"], "motif": ""})
        self.post("/ecritures/supprimer", data={"motif": "x"})
        with self.app.app_context():
            self.assertEqual(Ecriture.query.count(), 3)                 # refusées
        r = self.post("/ecritures/supprimer", data={"mvt": ["1", "3"], "motif": "doublons", "retour": "?q=loyer"})
        self.assertTrue(r.headers["Location"].endswith("/journal?q=loyer"))
        with self.app.app_context():
            self.assertEqual([e.mvt for e in Ecriture.query], [2])
        from comptajlc.models import Historique
        with self.app.app_context():
            h = [(x.action, x.mvt, x.motif) for x in Historique.query.filter_by(action="suppression")]
        self.assertEqual(sorted(h), [("suppression", 1, "doublons"), ("suppression", 3, "doublons")])

    def test_retour_externe_ignore(self):
        self.remplir()
        r = self.post("/ecritures/supprimer", data={"mvt": ["1"], "motif": "x", "retour": "//evil.example"})
        self.assertNotIn("evil", r.headers["Location"])

    def test_export_filtre(self):
        import io
        from openpyxl import load_workbook
        self.remplir()
        ws = load_workbook(io.BytesIO(self.c.get("/export/journal.xlsx?q=loyer").data)).active
        self.assertEqual(ws.max_row, 1 + 4)                             # 2 écritures x 2 lignes


class TestReinitialisation(Base):
    def vider(self, **extra):
        d = {"portee": "tout", "mdp": "motdepasse123", "phrase": "VIDER"}
        d.update(extra)
        return self.post("/reinitialiser", data=d)

    def compter(self):
        with self.app.app_context():
            return (Ecriture.query.count(), Compte.query.count(), CodeAxe1.query.count())

    def test_refus_sans_mot_de_passe_ou_phrase(self):
        self.ecriture()
        self.vider(mdp="faux")
        self.vider(phrase="vider")
        self.vider(portee="rien")
        self.assertEqual(self.compter()[0], 1)

    def test_vider_ecritures_seulement(self):
        self.ecriture()
        self.assertEqual(self.vider(portee="ecritures").status_code, 302)
        e, comptes, _ = self.compter()
        self.assertEqual((e, comptes), (0, 3))                    # plan conservé
        from comptajlc.models import Historique
        with self.app.app_context():
            self.assertEqual([h.action for h in Historique.query], ["réinitialisation"])
        self.ecriture()                                             # on peut ressaisir
        with self.app.app_context():
            self.assertEqual(db.session.query(Ecriture.mvt).scalar(), 1)

    def test_tout_vider_puis_recharger(self):
        with self.app.app_context():
            db.session.add(CodeAxe1(code="ACT.1", libelle="x"))
            db.session.commit()
        self.ecriture()
        self.vider()
        self.assertEqual(self.compter(), (0, 0, 0))
        im = TestImportEcritures("test_import_complet")
        im.app, im.c = self.app, self.c
        im.jeton, im.post = self.jeton, self.post
        im.prepare()
        self.assertIn("Import réussi", im.importer(TestImportEcritures.OK))

    def test_copie_de_sauvegarde_et_export_historique(self):
        import os, tempfile
        d = tempfile.mkdtemp()
        app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join(d, "t.db")})
        app.instance_path = d
        c = app.test_client()
        with c.session_transaction() as s:
            s["csrf"] = "j"
        c.post("/premier-demarrage", data={"csrf_token": "j", "nom": "a", "mdp": "motdepasse123", "mdp2": "motdepasse123"})
        with c.session_transaction() as s:
            jeton = s["csrf"]                       # renouvelé à la connexion
        c.post("/reinitialiser", data={"csrf_token": jeton, "portee": "ecritures", "mdp": "motdepasse123", "phrase": "VIDER"})
        self.assertEqual(len(os.listdir(os.path.join(d, "sauvegardes"))), 1)
        self.assertEqual(c.get("/export/historique.xlsx").status_code, 200)


class TestAuth(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})
        self.c = self.app.test_client()

    def jeton(self):
        with self.c.session_transaction() as s:
            s.setdefault("csrf", "jeton-test")
            return s["csrf"]

    def test_premier_demarrage_puis_connexion_obligatoire(self):
        self.assertIn("/premier-demarrage", self.c.get("/plan").headers["Location"])
        r = self.c.post("/premier-demarrage", data={"csrf_token": self.jeton(), "nom": "a",
                                                    "mdp": "court", "mdp2": "court"})
        self.assertIn("au moins 10", r.get_data(as_text=True))
        self.c.post("/premier-demarrage", data={"csrf_token": self.jeton(), "nom": "a",
                                                "mdp": "motdepasse123", "mdp2": "motdepasse123"})
        self.assertEqual(self.c.get("/plan").status_code, 200)
        self.c.post("/deconnexion", data={"csrf_token": self.jeton()})
        self.assertIn("/connexion", self.c.get("/plan").headers["Location"])
        self.assertEqual(self.c.get("/premier-demarrage").status_code, 302)

    def test_mauvais_mot_de_passe_et_bon(self):
        self.c.post("/premier-demarrage", data={"csrf_token": self.jeton(), "nom": "a",
                                                "mdp": "motdepasse123", "mdp2": "motdepasse123"})
        self.c.post("/deconnexion", data={"csrf_token": self.jeton()})
        r = self.c.post("/connexion", data={"csrf_token": self.jeton(), "nom": "a", "mdp": "faux"})
        self.assertIn("incorrect", r.get_data(as_text=True))
        self.assertIn("/connexion", self.c.get("/saisie").headers["Location"])
        r = self.c.post("/connexion", data={"csrf_token": self.jeton(), "nom": "a",
                                            "mdp": "motdepasse123", "suite": "/saisie"})
        self.assertTrue(r.headers["Location"].endswith("/saisie"))

    def test_redirection_externe_refusee(self):
        self.c.post("/premier-demarrage", data={"csrf_token": self.jeton(), "nom": "a",
                                                "mdp": "motdepasse123", "mdp2": "motdepasse123"})
        self.c.post("/deconnexion", data={"csrf_token": self.jeton()})
        r = self.c.post("/connexion", data={"csrf_token": self.jeton(), "nom": "a",
                                            "mdp": "motdepasse123", "suite": "//evil.example"})
        self.assertNotIn("evil", r.headers["Location"])

    def test_csrf_refuse(self):
        self.c.post("/premier-demarrage", data={"csrf_token": self.jeton(), "nom": "a",
                                                "mdp": "motdepasse123", "mdp2": "motdepasse123"})
        self.assertEqual(self.c.post("/plan", data={"numero": "999", "libelle": "x"}).status_code, 400)
        self.assertEqual(self.c.post("/plan", data={"csrf_token": "faux", "numero": "999",
                                                    "libelle": "x"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
