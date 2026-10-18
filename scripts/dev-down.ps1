<#
.SYNOPSIS
    Detiene el entorno local de desarrollo del ERP: la API (uvicorn) y PostgreSQL embebido.

.DESCRIPTION
    Contraparte de scripts\dev-up.ps1. Detiene la API arrancada por dev-up (o cualquier uvicorn de
    app.main:app que escuche en el puerto de la API) y luego PostgreSQL con un apagado limpio
    (pg_ctl stop -m fast), para que el clúster quede consistente.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\dev-down.ps1
#>
# Sin [CmdletBinding()]: en PowerShell 5.1 con modo de lenguaje restringido (WDAC/AppLocker) un script
# avanzado invocado con -File falla con DotSourceNotSupported.
param(
    [string]$PgHome,
    [int]$ApiPort = 8000,
    # Detiene solo PostgreSQL y deja la API como esté.
    [switch]$DbOnly
)

$ErrorActionPreference = 'Stop'

if (-not $PgHome) {
    $PgHome = if ($env:ERP_PG_HOME) { $env:ERP_PG_HOME } else { Join-Path $env:LOCALAPPDATA 'DatasysERP\pg' }
}

$pgCtl  = Join-Path $PgHome 'pginstall\bin\pg_ctl.exe'
$pgData = Join-Path $PgHome 'data'
$apiPid = Join-Path (Split-Path -Parent $PgHome) 'api.pid'

function Write-Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Test-PgRunning {
    # pg_ctl status devuelve 0 si el servidor corre; con EAP=Stop, PowerShell 5.1 convertiría su stderr en error.
    $ErrorActionPreference = 'Continue'
    & $pgCtl status -D $pgData *> $null
    $LASTEXITCODE -eq 0
}

function Get-Proc([int]$id) { if ($id) { Get-CimInstance Win32_Process -Filter "ProcessId=$id" } }

function Test-Uvicorn($proc) { $proc -and $proc.CommandLine -match 'uvicorn' -and $proc.CommandLine -match 'app\.main:app' }

# El proceso que escucha puede ser hijo de uvicorn: el python.exe del .venv relanza el intérprete base
# y, con --reload, el servidor es un proceso multiprocessing del recargador. Se busca el ancestro uvicorn
# más alto para que taskkill /T se lleve el árbol completo; $null si ninguno es uvicorn del ERP.
function Get-UvicornRoot($proc) {
    $root = $null
    for ($i = 0; $proc -and $i -lt 4; $i++) {
        if (Test-Uvicorn $proc) { $root = $proc }
        $proc = Get-Proc $proc.ParentProcessId
    }
    $root
}

if (-not $DbOnly) {
    Write-Step "API (puerto $ApiPort)"
    $targets = @()
    if (Test-Path $apiPid) {
        $proc = Get-Proc ([int](Get-Content $apiPid -TotalCount 1))
        if (Test-Uvicorn $proc) { $targets += $proc }
    }
    $conn = Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        $root = Get-UvicornRoot (Get-Proc $conn.OwningProcess)
        if ($root) {
            $targets += $root
        } else {
            Write-Warning "El puerto $ApiPort lo usa PID $($conn.OwningProcess), que no es uvicorn del ERP; no se toca."
        }
    }
    $ids = $targets | ForEach-Object { $_.ProcessId } | Sort-Object -Unique
    if ($ids) {
        foreach ($id in $ids) { & taskkill.exe /T /F /PID $id | Out-Null }
        Write-Host "Detenida (PID $($ids -join ', '))."
    } else {
        Write-Host "No estaba corriendo."
    }
    Remove-Item $apiPid -ErrorAction SilentlyContinue
}

Write-Step "PostgreSQL ($pgData)"
if (-not (Test-Path $pgCtl)) { Write-Host "No se encontró $pgCtl; nada que detener."; exit 0 }
if (-not (Test-PgRunning)) {
    Write-Host "No estaba corriendo."
} else {
    & $pgCtl stop -D $pgData -m fast -w -t 60
    if ($LASTEXITCODE -ne 0) { Write-Host "pg_ctl stop falló; revise $PgHome\pg.log" -ForegroundColor Red; exit 1 }
}
