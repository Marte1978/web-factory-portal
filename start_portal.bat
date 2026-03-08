@echo off
title Web Factory Portal
echo.
echo  ==========================================
echo    WEB FACTORY PORTAL - Iniciando...
echo  ==========================================
echo.
echo  Abre tu navegador en: http://localhost:8000
echo.
cd /d "C:\Users\Willy\sistema de egocios"
py -m uvicorn portal.main:app --host 127.0.0.1 --port 8000 --reload
pause
