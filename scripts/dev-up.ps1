<#
.SYNOPSIS
    Levanta el entorno local de desarrollo del ERP: PostgreSQL 16 embebido y la API FastAPI.

.DESCRIPTION
    Pensado para equipos Windows sin Docker. Usa los binarios de PostgreSQL (los de pgserver) y el
    clúster de datos que viven fuera del repositorio, por defecto en %LOCALAPPDATA%\DatasysERP\pg:

        pginstall\bin\   pg_ctl.exe, postgres.exe, psql.exe ...
        data\            clúster (usuario erp, bases erp y erp_test)
        pg.log           log de PostgreSQL

    Pasos: arranca PostgreSQL si no está corriendo, aplica migraciones (alembic upgrade head),
    arranca uvicorn en segundo plano y espera a que http://127.0.0.1:8000/health/ready responda "ok".
    Las credenciales se leen de .env (no versionado); este script no las toca ni las muestra.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1 -Reload
#>
# Sin [CmdletBinding()]: en PowerShell 5.1 con modo de lenguaje restringido (WDAC/AppLocker) un script
# avanzado invocado con -File falla con DotSourceNotSupported.
param(
    # Carpeta con pginstall\ y data\. También se puede fijar con la variable de entorno ERP_PG_HOME.
    [string]$PgHome,
    [int]$PgPort = 5433,
    [int]$ApiPort = 8000,
    # Raíz del repositorio (donde están .env y .venv). Por defecto, la carpeta padre de scripts\.
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    # Solo levanta PostgreSQL.
    [switch]$DbOnly,
    # No ejecuta alembic upgrade head.
    [switch]$NoMigrate,
    # Arranca uvicorn con --reload (recarga al guardar archivos del backend).
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'

if (-not $PgHome) {
    $PgHome = if ($env:ERP_PG_HOME) { $env:ERP_PG_HOME } else { Join-Path $env:LOCALAPPDATA 'DatasysERP\pg' }
}

$pgBin   = Join-Path $PgHome 'pginstall\bin'
$pgCtl   = Join-Path $pgBin 'pg_ctl.exe'
$pgData  = Join-Path $PgHome 'data'
$pgLog   = Join-Path $PgHome 'pg.log'
$state   = Split-Path -Parent $PgHome
$logDir  = Join-Path $state 'logs'
$apiPid  = Join-Path $state 'api.pid'
$healthUrl = "http://127.0.0.1:$ApiPort/health/ready"

function Write-Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Test-PgRunning {
    # pg_ctl status devuelve 0 si el servidor corre; con EAP=Stop, PowerShell 5.1 convertiría su stderr en error.
    $ErrorActionPreference = 'Continue'
    & $pgCtl status -D $pgData *> $null
    $LASTEXITCODE -eq 0
}

function Get-PortOwner([int]$port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" }
}

function Get-Health {
    try { Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3 } catch { $null }
}

# Ventana oculta propia: el proceso no muere al cerrar la terminal desde la que se lanzó y no hereda
# sus handles. La redirección a archivo la hace cmd.exe: con -RedirectStandardOutput, Start-Process
# heredaría la salida de esta terminal y quien lea por tubería (p. ej. "| more") nunca vería el final.
function Start-Hidden([string]$file, [string[]]$arguments, [string]$workDir, [string]$stdout, [string]$stderr) {
    $p = @{ FilePath = $file; ArgumentList = $arguments; WindowStyle = 'Hidden'; PassThru = $true }
    if ($workDir) { $p.WorkingDirectory = $workDir }
    if ($stdout) {
        foreach ($part in @($file, $stdout, $stderr) + $arguments) {
            if ($part -match '[%"!^]') { throw "Ruta o argumento con caracteres no admitidos por cmd.exe: $part" }
        }
        $p.FilePath = 'cmd.exe'
        $p.ArgumentList = "/d /s /c `"`"$file`" $($arguments -join ' ') > `"$stdout`" 2> `"$stderr`"`""
    }
    Start-Process @p
}

# ---------------------------------------------------------------- PostgreSQL
Write-Step "PostgreSQL ($pgData, puerto $PgPort)"

if (-not (Test-Path $pgCtl) -or -not (Test-Path (Join-Path $pgData 'PG_VERSION'))) {
    Write-Host @"
No se encontró PostgreSQL en $PgHome.
Se esperan los binarios en  $pgBin
y el clúster en             $pgData
Vea la sección "Desarrollo local en Windows" del README para instalarlo (pgserver + initdb)
o indique otra carpeta con -PgHome / la variable de entorno ERP_PG_HOME.
"@ -ForegroundColor Yellow
    exit 1
}

# Tras un apagado brusco queda un postmaster.pid cuyo PID puede pertenecer ya a otro proceso
# y PostgreSQL se niega a arrancar. Solo se borra si ese PID no es un postgres vivo.
$pidFile = Join-Path $pgData 'postmaster.pid'
if (Test-Path $pidFile) {
    $oldPid = 0
    [void][int]::TryParse((Get-Content $pidFile -TotalCount 1), [ref]$oldPid)
    $proc = if ($oldPid) { Get-Process -Id $oldPid -ErrorAction SilentlyContinue }
    if (-not $proc -or $proc.ProcessName -ne 'postgres') {
        Write-Warning "postmaster.pid obsoleto (PID $oldPid no es postgres); se elimina."
        Remove-Item $pidFile
    }
}

if (Test-PgRunning) {
    Write-Host "Ya estaba corriendo."
} else {
    $owner = Get-PortOwner $PgPort
    if ($owner) {
        Write-Host "El puerto $PgPort ya está en uso por PID $($owner.ProcessId): $($owner.CommandLine)" -ForegroundColor Red
        Write-Host "Deténgalo (por ejemplo, otro clúster PostgreSQL) o use -PgPort." -ForegroundColor Red
        exit 1
    }
    $p = Start-Hidden $pgCtl @('start', '-D', "`"$pgData`"", '-l', "`"$pgLog`"", '-w', '-t', '60',
                               '-o', "`"-p $PgPort -c listen_addresses=127.0.0.1 -c max_connections=200`"")
    $null = $p.Handle  # necesario en PowerShell 5.1 para poder leer ExitCode
    $p.WaitForExit()
    if ($p.ExitCode -ne 0) {
        Write-Host "PostgreSQL no arrancó (pg_ctl salió con $($p.ExitCode)). Últimas líneas de $pgLog :" -ForegroundColor Red
        Get-Content $pgLog -Tail 20
        exit 1
    }
    Write-Host "Arrancado."
}
& (Join-Path $pgBin 'pg_isready.exe') -h 127.0.0.1 -p $PgPort
if ($LASTEXITCODE -ne 0) { Write-Host "PostgreSQL no acepta conexiones; revise $pgLog" -ForegroundColor Red; exit 1 }

if ($DbOnly) {
    Write-Host "`nListo (solo base de datos). Para las pruebas de respaldo: `$env:PG_BIN = '$pgBin'"
    exit 0
}

# ---------------------------------------------------------------- API
Write-Step "API FastAPI (puerto $ApiPort)"

$python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host "No existe $python. Cree el entorno virtual:" -ForegroundColor Yellow
    Write-Host "  py -3.13 -m venv .venv ; .venv\Scripts\pip install -r backend\requirements-dev.txt"
    exit 1
}
if (-not (Test-Path (Join-Path $RepoRoot '.env'))) {
    Write-Host "No existe $RepoRoot\.env. Copie .env.example a .env y ajuste DATABASE_URL al puerto $PgPort." -ForegroundColor Yellow
    exit 1
}

# Salvaguarda: dev-up migra y arranca la API con lo que diga .env. Solo se permite un entorno de
# desarrollo o pruebas contra una base de esta máquina, para no migrar por error staging o producción.
# Se revisan solo ENVIRONMENT y el host de DATABASE_URL; las credenciales no se muestran.
$envVars = @{}
foreach ($line in Get-Content (Join-Path $RepoRoot '.env')) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { $envVars[$Matches[1]] = $Matches[2].Trim().Trim('"', "'") }
}
# Como en la API (pydantic-settings), una variable de entorno del sistema prevalece sobre .env.
foreach ($name in 'ENVIRONMENT', 'DATABASE_URL') {
    $value = (Get-Item -Path "Env:$name" -ErrorAction SilentlyContinue).Value  # sin tipos .NET: modo de lenguaje restringido
    if ($value) { $envVars[$name] = $value }
}
$environment = if ($envVars['ENVIRONMENT']) { $envVars['ENVIRONMENT'] } else { 'development' }  # mismo valor por defecto que la API
if ($environment -notin @('development', 'test')) {
    Write-Host "ENVIRONMENT=$environment (en .env o en el sistema): dev-up solo trabaja con development o test." -ForegroundColor Red
    exit 1
}
$dbHost = if ($envVars['DATABASE_URL'] -match '@(\[[^\]]+\]|[^:/?]+)') { $Matches[1] } else { '' }
if ($dbHost -notin @('127.0.0.1', 'localhost', '[::1]')) {
    Write-Host "DATABASE_URL (de .env o del sistema) no apunta a esta máquina (host '$dbHost'); dev-up no migra ni arranca contra otra base." -ForegroundColor Red
    exit 1
}

if (-not $NoMigrate) {
    Write-Host "Aplicando migraciones (alembic upgrade head)..."
    Push-Location $RepoRoot
    try { & $python -m alembic upgrade head } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { Write-Host "alembic falló; revise DATABASE_URL en .env." -ForegroundColor Red; exit 1 }
}

$health = Get-Health
if ($health -and $health.status -eq 'ok') {
    Write-Host "Ya estaba corriendo."
} else {
    $owner = Get-PortOwner $ApiPort
    if ($owner) {
        Write-Host "El puerto $ApiPort está ocupado por PID $($owner.ProcessId) y no responde /health/ready:" -ForegroundColor Red
        Write-Host "  $($owner.CommandLine)"
        Write-Host "Deténgalo con scripts\dev-down.ps1 o use -ApiPort." -ForegroundColor Red
        exit 1
    }
    New-Item -ItemType Directory -Force $logDir | Out-Null
    $uvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', "$ApiPort")
    if ($Reload) { $uvicornArgs += '--reload' }
    $p = Start-Hidden $python $uvicornArgs $RepoRoot (Join-Path $logDir 'api.out.log') (Join-Path $logDir 'api.err.log')
    Set-Content -Path $apiPid -Value $p.Id -Encoding ascii

    Write-Host -NoNewline "Esperando $healthUrl "
    # Por intentos y no por reloj: si el equipo se suspende a mitad de la espera no se da por fallida.
    for ($i = 0; $i -lt 60; $i++) {
        $health = Get-Health
        if ($health -and $health.status -eq 'ok') { break }
        if ($p.HasExited) { break }
        Write-Host -NoNewline '.'
        Start-Sleep -Seconds 1
    }
    Write-Host ''
    if (-not ($health -and $health.status -eq 'ok')) {
        Write-Host "La API no respondió. Últimas líneas de $logDir\api.err.log :" -ForegroundColor Red
        Get-Content (Join-Path $logDir 'api.err.log') -Tail 25 -ErrorAction SilentlyContinue
        exit 1
    }
}
Write-Host ("health/ready: status={0} schema={1} environment={2}" -f $health.status, $health.schema_version, $health.environment) -ForegroundColor Green

Write-Host @"

Listo.
  API:          http://localhost:$ApiPort/api/docs   (logs en $logDir)
  Frontend:     en otra terminal ejecute
                    npm --prefix frontend install   (solo la primera vez)
                    npm --prefix frontend run dev
                y abra http://localhost:5173
$(if ($ApiPort -ne 8000) { "                (API en otro puerto: antes, `$env:VITE_PROXY_TARGET = 'http://localhost:$ApiPort')`n" })  Pruebas:      `$env:PG_BIN = '$pgBin' ; .venv\Scripts\pytest -q
  Detener todo: powershell -ExecutionPolicy Bypass -File scripts\dev-down.ps1
"@
