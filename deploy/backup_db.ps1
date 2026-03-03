Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $rootDir

$runtimeEnv = Join-Path $rootDir ".env.runtime"
$baseEnv = Join-Path $rootDir ".env"
if (Test-Path $runtimeEnv) {
  $envFile = $runtimeEnv
} elseif (Test-Path $baseEnv) {
  $envFile = $baseEnv
} else {
  throw "Missing .env or .env.runtime"
}

$outDir = if ($args.Count -gt 0 -and $args[0]) { $args[0] } else { Join-Path $rootDir "backups" }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $outDir "agora_$ts.sql.gz"

$envMap = @{}
Get-Content $envFile | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) { return }
  $idx = $line.IndexOf("=")
  if ($idx -lt 1) { return }
  $k = $line.Substring(0, $idx).Trim()
  $v = $line.Substring($idx + 1).Trim()
  $commentIdx = $v.IndexOf(" #")
  if ($commentIdx -ge 0) {
    $v = $v.Substring(0, $commentIdx).Trim()
  }
  $envMap[$k] = $v
}

$pgUser = if ($envMap.ContainsKey("POSTGRES_USER") -and $envMap["POSTGRES_USER"]) { $envMap["POSTGRES_USER"] } else { "agora_user" }
$pgDb = if ($envMap.ContainsKey("POSTGRES_DB") -and $envMap["POSTGRES_DB"]) { $envMap["POSTGRES_DB"] } else { "agora" }

$dump = docker compose --env-file $envFile -f docker-compose.prod.yml exec -T postgres pg_dump -U $pgUser -d $pgDb
if ($LASTEXITCODE -ne 0) {
  throw "pg_dump failed"
}

$bytes = [System.Text.Encoding]::UTF8.GetBytes(($dump -join [Environment]::NewLine))
$file = [System.IO.File]::Create($outFile)
try {
  $gzip = New-Object System.IO.Compression.GzipStream($file, [System.IO.Compression.CompressionMode]::Compress)
  try {
    $gzip.Write($bytes, 0, $bytes.Length)
  } finally {
    $gzip.Dispose()
  }
} finally {
  $file.Dispose()
}

Write-Output "Backup created: $outFile"
