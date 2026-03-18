@echo off
cd /d "%~dp0"

echo.
echo  Limpiando datos de sesion anterior del ejecutable...
echo.

set DIST=dist\CONDORNEXUS

if exist "%DIST%\data\config.json" (
    del /q "%DIST%\data\config.json"
    echo  - config.json eliminado
)

if exist "%DIST%\data\cobros.db" (
    del /q "%DIST%\data\cobros.db"
    echo  - cobros.db eliminado
)

echo.
echo  Listo. La carpeta "%DIST%" esta limpia para entregar.
echo  Comprime esa carpeta en un ZIP y enviala al tester.
echo  El tester solo descomprime y hace doble clic en CONDORNEXUS.exe
echo.
pause
