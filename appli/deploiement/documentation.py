"""Régénère la documentation : captures d'écran, puis les PDF (Présentation, Mode d'emploi, Installation, Principes ; protocoles dans docs).

    cd appli && python deploiement/documentation.py

Étapes : base de démonstration (données fictives) dans un dossier temporaire, site lancé en local, captures d'écran
(docs/images), puis impression en PDF de docs/presentation.html et docs/mode-emploi.html. Les PDF sont écrits dans
compta/documentation (servis par l'application : menu Éditions), sans copie dans docs/ (une seule version dans Git).

À relancer après chaque changement visible de l'application, avant de publier la mise à jour.
Nécessite Playwright et Chromium (poste de développement) ; rien de tout cela n'est utile sur le site."""

import datetime as dt
import glob
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from decimal import Decimal as D
from pathlib import Path

APPLI = Path(__file__).resolve().parent.parent
DOCS = APPLI.parent / "docs"
IMAGES = DOCS / "images"
SORTIE = APPLI / "compta" / "documentation"
MOT_DE_PASSE = "Demo-ComptaJLC-2026"
DOCUMENTS = {"presentation.html": ("Présentation", "ComptaJLC_presentation.pdf"),
             "mode-emploi.html": ("Mode d'emploi", "ComptaJLC_mode_emploi.pdf"),
             "installation.html": ("Installation et mises à jour", "ComptaJLC_installation.pdf"),
             "principes.html": ("Principes de fonctionnement", "ComptaJLC_principes.pdf")}
PROTOCOLES = {"protocole-mise-a-jour.html": ("Protocole de mise à jour", "ComptaJLC_protocole_mise_a_jour.pdf"),
              "protocole-iphone-justificatifs.html": ("Documents avec un iPhone", "ComptaJLC_protocole_iphone_justificatifs.pdf")}


def preparer_django(dossier):
    os.environ["COMPTAJLC_DATA"] = str(dossier)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "comptajlc.settings")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"          # lectures de la base pendant les captures (Playwright)
    sys.path.insert(0, str(APPLI))
    import django
    django.setup()


def demonstration():
    """Données fictives, assez complètes pour que chaque page montre quelque chose."""
    from django.contrib.auth.models import User
    from django.core.management import call_command

    from compta import saisie as moteur
    from compta import tiers
    from compta.models import (Budget, CodeAnalytique, Compte, Exercice, Journal, Ligne, LigneReleve, Mouvement, ParametreReleve,
                               Prefixe, Reglage, Tiers, Traduction, TypeTiers)
    from compta.vues_utilisateurs import donner_role

    call_command("migrate", verbosity=0)
    for code, lib in (("BIL.4", "TIERS"), ("BIL.5", "TRESORERIE"), ("REC.1", "RECETTES"), ("ACT.1", "ACTIVITES"),
                      ("FON.1", "FONCTIONNEMENT"), ("DON.1", "DONS ET SUBVENTIONS")):
        CodeAnalytique.objects.create(code=code, libelle=lib)
    for p, lib in (("REC.", "Recettes"), ("ACT.", "Activités"), ("FON.", "Fonctionnement"), ("DON.", "Dons et subventions")):
        Prefixe.objects.create(prefixe=p, libelle=lib)
    comptes = [("110000", "REPORT A NOUVEAU", "BIL.5"), ("401000", "FOURNISSEURS DIVERS", "BIL.4"),
               ("411000", "CLIENTS DIVERS", "BIL.4"), ("512000", "BANQUE COMPTE COURANT", "BIL.5"),
               ("512100", "BANQUE EPARGNE", "BIL.5"), ("530000", "CAISSE", "BIL.5"), ("580000", "VIREMENTS INTERNES", "BIL.5"),
               ("470000", "COMPTE D'ATTENTE", "BIL.5"), ("600000", "ACHATS DIVERS", "FON.1"), ("600100", "FRAIS BANCAIRES", "FON.1"),
               ("600200", "LOCATION DE SALLE", "ACT.1"), ("610000", "PRESTATAIRES", "ACT.1"), ("625000", "DONS VERSES", "DON.1"),
               ("700000", "VENTES ET PRESTATIONS", "REC.1"), ("710000", "RECETTES D'ACTIVITES", "ACT.1"),
               ("725000", "DONS RECUS", "DON.1"), ("740000", "SUBVENTIONS", "DON.1"), ("750000", "INTERETS", "FON.1")]
    for n, lib, a1 in comptes:
        Compte.objects.create(numero=n, libelle=lib, anal1_id=a1)
    for code, intitule, compte in (("B1", "Banque compte courant", "512000"), ("B2", "Banque épargne", "512100"),
                                   ("CA", "Caisse", "530000"), ("VT", "Ventes", None), ("HA", "Achats", None),
                                   ("OD", "Opérations diverses", None), ("AN", "À-nouveaux", None)):
        Journal.objects.create(code=code, intitule=intitule, compte_id=compte)
    Exercice.objects.create(libelle="2025", debut=dt.date(2025, 1, 1), fin=dt.date(2025, 12, 31), clos=True)
    Exercice.objects.create(libelle="2026", debut=dt.date(2026, 1, 1), fin=dt.date(2026, 12, 31))
    for cle, valeur in (("compte_virement", "580000"), ("compte_attente", "470000"), ("nom_association", "Association exemple"),
                        ("releves_mizrahi", ""), ("releve_bit", ""), ("carte_bancaire", ""), ("traductions_releve", "oui")):
        Reglage.objects.update_or_create(cle=cle, defaults={"valeur": valeur})
    moteur.initialiser_parametres()

    client, fournisseur = TypeTiers.objects.get(libelle="Client"), TypeTiers.objects.get(libelle="Fournisseur")
    for compte, t, nom, prenom, adresse, cp, ville, email in (
            ("411COHEN001", client, "COHEN", "David", "12 rue Herzl", "4250000", "Netanya", "david.cohen@exemple.org"),
            ("411LEVYS001", client, "LEVY", "Sarah", "3 rue Weizmann", "4340000", "Raanana", "sarah.levy@exemple.org"),
            ("411TAIEB001", client, "TAIEB", "Jeanne", "8 rue Sokolov", "4250000", "Netanya", "jeanne.taieb@exemple.org"),
            ("411ATTAL001", client, "ATTAL", "Michel", "21 rue Bialik", "6100000", "Tel Aviv", ""),
            ("401TRAIT001", fournisseur, "TRAITEUR DU PARC", "", "5 rue Allenby", "6100000", "Tel Aviv", "contact@exemple.org")):
        Compte.objects.create(numero=compte, libelle=f"{nom} {prenom}".strip().upper(), anal1_id="BIL.4", lettrable=True)
        Tiers.objects.create(compte_id=compte, type=t, nom=nom, prenom=prenom, adresse=adresse, code_postal=cp, ville=ville,
                             email=email, telephone="+972 50 000 00 00")
    tiers.creer_manquants()

    admin = User.objects.create_user("admin", password=MOT_DE_PASSE, first_name="Jean", last_name="Administrateur")
    donner_role(admin, "Administration")
    gestion = User.objects.create_user("gestion", password=MOT_DE_PASSE, first_name="Paul", last_name="Gestionnaire",
                                       email="gestion@exemple.org")
    donner_role(gestion, "Gestion")

    mp = {m.libelle: m for m in moteur.MoyenPaiement.objects.all()}
    types = {m.type: m for m in moteur.ModeleOperation.objects.all()}

    def saisir(jour, modele, montant, paiement=None, tiers_=None, vers=None, compte=None):
        op = moteur.Operation(date=jour, modele=types[modele], tiers=Compte.objects.get(pk=tiers_) if tiers_ else None,
                              montant=D(montant), paiement=mp.get(paiement), vers=mp.get(vers),
                              compte=Compte.objects.get(pk=compte) if compte else None)
        r = moteur.controler(op)
        if not r.ok:
            raise SystemExit(f"Démonstration : saisie refusée ({modele}) : {r.erreurs}")
        moteur.enregistrer(op, gestion)

    j = lambda m, d: dt.date(2026, m, d)  # noqa: E731
    an = Mouvement.objects.create(numero=1, date=j(1, 1), journal_id="AN", origine="import", commentaire="Soldes d'ouverture")
    for ordre, (compte, debit, credit) in enumerate((("512000", 8000, 0), ("512100", 3000, 0), ("530000", 450, 0),
                                                     ("110000", 0, 11450))):
        Ligne.objects.create(mouvement=an, ordre=ordre, compte_id=compte, libelle="A NOUVEAU", debit=D(debit), credit=D(credit))
    banque, epargne = "Banque compte courant", "Banque épargne"
    for i, (compte, paiement) in enumerate((("411COHEN001", banque), ("411LEVYS001", banque), ("411TAIEB001", "Caisse (espèces)"))):
        saisir(j(1, 10 + i), "Facture client", 500 if i < 2 else 400, paiement, compte, compte="700000")
    saisir(j(1, 20), "Facture client", 400, "Non réglé", "411ATTAL001", compte="700000")
    saisir(j(2, 3), "Frais bancaires", 25, banque)
    saisir(j(3, 1), "Frais bancaires", 25, banque)
    saisir(j(3, 15), "Facture fournisseur", 3200, banque, "401TRAIT001", compte="610000")
    saisir(j(4, 2), "Virement interne", 2000, banque, vers=epargne)
    saisir(j(5, 12), "Dépense directe", 850, "Caisse (espèces)", compte="625000")

    # relevé bancaire téléchargé : deux lignes déjà en compta, quatre à passer
    b1 = Journal.objects.get(code="B1")
    ParametreReleve.objects.create(journal=b1, libelle="Relevé du compte courant", date_reprise=j(1, 1))
    for hebreu, francais in (("עמלת מסלול", "Frais de forfait"), ("הפקדת שיק", "Remise de chèque"),
                             ("העברה באינטרנט", "Virement internet"), ("ריבית זכות", "Intérêts créditeurs")):
        Traduction.objects.create(cle=Traduction.cle_de(hebreu), hebreu=hebreu, traduction=francais)
    for rang, (jour, operation, montant) in enumerate((
            (j(1, 11), "העברה באינטרנט", 500), (j(2, 3), "עמלת מסלול", -25), (j(3, 2), "עמלת מסלול", -25),
            (j(6, 30), "ריבית זכות", 42),
            (j(7, 9), "הפקדת שיק", 300), (j(7, 14), "משיכת מזומן", -200))):
        LigneReleve.objects.create(journal=b1, date=jour, rang=rang + 1, reference=str(5100 + rang), operation=operation,
                                   montant=D(montant), source="demo.xlsx")
    from compta import releves
    for l in LigneReleve.objects.filter(journal=b1, date__lt=j(3, 1)):          # déjà passées en compta : reliées
        releves.relier(l, releves.deja_en_compta(l)[0], gestion)
    ex = Exercice.objects.get(libelle="2026")
    for compte, nature, montant in (("700000", "P", 2000), ("710000", "P", 1500), ("610000", "C", 3000), ("600100", "C", 300)):
        Budget.objects.create(exercice=ex, nature=nature, compte_id=compte, montant=D(montant))


def port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def captures(adresse):
    """Une capture par écran décrit dans la documentation (docs/images)."""
    from playwright.sync_api import sync_playwright
    IMAGES.mkdir(parents=True, exist_ok=True)
    for vieux in IMAGES.glob("*.png"):
        vieux.unlink()
    with sync_playwright() as p:
        navigateur = p.chromium.launch(**chromium())
        contexte = navigateur.new_context(viewport={"width": 1400, "height": 800}, locale="fr-FR")

        def page_de(utilisateur):
            pg = contexte.new_page()
            pg.goto(adresse + "/connexion/")
            pg.fill("#id_username", utilisateur)
            pg.fill("#id_password", MOT_DE_PASSE)
            pg.click("button.principal")
            pg.wait_for_load_state("networkidle")
            return pg

        def photo(pg, nom, chemin=None, hauteur=None, avant=None):
            if chemin:
                pg.goto(adresse + chemin)
                pg.wait_for_load_state("networkidle")
            if avant:
                avant(pg)
            pg.screenshot(path=str(IMAGES / f"{nom}.png"), full_page=hauteur is None,
                          clip=None if hauteur is None else {"x": 0, "y": 0, "width": 1400, "height": hauteur})

        pg = contexte.new_page()
        pg.goto(adresse + "/connexion/")
        photo(pg, "01_connexion", hauteur=480)
        contexte.clear_cookies()

        pg = page_de("gestion")

        def menu(nom):
            def f(pg):
                pg.locator(f".menu > button:has-text('{nom}')").hover()
                pg.wait_for_timeout(300)
            return f
        photo(pg, "02_accueil_menu", "/", hauteur=720, avant=menu("Consulter"))

        def apercu(pg):
            pg.evaluate("""() => {
                const f = document.querySelector('#f-saisie');
                const choisir = (nom, texte) => { const s = f.querySelector(`select[name=${nom}]`);
                    const o = [...s.options].find(o => o.text.includes(texte)); s.value = o.value; };
                choisir('modele', 'Facture client'); choisir('tiers', 'ATTAL'); choisir('paiement', 'Caisse');
                choisir('compte', '700000'); f.querySelector('input[name=montant]').value = '400';
            }""")
            pg.click("button[name=apercu]")
            pg.wait_for_load_state("networkidle")
        photo(pg, "03_saisie", "/saisie/", avant=apercu)
        photo(pg, "04_mouvement", "/mouvement/2/")
        photo(pg, "05_modifier", "/mouvement/2/modifier/")
        photo(pg, "06_codes", "/codes/")
        photo(pg, "07_tiers", "/tiers/", hauteur=720)
        photo(pg, "08_fiche_tiers", "/tiers/411ATTAL001/", hauteur=720)
        photo(pg, "09_plan", "/plan/", hauteur=760)
        photo(pg, "10_codes_anal", "/parametrage/axes/", hauteur=620)
        photo(pg, "11_journal", "/journaux/?journal=B1&du=2026-01-01&au=2026-12-31", hauteur=760)
        photo(pg, "12_ecritures", "/ecritures/", hauteur=720)
        photo(pg, "13_banque", "/rapprochement/B1/", hauteur=760)
        photo(pg, "14_mon_compte", "/mon-compte/", hauteur=620)
        photo(pg, "15_etats", "/etats/", hauteur=760)
        photo(pg, "16_cloture", "/cloture/", hauteur=760)
        photo(pg, "18_controles", "/controles/", hauteur=720)
        photo(pg, "19_historique", "/modifications/", hauteur=620)
        photo(pg, "20_situation", "/situation/?du=2026-01-01&au=2026-12-31", hauteur=900)
        photo(pg, "21_analytique", "/analytique/?du=2026-01-01&au=2026-12-31", hauteur=720)
        photo(pg, "23_grand_livre", "/grand-livre/?compte=512000&du=2026-01-01&au=2026-12-31", hauteur=720)
        photo(pg, "24_justificatifs", "/justificatifs/a-classer/", hauteur=620)
        contexte.clear_cookies()

        pg = page_de("admin")
        photo(pg, "17_base", "/base/", hauteur=760)
        photo(pg, "22_utilisateurs", "/utilisateurs/")
        photo(pg, "25_echanges", "/echanges/", hauteur=760)
        photo(pg, "26_menu_editions", "/", hauteur=420, avant=menu("Éditions"))
        navigateur.close()


def chromium():
    """Chromium installé sur le poste ; à défaut, celui de Playwright."""
    for motif in ("/opt/pw-browsers/chromium-*/chrome-linux*/chrome", "/usr/bin/chromium*", "/usr/bin/google-chrome*"):
        trouves = sorted(glob.glob(motif))
        if trouves:
            return {"executable_path": trouves[-1], "args": ["--lang=fr-FR"]}
    return {"args": ["--lang=fr-FR"]}


def imprimer():
    """HTML → PDF (A4), avec les en-têtes de page et la numérotation."""
    from playwright.sync_api import sync_playwright
    SORTIE.mkdir(parents=True, exist_ok=True)
    pied = ('<div style="font-size:7.5pt;color:#777;width:100%;padding:0 14mm;display:flex;justify-content:space-between">'
            '<span>ComptaJLC – {titre} – version du {date}</span><span><span class="pageNumber"></span> / '
            '<span class="totalPages"></span></span></div>')
    with sync_playwright() as p:
        navigateur = p.chromium.launch(**chromium())
        for source, (titre, pdf) in {**DOCUMENTS, **PROTOCOLES}.items():
            if "--seul" in sys.argv and source != sys.argv[sys.argv.index("--seul") + 1]:
                continue                                      # ex. : --sans-captures --seul principes.html
            pg = navigateur.new_page()
            pg.goto((DOCS / source).as_uri())
            pg.wait_for_load_state("networkidle")
            cible = DOCS / pdf if source in PROTOCOLES else SORTIE / pdf
            pg.pdf(path=str(cible), format="A4", print_background=True, prefer_css_page_size=True,
                   display_header_footer=True, header_template="<span></span>",
                   footer_template=pied.format(titre=titre, date=f"{dt.date.today():%d/%m/%Y}"))
            print(f"  {cible}")
        navigateur.close()


def main():
    dossier = Path(tempfile.mkdtemp(prefix="comptajlc-doc-"))
    preparer_django(dossier)
    if "--sans-captures" not in sys.argv:
        demonstration()
        port = port_libre()
        env = dict(os.environ, COMPTAJLC_DATA=str(dossier), COMPTAJLC_IMPORTS=str(dossier / "Imports"),
                   COMPTAJLC_EXPORTS=str(dossier / "Exports"))
        serveur = subprocess.Popen([sys.executable, "manage.py", "runserver", "--noreload", f"127.0.0.1:{port}"], cwd=APPLI,
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                try:
                    socket.create_connection(("127.0.0.1", port), 0.5).close()
                    break
                except OSError:
                    time.sleep(0.5)
            captures(f"http://127.0.0.1:{port}")
        finally:
            serveur.terminate()
        print(f"Captures : {IMAGES}")
    imprimer()
    shutil.rmtree(dossier, ignore_errors=True)


if __name__ == "__main__":
    main()
