@echo off
cd /d "%~dp0"

echo.
echo  Limpiando datos de sesion anterior del ejecutable...
echo.

set DIST=dist\CobradordFacturas

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
echo  El tester configurara sus propios datos al abrir la app.
echo.
pause
