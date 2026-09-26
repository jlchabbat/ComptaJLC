# PyInstaller : construit ComptaBB.exe (lanceur + application Django).
#   cd appli && pyinstaller build.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

donnees = collect_data_files("compta") + collect_data_files("django") + collect_data_files("pdfminer")
cachees = (collect_submodules("django") + collect_submodules("pdfplumber") + collect_submodules("compta") + collect_submodules("comptabb")
           + ["waitress", "whitenoise", "whitenoise.middleware", "whitenoise.storage", "openpyxl"])

a = Analysis(["lanceur.py"], pathex=["."], datas=donnees, hiddenimports=cachees, excludes=["tkinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ComptaBB", console=True, icon="compta/static/compta/favicon.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="ComptaBB")
