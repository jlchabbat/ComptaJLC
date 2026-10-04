"""Fiche papier (PDF) : remplace la saisie en ligne ; remise par le trésorier, remplissable à l'écran ou à la main."""

import io

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from .models import ModeFiche, NatureFiche

LIGNES = 12
GRIS, BLANC = Color(.6, .6, .6), Color(1, 1, 1)


def _champ(c, nom, x, y, l, h, **k):
    c.acroForm.textfield(name=nom, x=x, y=y, width=l, height=h, borderWidth=0.6, fontSize=8, forceBorder=True,
                         borderColor=GRIS, fillColor=BLANC, **k)


def _liste(c, nom, x, y, l, h, options):
    c.acroForm.choice(name=nom, x=x, y=y, width=l, height=h, options=[" "] + options, value=[" "], fieldFlags="combo",
                      borderWidth=0.6, fontSize=8, forceBorder=True, borderColor=GRIS, fillColor=BLANC)


def pdf(fiche):
    """PDF A4 paysage d'une fiche : en-tête, puis une grille de lignes pour les recettes et pour les dépenses."""
    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, pagesize=landscape(A4))
    L, H = landscape(A4)
    activite = fiche.type == "activite"
    colonnes = [("Date", 55), ("Qui (nom, prénom)", 150), ("Nature", 125), ("Montant", 60), ("Mode", 85)]
    colonnes.append(("Pers.", 30) if activite else ("", 0))
    colonnes.append(("Justificatif (n°)", 0) if not activite else ("", 0))
    colonnes = [x for x in colonnes if x[1]]
    reste = L - 60 - sum(w for _, w in colonnes)
    colonnes.append(("Remarque", reste))
    for sens, titre in (("R", "Recettes" if activite else "Dons et aides reçus"), ("D", "Dépenses" if activite else "Dons et aides versés")):
        natures = [n.libelle for n in NatureFiche.objects.filter(type_fiche=fiche.type, sens=sens)]
        modes = [m.libelle for m in ModeFiche.objects.filter(type_fiche=fiche.type, sens__in=(sens, "*"))]
        c.setFont("Helvetica-Bold", 13)
        c.drawString(30, H - 34, f"{fiche.titre} — {titre}")
        c.setFont("Helvetica", 8)
        axe = f" · code axe 2 : {fiche.anal2_id}" if activite and fiche.anal2_id else ""
        c.drawString(30, H - 48, f"{fiche.get_type_display()}{axe} · bénévoles : "
                     + (", ".join(u.get_full_name() or u.username for u in fiche.benevoles.all()) or "—")
                     + " · à remettre au trésorier avec les justificatifs.")
        x, haut = 30, 22
        y = H - 80
        c.setFont("Helvetica-Bold", 8)
        for lib, w in colonnes:
            c.drawString(x + 2, y + haut - 12, lib)
            x += w
        for i in range(LIGNES):
            x, y = 30, H - 80 - (i + 1) * haut
            for lib, w in colonnes:
                nom = f"{sens}{i + 1}_{lib.split()[0].lower() if lib else 'x'}"
                if lib == "Nature":
                    _liste(c, nom, x, y, w - 2, haut - 3, natures)
                elif lib == "Mode":
                    _liste(c, nom, x, y, w - 2, haut - 3, modes)
                else:
                    _champ(c, nom, x, y, w - 2, haut - 3)
                x += w
        c.showPage()
    c.save()
    return tampon.getvalue()
