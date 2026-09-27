# PyInstaller : construit ComptaBB.exe (lanceur + application Django).
#   cd appli && pyinstaller build.spec
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

APPLI = Path(SPECPATH).resolve()
sys.path.insert(0, str(APPLI))          # compta et comptabb importables pendant la construction


def fichiers_du_paquet(nom):
    """Gabarits, fichiers statiques et PDF du paquet, listés explicitement (collect_data_files les ignore
    silencieusement quand le paquet n'est pas importable : l'exe démarrait sans ses pages)."""
    racine = APPLI / nom
    return [(str(f), str(f.parent.relative_to(APPLI))) for f in racine.rglob("*")
            if f.is_file() and f.suffix not in (".py", ".pyc") and "__pycache__" not in f.parts]


donnees = fichiers_du_paquet("compta") + collect_data_files("django") + collect_data_files("pdfminer")
if not any(dest == "compta/templates/compta" for _, dest in donnees):
    raise SystemExit("build.spec : gabarits de compta introuvables")
cachees = (collect_submodules("django") + collect_submodules("pdfplumber") + collect_submodules("compta") + collect_submodules("comptabb")
           + ["waitress", "whitenoise", "whitenoise.middleware", "whitenoise.storage", "openpyxl"])

a = Analysis(["lanceur.py"], pathex=["."], datas=donnees, hiddenimports=cachees, excludes=["tkinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ComptaBB", console=True, icon="compta/static/compta/favicon.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="ComptaBB")
