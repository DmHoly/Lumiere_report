@echo off
setlocal
title Lumiere Report Builder

rem Se placer dans le dossier du script, quel que soit l'endroit d'où il est lancé
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python est introuvable dans le PATH.
    echo Installe Python 3.10+ depuis https://www.python.org/downloads/ ^(coche "Add python.exe to PATH"^) puis relance ce script.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [Lumiere Report] Premier lancement : creation de l'environnement virtuel .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERREUR] La creation de l'environnement virtuel a echoue.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo [Lumiere Report] Verification des dependances ^(peut prendre une minute au premier lancement^)...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ERREUR] L'installation des dependances a echoue. Voir le message ci-dessus.
    pause
    exit /b 1
)

echo.
echo [Lumiere Report] Demarrage du serveur sur http://127.0.0.1:8420
echo [Lumiere Report] Laisse cette fenetre ouverte tant que tu utilises l'outil.
echo [Lumiere Report] Ferme la fenetre ^(ou Ctrl+C^) pour arreter le serveur.
echo.

start "" /min "%~dp0_open_browser.bat"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8420

echo.
echo [Lumiere Report] Serveur arrete.
pause
