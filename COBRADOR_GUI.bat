@echo off
cd /d "%~dp0"
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" main.py
if %errorlevel% neq 0 (
    echo.
    echo Error al iniciar la aplicacion. Presiona una tecla para cerrar.
    pause >nul
)
