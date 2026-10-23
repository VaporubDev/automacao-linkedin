@echo off
title GitPost - GitHub para LinkedIn

IF NOT EXIST "venv\Scripts\python.exe" (
    echo [1/2] Criando ambiente virtual Python...
    python -m venv venv
    echo [2/2] Instalando dependencias...
    .\venv\Scripts\pip install -r requirements.txt
)

echo Abrindo o servidor local...
echo Painel Web: http://localhost:8000
echo.
.\venv\Scripts\python main.py
pause
