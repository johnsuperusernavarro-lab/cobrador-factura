@echo off
chcp 65001 >nul
echo ================================================
echo  Compilando Cobrador de Facturas (version web)
echo ================================================
echo.

"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" -m PyInstaller CobradordFacturas_Web.spec --clean -y

echo.
if exist "dist\CobradordFacturas\CobradordFacturas.exe" (
    echo [OK] Compilacion exitosa.
    echo Ejecutable: dist\CobradordFacturas\CobradordFacturas.exe
) else (
    echo [ERROR] No se genero el ejecutable. Revisa los mensajes de arriba.
)
echo.
pause
