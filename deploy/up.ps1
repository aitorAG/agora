Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $rootDir

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "No se encontro 'docker' en PATH. Instala Docker Desktop o agrega docker al PATH."
}

& (Join-Path $PSScriptRoot "resolve_env.ps1")
try {
  docker network create agora_edge *> $null
} catch {
  if ($_.Exception.Message -notmatch "already exists") {
    throw
  }
}

$postgresId = docker compose --env-file .env.runtime -f docker-compose.prod.yml ps -q postgres 2>$null
if ($postgresId) {
  $postgresRunning = docker inspect -f "{{.State.Running}}" $postgresId 2>$null
  if ($postgresRunning -match "true") {
    Write-Output "Creating pre-deploy database backup..."
    try {
      & (Join-Path $PSScriptRoot "backup_db.ps1") (Join-Path $rootDir "backups\predeploy") | Out-Host
    } catch {
      Write-Warning "Pre-deploy database backup failed; continuing with deploy."
    }
  }
}

docker compose --env-file .env.runtime -f observability-platform/docker-compose.telemetry.yml up -d --build --remove-orphans
docker compose --env-file .env.runtime -f docker-compose.prod.yml up -d --build --remove-orphans
docker compose --env-file .env.runtime -f docker-compose.prod.yml up -d --force-recreate nginx

docker compose --env-file .env.runtime -f docker-compose.prod.yml ps
docker compose --env-file .env.runtime -f observability-platform/docker-compose.telemetry.yml ps
