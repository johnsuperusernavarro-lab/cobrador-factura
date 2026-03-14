@echo off
chcp 65001 >nul
echo ================================================
echo  Preparar distribucion para tester (version web)
echo ================================================
echo.
echo Esta operacion eliminara la carpeta "data" del dist
echo para que el tester empiece con una instalacion limpia.
echo.
set /p confirm="Continuar? (S/N): "
if /i not "%confirm%"=="S" goto :fin

set DIST=dist\CobradordFacturas

if not exist "%DIST%" (
    echo ERROR: No existe %DIST%. Ejecuta BUILD_WEB.bat primero.
    goto :fin
)

if exist "%DIST%\data" (
    rmdir /s /q "%DIST%\data"
    echo [OK] Carpeta data eliminada.
) else (
    echo [INFO] La carpeta data no existia.
)

echo.
echo Listo. La carpeta "%DIST%" esta lista para comprimir y entregar.
echo El tester debe:
echo   1. Descomprimir la carpeta
echo   2. Doble clic en CobradordFacturas.exe
echo   3. Se abre el navegador automaticamente
echo   4. Ir a Ajustes y configurar sus credenciales

:fin
echo.
pause
