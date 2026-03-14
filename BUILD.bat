@echo off
cd /d "%~dp0"

echo.
echo  Compilando Cobrador de Facturas...
echo  Esto puede tardar 1-3 minutos.
echo.

"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" -m PyInstaller CobradordFacturas.spec --clean

if %errorlevel% neq 0 (
    echo.
    echo  ERROR: la compilacion fallo. Revisa los mensajes arriba.
    pause
    exit /b 1
)

echo.
echo  Compilacion exitosa.
echo  Ejecutable en: dist\CobradordFacturas\CobradordFacturas.exe
echo.
pause
