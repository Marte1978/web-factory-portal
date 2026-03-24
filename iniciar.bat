@echo off
title Web Factory — Portal + Daemon
color 0A
cls

echo ============================================================
echo   WEB FACTORY — Sistema de Prospeccion Automatica
echo ============================================================
echo.

:: Verificar variables de entorno
if "%SUPABASE_SERVICE_ROLE_KEY%"=="" (
    echo [WARN] SUPABASE_SERVICE_ROLE_KEY no esta configurada
    echo        El daemon puede no funcionar correctamente
    echo.
)
if "%APIFY_API_TOKEN%"=="" (
    echo [WARN] APIFY_API_TOKEN no esta configurada
    echo        Los datos de Google Maps no estaran disponibles
    echo.
)

:: Ir al directorio del proyecto
cd /d "C:\Users\Willy\sistema de egocios"

:: Abrir el portal en el navegador (Vercel)
echo [1/2] Abriendo portal en el navegador...
start "" "https://portal-web-factory.vercel.app"
timeout /t 2 /nobreak >nul

:: Iniciar el daemon de investigacion
echo [2/2] Iniciando daemon de investigacion...
echo.
echo ============================================================
echo   DAEMON ACTIVO — Presiona Ctrl+C para detener
echo ============================================================
echo.

python scripts/research_daemon.py

echo.
echo [INFO] Daemon detenido.
pause
