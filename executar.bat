@echo off
setlocal
cd /d "%~dp0"

set "CONDA_BAT=C:\ProgramData\anaconda3\condabin\conda.bat"

echo =========================================
echo Iniciando sistema FUNDEF
echo Pasta: %CD%
echo =========================================
echo.

if exist "%CONDA_BAT%" (
    echo [1/3] Tentando Conda base...
    call "%CONDA_BAT%" run --no-capture-output -n base python -u app.py
    set "RC=%ERRORLEVEL%"
    if "%RC%"=="0" goto :success
    echo [ERRO] Falha ao executar com Conda. Codigo %RC%.
) else (
    echo [INFO] Conda nao encontrado em "%CONDA_BAT%".
)

if exist ".venv\Scripts\python.exe" (
    echo [2/3] Tentando ambiente virtual local .venv...
    ".venv\Scripts\python.exe" -u app.py
    set "RC=%ERRORLEVEL%"
    if "%RC%"=="0" goto :success
    echo [ERRO] Falha ao executar com .venv. Codigo %RC%.
) else (
    echo [INFO] .venv nao encontrado.
)

echo [3/3] Tentando Python do sistema...
py -u app.py
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" goto :success

echo [ERRO] Falha ao executar com py. Codigo %RC%.
echo.
echo Verifique se Python/Conda estao instalados e se as dependencias estao ok:
echo   py -m pip install -r requirements.txt
goto :end_fail

:success
echo.
echo Aplicacao encerrada normalmente.
pause
exit /b 0

:end_fail
echo.
echo O processo terminou com erro.
pause
exit /b %RC%
