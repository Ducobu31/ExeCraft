#!/usr/bin/env python3
"""
Convertisseur Python/HTML -> EXE
=================================

Interface graphique simple permettant de transformer :
  - un script Python (.py)          -> exécutable .exe autonome (PyInstaller)
  - une page HTML (.html/.htm)      -> application de bureau .exe (pywebview + PyInstaller)

IMPORTANT : ce script doit être exécuté sous Windows pour produire un .exe Windows.
PyInstaller compile toujours pour le système sur lequel il est lancé.

Dépendances (installées automatiquement si absentes) :
  pip install pyinstaller pywebview
"""

import os
import sys
import shutil
import subprocess
import threading
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


WRAPPER_TEMPLATE = '''\
import sys
import os
import multiprocessing
import webview


def resource_path(relative_path):
    """Trouve le chemin d'une ressource, que le script tourne
    normalement ou soit packagé en exe par PyInstaller (--onefile)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


if __name__ == "__main__":
    # OBLIGATOIRE avec PyInstaller --onefile + pywebview sur Windows :
    # sans cet appel, l'exe relance une nouvelle instance de lui-même
    # en boucle a l'ouverture.
    multiprocessing.freeze_support()

    html_file = resource_path("{html_name}")
    webview.create_window("{window_title}", html_file, width=1000, height=700)
    webview.start()
'''

# Injecté au tout début de chaque script .py avant compilation. Corrige le
# bug très courant "l'exe s'ouvre en boucle" causé par PyInstaller --onefile
# combiné à multiprocessing/threading/certaines librairies GUI sur Windows.
FREEZE_SUPPORT_HEADER = (
    "import multiprocessing as _freeze_support_helper\n"
    "_freeze_support_helper.freeze_support()\n"
    "del _freeze_support_helper\n\n"
)


# Extensions de fichiers considérées comme des ressources web liées au HTML
# (css, js, images, polices, médias). On ne copie QUE celles-ci pour éviter
# de recopier tout un dossier (ex: Téléchargements avec des centaines de
# fichiers sans rapport), ce qui peut planter sur Windows (chemins trop
# longs, fichiers verrouillés -> WinError 3).
WEB_RESOURCE_EXTENSIONS = {
    ".css", ".js", ".mjs", ".json",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".wav", ".ogg", ".webm",
}


def get_downloads_dir():
    """Retourne le dossier Téléchargements/Downloads de l'utilisateur.
    Sous Windows, le dossier physique s'appelle "Downloads" même sur un
    système en français (seul le nom affiché dans l'explorateur change)."""
    home = os.path.expanduser("~")
    downloads = os.path.join(home, "Downloads")
    if os.path.isdir(downloads):
        return downloads
    # Repli si jamais le dossier n'existe pas encore
    os.makedirs(downloads, exist_ok=True)
    return downloads


class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Convertisseur Python / HTML -> EXE")
        self.root.geometry("640x480")
        self.root.resizable(False, False)

        self.file_path = tk.StringVar()
        self.app_name = tk.StringVar(value="MonApplication")
        self.console_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._check_dependencies_async()

    # ---------------------------------------------------------- UI ----
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        frame_top = tk.Frame(self.root)
        frame_top.pack(fill="x", **pad)

        tk.Label(frame_top, text="Fichier source (.py ou .html) :").pack(anchor="w")
        row = tk.Frame(frame_top)
        row.pack(fill="x", pady=4)
        tk.Entry(row, textvariable=self.file_path).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Parcourir...", command=self.browse_file).pack(side="left", padx=6)

        frame_opts = tk.Frame(self.root)
        frame_opts.pack(fill="x", **pad)

        tk.Label(frame_opts, text="Nom de l'application (nom du .exe) :").pack(anchor="w")
        tk.Entry(frame_opts, textvariable=self.app_name).pack(fill="x", pady=4)

        tk.Checkbutton(
            frame_opts,
            text="Afficher une console (utile pour déboguer)",
            variable=self.console_var,
        ).pack(anchor="w", pady=2)

        tk.Button(
            self.root,
            text="Convertir en EXE",
            command=self.start_conversion,
            bg="#2d6cdf",
            fg="white",
            height=2,
        ).pack(fill="x", padx=10, pady=10)

        tk.Label(self.root, text="Journal :").pack(anchor="w", padx=10)
        self.log = scrolledtext.ScrolledText(self.root, height=14, state="disabled")
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ------------------------------------------------------ helpers ----
    def log_msg(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Choisir un fichier .py ou .html",
            filetypes=[
                ("Python ou HTML", "*.py *.html *.htm"),
                ("Python", "*.py"),
                ("HTML", "*.html *.htm"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if path:
            self.file_path.set(path)
            base = os.path.splitext(os.path.basename(path))[0]
            self.app_name.set(base)

    def _check_dependencies_async(self):
        threading.Thread(target=self._check_dependencies, daemon=True).start()

    def _check_dependencies(self):
        self.log_msg("Vérification des dépendances (pyinstaller, pywebview)...")
        missing = []
        for pkg, import_name in (("pyinstaller", "PyInstaller"), ("pywebview", "webview")):
            try:
                __import__(import_name)
            except ImportError:
                missing.append(pkg)
        if missing:
            self.log_msg(f"Modules manquants : {', '.join(missing)}. Installation en cours...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", *missing],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.log_msg("Dépendances installées avec succès.")
            except subprocess.CalledProcessError as e:
                self.log_msg("Échec de l'installation automatique. Installe manuellement :")
                self.log_msg("    pip install pyinstaller pywebview")
                self.log_msg(e.stderr or str(e))
        else:
            self.log_msg("Toutes les dépendances sont présentes.")

    # -------------------------------------------------- conversion ----
    def start_conversion(self):
        path = self.file_path.get().strip()
        # Si le chemin a été collé depuis "Copier en tant que chemin d'accès"
        # (Windows) ou tapé avec des guillemets autour, on les retire, sinon
        # os.path.isfile ne trouve jamais le fichier même si le chemin est
        # correct.
        if len(path) >= 2 and path[0] == path[-1] and path[0] in ("\"", "'"):
            path = path[1:-1].strip()
        self.file_path.set(path)

        if not path:
            messagebox.showerror("Erreur", "Sélectionne un fichier .py ou .html valide.")
            return
        if not os.path.isfile(path):
            messagebox.showerror(
                "Fichier introuvable",
                "Le chemin suivant ne correspond à aucun fichier :\n\n"
                f"{path}\n\n"
                "Vérifie qu'il n'y a pas de faute de frappe, que le fichier "
                "n'a pas été déplacé/renommé, et utilise de préférence le "
                "bouton \"Parcourir...\" plutôt que de coller le chemin à la main.",
            )
            return
        name = self.app_name.get().strip() or "MonApplication"
        threading.Thread(target=self.run_conversion, args=(path, name), daemon=True).start()

    def run_conversion(self, path, app_name):
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".py":
                self.convert_python(path, app_name)
            elif ext in (".html", ".htm"):
                self.convert_html(path, app_name)
            else:
                self.log_msg(f"Extension non supportée : {ext}")
                return
        except Exception as exc:  # pragma: no cover
            self.log_msg(f"ERREUR : {exc}")
            messagebox.showerror("Erreur", str(exc))
            return

        self.log_msg("=" * 50)
        self.log_msg("Terminé ! Regarde le message ci-dessus pour l'emplacement exact de l'exécutable.")
        messagebox.showinfo(
            "Terminé", f"Conversion terminée. Dossier créé : '{app_name}' (voir le journal pour le chemin complet)."
        )

    def convert_python(self, py_path, app_name):
        self.log_msg(f"Conversion du script Python : {py_path}")
        py_path = os.path.abspath(py_path)
        source_dir = os.path.dirname(py_path)
        original_name = os.path.basename(py_path)

        work_dir = tempfile.mkdtemp(prefix="py2exe_")

        # On copie le script dans un dossier temporaire en lui ajoutant
        # l'en-tête freeze_support (corrige le bug d'ouverture en boucle),
        # sans jamais toucher au fichier original de l'utilisateur.
        with open(py_path, "r", encoding="utf-8", errors="ignore") as f:
            original_code = f.read()
        patched_path = os.path.join(work_dir, original_name)
        with open(patched_path, "w", encoding="utf-8") as f:
            f.write(FREEZE_SUPPORT_HEADER + original_code)

        # Si le script importe d'autres fichiers du même dossier, on les
        # copie aussi pour que PyInstaller puisse les trouver (uniquement
        # des fichiers Python/données courants, pas tout le dossier).
        allowed_ext = {".py", ".json", ".txt", ".ini", ".cfg"} | WEB_RESOURCE_EXTENSIONS
        for fname in os.listdir(source_dir):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in allowed_ext:
                continue
            src = os.path.join(source_dir, fname)
            dst = os.path.join(work_dir, fname)
            if os.path.isfile(src) and fname != original_name and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except OSError as e:
                    self.log_msg(f"Ignoré (impossible de copier) : {fname} ({e})")

        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name", app_name,
            patched_path,
        ]
        if not self.console_var.get():
            cmd.insert(-1, "--noconsole")

        self._run_pyinstaller(cmd, work_dir)
        self._collect_result(work_dir, source_dir, app_name)

    def convert_html(self, html_path, app_name):
        self.log_msg(f"Conversion de la page HTML : {html_path}")
        html_path = os.path.abspath(html_path)
        html_dir = os.path.dirname(html_path)
        html_name = os.path.basename(html_path)

        work_dir = tempfile.mkdtemp(prefix="html2exe_")
        local_html = os.path.join(work_dir, html_name)
        shutil.copy2(html_path, local_html)

        # Copie uniquement les ressources web du même dossier (css, js,
        # images, polices, médias) — pas n'importe quel fichier présent
        # dans ce dossier (ex: Téléchargements peut contenir des centaines
        # de fichiers sans rapport).
        for fname in os.listdir(html_dir):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in WEB_RESOURCE_EXTENSIONS:
                continue
            src = os.path.join(html_dir, fname)
            dst = os.path.join(work_dir, fname)
            if os.path.isfile(src) and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except OSError as e:
                    # On ignore un fichier problématique (chemin trop long,
                    # verrouillé, etc.) plutôt que de faire échouer toute
                    # la conversion.
                    self.log_msg(f"Ignoré (impossible de copier) : {fname} ({e})")

        wrapper_path = os.path.join(work_dir, "wrapper.py")
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(WRAPPER_TEMPLATE.format(html_name=html_name, window_title=app_name))

        sep = ";" if os.name == "nt" else ":"
        add_data = f"{work_dir}{sep}."

        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name", app_name,
            "--add-data", add_data,
            wrapper_path,
        ]
        if not self.console_var.get():
            cmd.insert(-1, "--noconsole")

        self._run_pyinstaller(cmd, work_dir)

        # Le résultat va dans Téléchargements/<NomApplication EXE>, pas à
        # côté du HTML source.
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self._collect_result(work_dir, downloads_dir, app_name, folder_name=f"{app_name} EXE")

    def _collect_result(self, work_dir, base_dir, app_name, folder_name=None):
        """Copie uniquement le .exe final dans un dossier dédié (nommé
        d'après l'application, éventuellement avec un suffixe), pour ne
        rien mélanger avec les fichiers temporaires de build."""
        exe_name = app_name + (".exe" if os.name == "nt" else "")
        dist_exe = os.path.join(work_dir, "dist", exe_name)

        final_dir = os.path.join(base_dir, folder_name or app_name)
        os.makedirs(final_dir, exist_ok=True)

        if os.path.isfile(dist_exe):
            shutil.copy2(dist_exe, os.path.join(final_dir, exe_name))
            self.log_msg(f"Exécutable copié dans : {final_dir}")
        else:
            self.log_msg(
                "ATTENTION : l'exécutable n'a pas été trouvé après la compilation. "
                "Regarde les messages ci-dessus pour l'erreur PyInstaller."
            )

        # Nettoyage du dossier temporaire de build (build/, spec, sources copiées)
        shutil.rmtree(work_dir, ignore_errors=True)

    def _run_pyinstaller(self, cmd, work_dir):
        self.log_msg("Commande : " + " ".join(cmd))
        process = subprocess.Popen(
            cmd,
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in process.stdout:
            self.log_msg(line.rstrip())
        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"PyInstaller a échoué (code {process.returncode}).")


def main():
    # Garde-fou : cet outil orchestre lui-même des appels à python/pip/
    # PyInstaller via sys.executable. S'il est un jour figé en .exe,
    # sys.executable pointe vers l'exe lui-même, ce qui le relance en
    # boucle infinie. On bloque donc proprement ce cas au démarrage.
    if getattr(sys, "frozen", False):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Utilisation incorrecte",
            "Ce convertisseur ne doit pas être figé en .exe : il a besoin "
            "d'un Python, pip et PyInstaller fonctionnels sur la machine "
            "pour convertir d'autres fichiers.\n\n"
            "Lance-le avec : python app.py",
        )
        sys.exit(1)

    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
