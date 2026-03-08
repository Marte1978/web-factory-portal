@echo off
echo.
echo ====================================
echo   Business Machine — Setup
echo ====================================
echo.

:: Crear carpetas necesarias
echo [1/3] Creando estructura de carpetas...
mkdir "C:\Users\Willy\sistema de egocios\transcripts" 2>nul
mkdir "C:\Users\Willy\sistema de egocios\research" 2>nul
mkdir "C:\Users\Willy\sistema de egocios\proposals" 2>nul
mkdir "C:\Users\Willy\sistema de egocios\content" 2>nul
echo     ✓ Carpetas creadas

:: Instalar dependencias del MCP server
echo [2/3] Instalando dependencias del MCP Server...
cd /d "C:\Users\Willy\sistema de egocios\mcp-server"
npm install
echo     ✓ Dependencias instaladas

:: Verificar Node.js
echo [3/3] Verificando Node.js...
node --version >nul 2>&1
if %errorlevel% == 0 (
    echo     ✓ Node.js disponible
) else (
    echo     ✗ Node.js no encontrado. Instala desde https://nodejs.org
    pause
    exit /b 1
)

echo.
echo ====================================
echo   Setup completado exitosamente
echo ====================================
echo.
echo Proximos pasos:
echo   1. Edita PRODUCT_BRIEF.md con tu idea actual
echo   2. Abre Claude Code en esta carpeta
echo   3. Ejecuta /daily para empezar el dia
echo   4. O ejecuta /research para encontrar tu primera idea
echo.
pause
