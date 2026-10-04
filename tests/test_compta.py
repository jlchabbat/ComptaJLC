import unittest

from comptajlc import create_app
from comptajlc.models import Axe, CodeAnalytique, Compte, db
from comptajlc.vues import en_centimes, fmt_montant


class Base(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})
        self.c = self.app.test_client()
        self.connecter(self.c)

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

    def test_analytique(self):
        with self.app.app_context():
            a = Axe.query.first()
            code = CodeAnalytique(axe_id=a.id, code="ACT.1", libelle="Activité")
            db.session.add(code)
            db.session.commit()
            aid, cid = a.id, code.id
        self.assertEqual(self.ecriture(**{f"axe{aid}_0": str(cid)}).status_code, 302)
        self.assertIn("ACT.1", self.c.get(f"/analytique/{aid}").get_data(as_text=True))


class TestPlan(Base):
    def test_ajout_import_suppression(self):
        self.post("/plan", data={"numero": "6061", "libelle": "Fournitures"})
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Compte, "6061"))
        import io
        self.post("/plan/importer", data={"fichier": (io.BytesIO("7061;Dons\n".encode()), "p.csv")},
                  content_type="multipart/form-data")
        with self.app.app_context():
            self.assertEqual(db.session.get(Compte, "7061").libelle, "Dons")
        self.ecriture(compte0="6061")
        self.post("/plan/6061/supprimer")  # utilisé : refusé
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Compte, "6061"))


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
