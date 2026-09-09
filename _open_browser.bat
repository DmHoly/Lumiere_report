@echo off
rem Petit utilitaire interne : attend que le serveur soit prêt puis ouvre le
rem navigateur. Appelé par start_report_builder.bat — pas destiné à un lancement direct.
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8420/"
