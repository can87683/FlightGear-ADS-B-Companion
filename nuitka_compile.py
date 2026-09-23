#!/usr/bin/env python3
# nuitka_compile.py
# Copyright Su Nie | BSD-3C License | https://github.com/can87683

import sys
import ast
import shutil
import subprocess
from pathlib import Path

class NuitkaCompiler:
    IMPORT_TO_PACKAGE = {
        "cv2": "opencv-python", "PIL": "Pillow", "sklearn": "scikit-learn",
        "yaml": "PyYAML", "bs4": "beautifulsoup4", "attr": "attrs",
        "dateutil": "python-dateutil", "dotenv": "python-dotenv", "jwt": "PyJWT",
        "Crypto": "pycryptodome", "serial": "pyserial", "usb": "pyusb", "wx": "wxPython",
    }

    PROBLEMATIC_PACKAGES = [
        "torch", "tensorflow",
        "keras", "sklearn", "cv2", "bokeh", "plotly", "seaborn", "statsmodels", "xgboost",
        "lightgbm", "catboost", "spacy", "nltk", "transformers", "flask", "django", "fastapi",
        "sqlalchemy", "psycopg2", "pymongo", "redis", "celery", "boto3", "botocore", "awscli",
        "azure", "google.cloud", "grpc", "protobuf", "cryptography", "paramiko", "fabric",
        "ansible", "pytest", "unittest", "nose", "hypothesis", "jupyter", "ipython", "notebook",
        "lab", "sphinx", "mkdocs",
    ]

    SAFE_PIL_EXCLUDES = [
        "PIL._avif", "PIL._webp", "PIL.ImageQt", "PIL._imagingmorph",
        "PIL._imagingmath", "PIL._imagingcms", "PIL._tkinter_finder"
    ]

    DATA_EXTENSIONS = {
        ".csv", ".json", ".xml", ".yaml", ".yml", ".txt", ".ini", ".cfg",
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".ttf", ".otf"
    }

    STDLIB_MODULES = {
        "os", "sys", "math", "json", "csv", "time", "datetime", "threading", "queue",
        "configparser", "logging", "typing", "dataclasses", "socket", "subprocess",
        "shlex", "webbrowser", "ast", "shutil", "pathlib", "io", "re", "collections",
        "itertools", "functools", "abc", "contextlib", "copy", "enum", "hashlib", "hmac",
        "html", "http", "inspect", "keyword", "linecache", "locale", "operator", "pickle",
        "platform", "pprint", "random", "signal", "string", "struct", "tempfile", "textwrap",
        "traceback", "types", "urllib", "uuid", "warnings", "weakref", "xml", "zipfile",
        "zipimport", "PIL"
    }

    def __init__(self, script_path: Path, output_name: str = ""):
        self.script_path = script_path.resolve()
        self.output_name = output_name
        self.root = Path.cwd()
        self.is_win = sys.platform == "win32"

    def scan_imports(self) -> set:
        with open(self.script_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        return imports

    def install_missing(self, imports: set, exclude: set):
        missing = [
            self.IMPORT_TO_PACKAGE.get(imp, imp)
            for imp in imports
            if imp not in self.STDLIB_MODULES and imp not in exclude
        ]

        missing = [pkg for pkg in missing if subprocess.call([sys.executable, "-c", f"import {pkg.split('-')[0]}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0]

        if missing:
            print(f"==> Installing missing packages: {', '.join(missing)}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet"] + missing)

    def detect_gui_plugin(self, imports: set) -> str:
        if "customtkinter" in imports or "tkinter" in imports:
            return "tk-inter"
        if "PyQt6" in imports:
            return "pyqt6"
        if "PyQt5" in imports:
            return "pyqt5"
        if "PySide6" in imports:
            return "pyside6"
        if "PySide2" in imports:
            return "pyside2"
        if "wx" in imports:
            return "wx"
        return ""

    def detect_data_files(self) -> list:
        files = []
        for ext in self.DATA_EXTENSIONS:
            files.extend([f.name for f in self.root.glob(f"*{ext}")])
        return files

    def build(self):
        imports = self.scan_imports()
        print(f"==> Detected imports: {', '.join(sorted(imports)) if imports else 'none'}")

        final_exclude = set(self.PROBLEMATIC_PACKAGES)
        self.install_missing(imports, final_exclude)

        data_files = self.detect_data_files()
        if data_files:
            print(f"==> Data files: {', '.join(data_files)}")

        basename = self.script_path.stem
        if not self.output_name:
            self.output_name = f"{basename}.exe" if self.is_win else basename

        print(f"==> Building: {self.script_path.name} -> dist/{self.output_name}")

        for p in [self.root / f"{basename}.build", self.root / f"{basename}.dist"]:
            if p.exists():
                shutil.rmtree(p)

        cmd = [
            sys.executable, "-m", "nuitka", "--standalone", "--onefile",
            "--assume-yes-for-downloads", "--enable-plugin=anti-bloat",
            "--remove-output"
        ]

        if self.is_win:
            cmd.append("--windows-console-mode=disable")

        gui_plugin = self.detect_gui_plugin(imports)
        if gui_plugin:
            cmd.append(f"--enable-plugin={gui_plugin}")
            print(f"==> Auto-detected GUI plugin: {gui_plugin}")

        if gui_plugin == "tk-inter" and "PIL" in imports:
            cmd.append("--include-module=PIL._imaging")
            cmd.append("--include-module=PIL._imagingtk")
            cmd.append("--include-module=PIL._imagingft")

        for pkg in final_exclude:
            cmd.append(f"--nofollow-import-to={pkg}")

        for exc in self.SAFE_PIL_EXCLUDES:
            cmd.append(f"--nofollow-import-to={exc}")

        for imp in imports:
            if imp not in self.STDLIB_MODULES and imp not in final_exclude and imp != "PIL":
                cmd.append(f"--include-module={imp}")

        for data_file in data_files:
            cmd.append(f"--include-data-files={data_file}={data_file}")

        cmd.extend([
            "--output-dir=dist",
            f"--output-filename={self.output_name}",
            str(self.script_path)
        ])

        print("==> Running Nuitka...")
        subprocess.check_call(cmd)
        print("==> Build successful.")

        binary_path = self.root / "dist" / self.output_name
        if not self.is_win:
            binary_path.chmod(0o755)

        print(f"==> Running {binary_path}...")
        sys.exit(subprocess.call([str(binary_path)]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python nuitka_compile.py <script.py> [output_name]")
        sys.exit(1)

    target_script = Path(sys.argv[1])
    out_name = sys.argv[2] if len(sys.argv) > 2 else ""

    compiler = NuitkaCompiler(target_script, out_name)
    compiler.build()