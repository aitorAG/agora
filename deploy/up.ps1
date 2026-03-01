Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $rootDir

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "No se encontro 'docker' en PATH. Instala Docker Desktop o agrega docker al PATH."
}

& (Join-Path $PSScriptRoot "resolve_env.ps1")
docker network create agora_edge *> $null

docker compose --env-file .env.runtime -f observability-platform/docker-compose.langfuse.yml up -d
docker compose --env-file .env.runtime -f docker-compose.prod.yml up -d --build

docker compose --env-file .env.runtime -f docker-compose.prod.yml ps
docker compose --env-file .env.runtime -f observability-platform/docker-compose.langfuse.yml ps
