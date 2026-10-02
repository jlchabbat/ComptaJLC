"""Régénère la documentation intégrée à l'application : captures d'écran, puis Présentation et Mode d'emploi en PDF.

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
MOT_DE_PASSE = "Demo-ComptaBB-2026"
DOCUMENTS = {"presentation.html": ("Présentation", "ComptaBB_presentation.pdf"),
             "mode-emploi.html": ("Mode d'emploi", "ComptaBB_mode_emploi.pdf"),
             "installation.html": ("Installation et mises à jour", "ComptaBB_installation.pdf")}


def preparer_django(dossier):
    os.environ["COMPTABB_DATA"] = str(dossier)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "comptabb.settings")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"          # lectures de la base pendant les captures (Playwright)
    sys.path.insert(0, str(APPLI))
    import django
    django.setup()


def demonstration():
    """Données fictives, assez complètes pour que chaque page montre quelque chose."""
    from django.contrib.auth.models import User
    from django.core.management import call_command

    from compta import fiches, membres
    from compta import saisie as moteur
    from compta.models import (Budget, CodeAnalytique, Compte, Exercice, Fiche, Journal, LigneFiche, LigneReleve, Membre,
                               ModeFiche, ModeleOperation, MoyenPaiement, NatureFiche, ParametreReleve, Prefixe, Reglage,
                               TiersProvisoire, Traduction, TypeTiers)
    from compta.vues_utilisateurs import donner_role

    call_command("migrate", verbosity=0)
    for code, lib in (("BIL.5", "TRESORERIE"), ("BIL.4", "TIERS"), ("COT.2", "COTISATIONS"), ("FON.1", "FONCTIONNEMENT"),
                      ("MAN.1", "MANIFESTATIONS")):
        CodeAnalytique.objects.create(code=code, axe=1, libelle=lib)
    for code, lib in (("GEN.001", "GENERAL"), ("GEN.002", "COTISATIONS"), ("GEN.004", "BANQUE"), ("MAN.001", "RALLYE 2026"),
                      ("MAN.002", "GALA DE PRINTEMPS"), ("SOC.001", "BOURSES D'ETUDES")):
        CodeAnalytique.objects.create(code=code, axe=2, libelle=lib)
    for p, axe, lib in (("GEN.", 2, "Général"), ("MAN.", 2, "Manifestations"), ("SOC.", 2, "Social"), ("COT.", 1, "Cotisations")):
        Prefixe.objects.create(prefixe=p, axe=axe, libelle=lib)
    comptes = [("110000", "REPORT A NOUVEAU", "BIL.4"), ("401000", "FOURNISSEURS DIVERS", "BIL.4"),
               ("512000", "MIZRAHI COMPTE COURANT", "BIL.5"), ("512100", "MIZRAHI EPARGNE", "BIL.5"), ("512200", "BIT", "BIL.5"),
               ("530000", "CAISSE", "BIL.5"), ("580000", "VIREMENTS INTERNES", "BIL.5"), ("470000", "COMPTE D'ATTENTE", "BIL.4"),
               ("600000", "ACHATS DIVERS", "FON.1"), ("600100", "FRAIS BANCAIRES", "FON.1"), ("600200", "LOCATION DE SALLE", "MAN.1"),
               ("610000", "TRAITEUR ET ARTISTES", "MAN.1"), ("625000", "DONS VERSES", "FON.1"), ("630000", "AIDES SOCIALES", "FON.1"),
               ("700000", "COTISATIONS", "COT.2"), ("710000", "PARTICIPATIONS AUX MANIFESTATIONS", "MAN.1"),
               ("720000", "AUTRES RECETTES", "FON.1"), ("725000", "DONS RECUS", "FON.1"), ("740000", "SUBVENTIONS", "FON.1"),
               ("750000", "INTERETS", "FON.1")]
    for n, lib, a1 in comptes:
        Compte.objects.create(numero=n, libelle=lib, anal1_id=a1)
    for code, intitule, compte in (("B1", "Mizrahi compte courant", "512000"), ("B2", "Mizrahi épargne", "512100"),
                                   ("B3", "BIT", "512200"), ("CA", "Caisse", "530000"), ("VT", "Ventes", None),
                                   ("HA", "Achats", None), ("OD", "Opérations diverses", None), ("AN", "À-nouveaux", None)):
        Journal.objects.create(code=code, intitule=intitule, compte_id=compte)
    Exercice.objects.create(libelle="2025", debut=dt.date(2025, 1, 1), fin=dt.date(2025, 12, 31), clos=True)
    Exercice.objects.create(libelle="2026", debut=dt.date(2026, 1, 1), fin=dt.date(2026, 12, 31))
    for cle, valeur in (("compte_virement", "580000"), ("compte_attente", "470000"), ("compte_cotisations", "700000")):
        Reglage.objects.update_or_create(cle=cle, defaults={"valeur": valeur})
    moteur.initialiser_parametres()
    fiches.initialiser()

    membre, fournisseur = TypeTiers.objects.get(libelle="Membre"), TypeTiers.objects.get(libelle="Fournisseur")
    tiers = [("411COHEN001", membre, "COHEN", "David", "12 rue Herzl", "4250000", "Netanya", "david.cohen@exemple.org", 500),
             ("411LEVYS001", membre, "LEVY", "Sarah", "3 rue Weizmann", "4340000", "Raanana", "sarah.levy@exemple.org", 500),
             ("411TAIEB001", membre, "TAIEB", "Jeanne", "8 rue Sokolov", "4250000", "Netanya", "jeanne.taieb@exemple.org", 400),
             ("411ATTAL001", membre, "ATTAL", "Michel", "21 rue Bialik", "6100000", "Tel Aviv", "", 400),
             ("401TRAIT001", fournisseur, "TRAITEUR DU PARC", "", "5 rue Allenby", "6100000", "Tel Aviv", "contact@exemple.org", None)]
    for compte, t, nom, prenom, adresse, cp, ville, email, cotisation in tiers:
        Compte.objects.create(numero=compte, libelle=f"{nom} {prenom}".strip().upper(), anal1_id="BIL.4", lettrable=True)
        Membre.objects.create(compte_id=compte, type=t, nom=nom, prenom=prenom, adresse=adresse, code_postal=cp, ville=ville,
                              email=email, telephone="+972 50 000 00 00", date_adhesion=dt.date(2015, 9, 1) if t == membre else None,
                              cotisation=cotisation)
    membres.creer_manquants()

    admin = User.objects.create_user("admin", password=MOT_DE_PASSE, first_name="Jean", last_name="Administrateur")
    donner_role(admin, "Administrateur")
    tresorier = User.objects.create_user("tresorier", password=MOT_DE_PASSE, first_name="Paul", last_name="Trésorier",
                                         email="tresorier@exemple.org")
    donner_role(tresorier, "Trésorier")
    donner_role(User.objects.create_user("bureau", password=MOT_DE_PASSE, first_name="Anne", last_name="Bureau"), "Bureau")
    benevole = User.objects.create_user("sarah", password=MOT_DE_PASSE, first_name="Sarah", last_name="LEVY")
    donner_role(benevole, "Bénévole")
    Membre.objects.filter(compte_id="411LEVYS001").update(utilisateur=benevole)

    mp = {m.libelle: m for m in MoyenPaiement.objects.all()}
    types = {m.type: m for m in ModeleOperation.objects.all()}
    codes = {c.code: c for c in CodeAnalytique.objects.all()}

    def saisir(jour, modele, montant, paiement=None, tiers=None, anal2="GEN.001", vers=None, compte=None):
        op = moteur.Operation(date=jour, modele=types[modele], tiers=Compte.objects.get(pk=tiers) if tiers else None,
                              montant=D(montant), paiement=mp.get(paiement), vers=mp.get(vers), anal2=codes[anal2],
                              compte=Compte.objects.get(pk=compte) if compte else None)
        r = moteur.controler(op)
        if not r.ok:
            raise SystemExit(f"Démonstration : saisie refusée ({modele}) : {r.erreurs}")
        moteur.enregistrer(op, tresorier)

    j = lambda m, d: dt.date(2026, m, d)  # noqa: E731
    from compta.models import Ligne, Mouvement
    an = Mouvement.objects.create(numero=1, date=j(1, 1), journal_id="AN", piece=1, origine="import", commentaire="Soldes d'ouverture")
    for ordre, (compte, debit, credit) in enumerate((("512000", 8000, 0), ("512100", 3000, 0), ("512200", 1200, 0),
                                                     ("530000", 450, 0), ("110000", 0, 12650))):
        Ligne.objects.create(mouvement=an, ordre=ordre, compte_id=compte, libelle="A NOUVEAU", debit=D(debit), credit=D(credit),
                             anal2=codes["GEN.001"])
    for i, (compte, paiement) in enumerate((("411COHEN001", "BIT"), ("411LEVYS001", "Mizrahi compte courant"),
                                            ("411TAIEB001", "BIT"))):
        saisir(j(1, 10 + i), "Cotisation membre", 500 if i < 2 else 400, paiement, compte, "GEN.002")
    saisir(j(1, 20), "Cotisation membre", 400, "Non réglé", "411ATTAL001", "GEN.002")
    saisir(j(2, 3), "Frais bancaires", 25, "Mizrahi compte courant", anal2="GEN.004")
    saisir(j(3, 1), "Frais bancaires", 25, "Mizrahi compte courant", anal2="GEN.004")
    saisir(j(3, 15), "Facture fournisseur", 3200, "Mizrahi compte courant", "401TRAIT001", "MAN.001", compte="610000")
    saisir(j(4, 2), "Virement interne", 2000, "Mizrahi compte courant", anal2="GEN.001", vers="Mizrahi épargne")
    saisir(j(5, 12), "Dépense directe", 850, "BIT", anal2="SOC.001", compte="630000")

    # fiche d'activité remplie par une bénévole, prête à être reportée
    rallye = Fiche.objects.create(type="activite", titre="Rallye 2026", anal2=codes["MAN.001"], statut="transmise")
    rallye.benevoles.add(benevole)
    nat = lambda sens, lib: NatureFiche.objects.get(type_fiche="activite", sens=sens, libelle=lib)  # noqa: E731
    mode = lambda lib: ModeFiche.objects.get(type_fiche="activite", libelle=lib)  # noqa: E731
    for jour, sens, nature, montant, md, qui, personnes in (
            (j(6, 7), "R", "Participation", 240, "Bit", "411COHEN001", 2), (j(6, 7), "R", "Participation", 120, "Espèces", "411TAIEB001", 1),
            (j(6, 7), "R", "Don", 300, "Chèque", "411LEVYS001", None), (j(6, 7), "D", "Location de salle", 450, "Virement", None, None)):
        LigneFiche.objects.create(fiche=rallye, sens=sens, date=jour, nature=nat(sens, nature), montant=D(montant), mode=mode(md),
                                  tiers=Compte.objects.get(pk=qui) if qui else None, autre="" if qui else "Mairie de Netanya",
                                  personnes=personnes, cree_par=benevole)
    t = TiersProvisoire.objects.create(nom="BENSIMON", prenom="Rachel", remarque="Nouvelle participante", cree_par=benevole)
    LigneFiche.objects.create(fiche=rallye, sens="R", date=j(6, 7), nature=nat("R", "Participation"), montant=D(120),
                              mode=mode("Espèces"), provisoire=t, personnes=1, cree_par=benevole)
    gala = Fiche.objects.create(type="activite", titre="Gala de printemps", anal2=codes["MAN.002"])
    gala.benevoles.add(benevole)

    # relevé bancaire téléchargé : deux lignes déjà en compta, trois à passer
    b1 = Journal.objects.get(code="B1")
    ParametreReleve.objects.create(journal=b1, libelle="Mizrahi-Tefahot 732-182029", date_reprise=j(1, 1))
    for hebreu, francais in (("עמלת מסלול", "Frais de forfait"), ("הפקדת שיק", "Remise de chèque"),
                             ("העברה באינטרנט", "Virement internet"), ("ריבית זכות", "Intérêts créditeurs")):
        Traduction.objects.create(cle=Traduction.cle_de(hebreu), hebreu=hebreu, traduction=francais)
    for rang, (jour, operation, montant) in enumerate((
            (j(1, 11), "העברה באינטרנט", 500), (j(2, 3), "עמלת מסלול", -25), (j(3, 2), "עמלת מסלול", -25),
            (j(6, 30), "ריבית זכות", 42),
            (j(7, 9), "הפקדת שיק", 300), (j(7, 14), "משיכת מזומן", -200))):
        LigneReleve.objects.create(journal=b1, date=jour, rang=rang + 1, reference=str(5100 + rang), operation=operation,
                                   montant=D(montant), source="demo.pdf")
    from compta import releves
    for l in LigneReleve.objects.filter(journal=b1, date__lt=j(3, 1)):          # déjà passées en compta : reliées
        releves.relier(l, releves.deja_en_compta(l)[0], tresorier)
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
        if "justificatifs" not in vieux.name:            # captures des justificatifs faites à part (documents joints)
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

        pg = page_de("tresorier")

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
                choisir('modele', 'Cotisation membre'); choisir('tiers', 'ATTAL'); choisir('paiement', 'BIT');
                choisir('anal2', 'GEN.002'); f.querySelector('input[name=montant]').value = '400';
            }""")
            pg.click("button[name=apercu]")
            pg.wait_for_load_state("networkidle")
        photo(pg, "03_saisie", "/saisie/", avant=apercu)
        photo(pg, "04_mouvement", "/mouvement/2/")
        photo(pg, "05_modifier", "/mouvement/2/modifier/")
        photo(pg, "06_codes", "/codes/")
        photo(pg, "07_tiers", "/membres/", hauteur=720)
        photo(pg, "08_fiche_tiers", "/membres/411ATTAL001/", hauteur=720)
        photo(pg, "09_fiches", "/fiches/")
        from compta.models import Fiche
        rallye = Fiche.objects.get(titre="Rallye 2026").pk
        photo(pg, "10_fiche_benevole", f"/fiches/{rallye}/", hauteur=760)
        photo(pg, "11_journal", "/journaux/?journal=B1&du=2026-01-01&au=2026-12-31", hauteur=760)
        photo(pg, "12_ecritures", "/ecritures/", hauteur=720)
        photo(pg, "13_banque", "/rapprochement/B1/", hauteur=760)
        photo(pg, "14_mon_compte", "/mon-compte/", hauteur=620)
        photo(pg, "15_etats", "/etats/", hauteur=760)
        photo(pg, "16_cloture", "/cloture/", hauteur=760)
        photo(pg, "18_controles", "/controles/", hauteur=720)
        photo(pg, "19_historique", "/modifications/", hauteur=620)
        contexte.clear_cookies()

        pg = page_de("admin")
        photo(pg, "17_base", "/base/", hauteur=760)
        photo(pg, "21_utilisateurs", "/utilisateurs/")
        photo(pg, "22_echanges", "/echanges/", hauteur=760)
        photo(pg, "23_menu_editions", "/", hauteur=420, avant=menu("Éditions"))
        contexte.clear_cookies()

        pg = page_de("sarah")
        photo(pg, "20_benevole", f"/fiches/{Fiche.objects.get(titre='Gala de printemps').pk}/", hauteur=720)
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
            '<span>ComptaBB – {titre} – version du {date}</span><span><span class="pageNumber"></span> / '
            '<span class="totalPages"></span></span></div>')
    with sync_playwright() as p:
        navigateur = p.chromium.launch(**chromium())
        for source, (titre, pdf) in DOCUMENTS.items():
            pg = navigateur.new_page()
            pg.goto((DOCS / source).as_uri())
            pg.wait_for_load_state("networkidle")
            pg.pdf(path=str(SORTIE / pdf), format="A4", print_background=True, prefer_css_page_size=True,
                   display_header_footer=True, header_template="<span></span>",
                   footer_template=pied.format(titre=titre, date=f"{dt.date.today():%d/%m/%Y}"))
            print(f"  {SORTIE / pdf}")
        navigateur.close()


def main():
    dossier = Path(tempfile.mkdtemp(prefix="comptabb-doc-"))
    preparer_django(dossier)
    if "--sans-captures" not in sys.argv:
        demonstration()
        port = port_libre()
        env = dict(os.environ, COMPTABB_DATA=str(dossier), COMPTABB_IMPORTS=str(dossier / "Imports"),
                   COMPTABB_EXPORTS=str(dossier / "Exports"))
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
