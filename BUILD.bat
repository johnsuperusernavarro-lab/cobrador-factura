@echo off
cd /d "%~dp0"

echo.
echo  Compilando CONDORNEXUS...
echo  Esto puede tardar 2-4 minutos.
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
echo  Carpeta lista en: dist\CONDORNEXUS\
echo  Ejecutable:       dist\CONDORNEXUS\CONDORNEXUS.exe
echo.
echo  Siguiente paso: ejecuta PREPARAR_PARA_TESTER.bat y luego comprime
echo  la carpeta dist\CONDORNEXUS\ en un ZIP para distribuir.
echo.
pause
