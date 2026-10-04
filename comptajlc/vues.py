import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from .models import (Axe, CodeAnalytique, Compte, Ecriture, Journal, Ligne,
                     LigneAnalytique, db)

bp = Blueprint("compta", __name__)


def fmt_montant(c):
    """Centimes -> « 1 234,50 »."""
    s = f"{abs(c or 0) / 100:,.2f}".replace(",", " ").replace(".", ",")
    return ("-" if (c or 0) < 0 else "") + s


def en_centimes(texte):
    texte = (texte or "").strip().replace(" ", "").replace(",", ".")
    if not texte:
        return 0
    try:
        return int((Decimal(texte) * 100).to_integral_value())
    except InvalidOperation:
        raise ValueError(f"Montant invalide : « {texte} »")


@bp.route("/")
def accueil():
    return render_template("accueil.html", nb=Ecriture.query.count())


# ---------- Plan comptable ----------

@bp.route("/plan", methods=["GET", "POST"])
def plan():
    if request.method == "POST":
        numero = request.form["numero"].strip()
        libelle = request.form["libelle"].strip()
        if not numero.isdigit() or not libelle:
            flash("Numéro (chiffres) et libellé obligatoires.", "erreur")
        elif db.session.get(Compte, numero):
            flash("Ce compte existe déjà.", "erreur")
        else:
            db.session.add(Compte(numero=numero, libelle=libelle))
            db.session.commit()
            flash("Compte ajouté.", "ok")
        return redirect(url_for("compta.plan"))
    return render_template("plan.html", comptes=Compte.query.order_by(Compte.numero).all())


@bp.post("/plan/<numero>/modifier")
def plan_modifier(numero):
    c = db.get_or_404(Compte, numero)
    libelle = request.form["libelle"].strip()
    if libelle:
        c.libelle = libelle
        db.session.commit()
        flash("Libellé modifié.", "ok")
    return redirect(url_for("compta.plan"))


@bp.post("/plan/<numero>/supprimer")
def plan_supprimer(numero):
    c = db.get_or_404(Compte, numero)
    if Ligne.query.filter_by(compte_numero=numero).first():
        flash("Compte utilisé par des écritures : suppression impossible.", "erreur")
    else:
        db.session.delete(c)
        db.session.commit()
        flash("Compte supprimé.", "ok")
    return redirect(url_for("compta.plan"))


@bp.post("/plan/importer")
def plan_importer():
    """Import CSV « numero;libelle » : ajoute les comptes absents, met à jour les libellés."""
    f = request.files.get("fichier")
    if not f:
        flash("Aucun fichier.", "erreur")
        return redirect(url_for("compta.plan"))
    texte = f.read().decode("utf-8-sig", errors="replace")
    delim = ";" if texte.count(";") >= texte.count(",") else ","
    ajoutes = maj = 0
    for row in csv.reader(io.StringIO(texte), delimiter=delim):
        if len(row) < 2 or not row[0].strip().isdigit():
            continue
        c = db.session.get(Compte, row[0].strip())
        if c:
            c.libelle = row[1].strip()
            maj += 1
        else:
            db.session.add(Compte(numero=row[0].strip(), libelle=row[1].strip()))
            ajoutes += 1
    db.session.commit()
    flash(f"Import terminé : {ajoutes} ajouté(s), {maj} mis à jour.", "ok")
    return redirect(url_for("compta.plan"))


# ---------- Axes et codes analytiques ----------

@bp.route("/axes", methods=["GET", "POST"])
def axes():
    if request.method == "POST":
        nom = request.form["nom"].strip()
        if nom and not Axe.query.filter_by(nom=nom).first():
            db.session.add(Axe(nom=nom))
            db.session.commit()
            flash("Axe ajouté.", "ok")
        else:
            flash("Nom vide ou déjà utilisé.", "erreur")
        return redirect(url_for("compta.axes"))
    return render_template("axes.html", axes=Axe.query.order_by(Axe.id).all())


@bp.post("/axes/<int:axe_id>/renommer")
def axe_renommer(axe_id):
    a = db.get_or_404(Axe, axe_id)
    nom = request.form["nom"].strip()
    if nom:
        a.nom = nom
        db.session.commit()
    return redirect(url_for("compta.axes"))


@bp.post("/axes/<int:axe_id>/codes")
def code_ajouter(axe_id):
    a = db.get_or_404(Axe, axe_id)
    code, libelle = request.form["code"].strip().upper(), request.form["libelle"].strip()
    if not code or not libelle:
        flash("Code et libellé obligatoires.", "erreur")
    elif CodeAnalytique.query.filter_by(axe_id=a.id, code=code).first():
        flash("Ce code existe déjà sur cet axe.", "erreur")
    else:
        db.session.add(CodeAnalytique(axe_id=a.id, code=code, libelle=libelle))
        db.session.commit()
        flash("Code ajouté.", "ok")
    return redirect(url_for("compta.axes"))


@bp.post("/codes/<int:code_id>/supprimer")
def code_supprimer(code_id):
    c = db.get_or_404(CodeAnalytique, code_id)
    if LigneAnalytique.query.filter_by(code_id=c.id).first():
        flash("Code utilisé par des écritures : suppression impossible.", "erreur")
    else:
        db.session.delete(c)
        db.session.commit()
        flash("Code supprimé.", "ok")
    return redirect(url_for("compta.axes"))


# ---------- Journaux ----------

@bp.route("/journaux", methods=["GET", "POST"])
def journaux():
    if request.method == "POST":
        code, libelle = request.form["code"].strip().upper(), request.form["libelle"].strip()
        if code and libelle and not db.session.get(Journal, code):
            db.session.add(Journal(code=code, libelle=libelle))
            db.session.commit()
            flash("Journal ajouté.", "ok")
        else:
            flash("Code vide ou déjà utilisé.", "erreur")
        return redirect(url_for("compta.journaux"))
    return render_template("journaux.html", journaux=Journal.query.order_by(Journal.code).all())


# ---------- Saisie ----------

@bp.route("/saisie", methods=["GET", "POST"])
def saisie():
    axes_ = Axe.query.order_by(Axe.id).all()
    ctx = dict(journaux=Journal.query.all(), comptes=Compte.query.order_by(Compte.numero).all(),
               axes=axes_, aujourdhui=date.today().isoformat(), nb_lignes=6)
    if request.method == "GET":
        return render_template("saisie.html", **ctx)

    f = request.form
    try:
        d = datetime.strptime(f["date"], "%Y-%m-%d").date()
        if not f["libelle"].strip():
            raise ValueError("Libellé obligatoire.")
        if not db.session.get(Journal, f["journal"]):
            raise ValueError("Journal inconnu.")
        lignes = []
        for i in range(ctx["nb_lignes"]):
            num = f.get(f"compte{i}", "").strip()
            deb, cre = en_centimes(f.get(f"debit{i}")), en_centimes(f.get(f"credit{i}"))
            if not num and not deb and not cre:
                continue
            if not db.session.get(Compte, num):
                raise ValueError(f"Ligne {i + 1} : compte « {num} » introuvable.")
            if (deb and cre) or not (deb or cre) or deb < 0 or cre < 0:
                raise ValueError(f"Ligne {i + 1} : un montant positif au débit OU au crédit.")
            codes = []
            for a in axes_:
                cid = f.get(f"axe{a.id}_{i}", "")
                if cid:
                    c = db.session.get(CodeAnalytique, int(cid))
                    if not c or c.axe_id != a.id:
                        raise ValueError(f"Ligne {i + 1} : code analytique invalide.")
                    codes.append(c)
            lignes.append((num, deb, cre, codes))
        if len(lignes) < 2:
            raise ValueError("Au moins deux lignes.")
        if sum(l[1] for l in lignes) != sum(l[2] for l in lignes):
            raise ValueError("Écriture non équilibrée : total débit ≠ total crédit.")
    except ValueError as e:
        flash(str(e), "erreur")
        return render_template("saisie.html", **ctx), 400

    mvt = (db.session.query(func.max(Ecriture.mvt)).scalar() or 0) + 1
    e = Ecriture(mvt=mvt, date=d, journal_code=f["journal"], piece=f.get("piece", "").strip(),
                 libelle=f["libelle"].strip())
    for num, deb, cre, codes in lignes:
        l = Ligne(compte_numero=num, debit=deb, credit=cre)
        l.analytiques = [LigneAnalytique(code_id=c.id) for c in codes]
        e.lignes.append(l)
    db.session.add(e)
    db.session.commit()
    flash(f"Écriture n° {mvt} enregistrée.", "ok")
    return redirect(url_for("compta.saisie"))


# ---------- États ----------

@bp.route("/journal")
def journal():
    return render_template("journal.html", ecritures=Ecriture.query.order_by(Ecriture.date, Ecriture.mvt).all())


@bp.route("/balance")
def balance():
    rows = (db.session.query(Ligne.compte_numero, Compte.libelle, func.sum(Ligne.debit), func.sum(Ligne.credit))
            .join(Compte).group_by(Ligne.compte_numero).order_by(Ligne.compte_numero).all())
    return render_template("balance.html", rows=rows,
                           td=sum(r[2] for r in rows), tc=sum(r[3] for r in rows))


@bp.route("/grand-livre/<numero>")
def grand_livre(numero):
    c = db.get_or_404(Compte, numero)
    lignes = (Ligne.query.filter_by(compte_numero=numero).join(Ecriture)
              .order_by(Ecriture.date, Ecriture.mvt).all())
    return render_template("grand_livre.html", compte=c, lignes=lignes)


@bp.route("/analytique/<int:axe_id>")
def analytique(axe_id):
    a = db.get_or_404(Axe, axe_id)
    rows = (db.session.query(CodeAnalytique.code, CodeAnalytique.libelle,
                             func.sum(Ligne.debit), func.sum(Ligne.credit))
            .join(LigneAnalytique, LigneAnalytique.code_id == CodeAnalytique.id)
            .join(Ligne, Ligne.id == LigneAnalytique.ligne_id)
            .filter(CodeAnalytique.axe_id == a.id).group_by(CodeAnalytique.id)
            .order_by(CodeAnalytique.code).all())
    return render_template("analytique.html", axe=a, rows=rows)
