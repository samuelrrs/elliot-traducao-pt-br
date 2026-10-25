@echo off
chcp 65001 >nul
setlocal DisableDelayedExpansion
title Aplicar traducao Elliot
echo.
echo === Traducao Elliot ===
echo.

set "ALVO=%~1"
if defined ALVO goto temalvo

echo Arraste a pasta PPSA32193-app0 em cima deste arquivo.
echo Ou cole o caminho dela abaixo.
set /p "ALVO=Pasta app0: "
if defined ALVO goto temalvo

echo Nenhuma pasta informada.
goto fim

:temalvo
echo Alvo: "%ALVO%"
echo.
set "ELLIOT_FROM_BAT=1"

where python >nul 2>&1
if errorlevel 1 goto trypy
python "%~dp0aplicar_traducao.py" "%ALVO%"
goto depois

:trypy
where py >nul 2>&1
if errorlevel 1 goto nopy
py -3 "%~dp0aplicar_traducao.py" "%ALVO%"
goto depois

:nopy
if exist "%~dp0aplicar_traducao.exe" (
  echo Python nao encontrado, usando o exe.
  "%~dp0aplicar_traducao.exe" "%ALVO%"
  goto depois
)
echo Python 3 nao encontrado e nao achei aplicar_traducao.exe.
echo Instale o Python no PC (python.org) e marque "Add python.exe to PATH".
echo Depois: pip install pycryptodome
goto fim

:depois
if errorlevel 1 goto falhou
echo.
echo Pronto.
goto fim

:falhou
echo.
echo Falhou. Confira o Python, o pycryptodome e a pasta PPSA32193-app0.

:fim
echo.
pause
endlocal
