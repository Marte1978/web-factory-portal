# Web Factory — Launcher Script
# Doble clic o: powershell -ExecutionPolicy Bypass -File iniciar.ps1

$Host.UI.RawUI.WindowTitle = "Web Factory — Daemon Activo"
$projectDir = "C:\Users\Willy\sistema de egocios"

function Write-Header {
    Clear-Host
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  WEB FACTORY — Sistema de Prospeccion Automatica" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
}

function Check-EnvVars {
    $ok = $true
    if (-not $env:SUPABASE_SERVICE_ROLE_KEY) {
        Write-Host "[WARN] SUPABASE_SERVICE_ROLE_KEY no configurada" -ForegroundColor Yellow
        $ok = $false
    }
    if (-not $env:NEXT_PUBLIC_SUPABASE_ANON_KEY) {
        Write-Host "[WARN] NEXT_PUBLIC_SUPABASE_ANON_KEY no configurada" -ForegroundColor Yellow
        $ok = $false
    }
    if (-not $env:APIFY_API_TOKEN) {
        Write-Host "[WARN] APIFY_API_TOKEN no configurada (Google Maps desactivado)" -ForegroundColor Yellow
    }
    if ($ok) {
        Write-Host "[OK] Variables de entorno configuradas" -ForegroundColor Green
    }
    Write-Host ""
}

Write-Header
Check-EnvVars

# Opcion: elegir entre portal local o Vercel
Write-Host "Portal:" -ForegroundColor Cyan
Write-Host "  [1] Vercel (https://portal-web-factory.vercel.app) — RECOMENDADO"
Write-Host "  [2] Local  (file:///C:/Users/Willy/sistema de egocios/portal/static/index.html)"
Write-Host ""
$choice = Read-Host "Elige [1/2] (Enter = 1)"

if ($choice -eq "2") {
    $portalUrl = "file:///C:/Users/Willy/sistema%20de%20egocios/portal/static/index.html"
    Write-Host "[INFO] Abriendo portal local..." -ForegroundColor Cyan
} else {
    $portalUrl = "https://portal-web-factory.vercel.app"
    Write-Host "[INFO] Abriendo portal Vercel..." -ForegroundColor Cyan
}

Start-Process $portalUrl
Start-Sleep -Seconds 1

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  DAEMON INICIANDO..." -ForegroundColor Green
Write-Host "  Presiona Ctrl+C para detener" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

Set-Location $projectDir
python scripts/research_daemon.py

Write-Host ""
Write-Host "[INFO] Daemon detenido." -ForegroundColor Yellow
Read-Host "Presiona Enter para cerrar"
