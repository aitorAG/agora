Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFile = Join-Path $rootDir ".env"
$runtimeEnvFile = Join-Path $rootDir ".env.runtime"

if (-not (Test-Path $envFile)) {
  throw "Missing $envFile"
}

$envMap = @{}
Get-Content $envFile | ForEach-Object {
  $line = $_.Trim()
  if (-not $line) { return }
  if ($line.StartsWith("#")) { return }
  $idx = $line.IndexOf("=")
  if ($idx -lt 1) { return }
  $k = $line.Substring(0, $idx).Trim()
  $v = $line.Substring($idx + 1).Trim()
  $commentIdx = $v.IndexOf(" #")
  if ($commentIdx -ge 0) {
    $v = $v.Substring(0, $commentIdx).Trim()
  }
  if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
    if ($v.Length -ge 2) {
      $v = $v.Substring(1, $v.Length - 2)
    }
  }
  $envMap[$k] = $v
}

$targetRaw = if ($envMap.ContainsKey("AGORA_DEPLOY_TARGET")) { $envMap["AGORA_DEPLOY_TARGET"] } else { "local" }
$target = $targetRaw.ToLowerInvariant()
if ($target -ne "local" -and $target -ne "vps") {
  throw "Invalid AGORA_DEPLOY_TARGET='$targetRaw'. Expected: local or vps."
}

$localBase = if ($envMap.ContainsKey("AGORA_BASE_URL_LOCAL")) { $envMap["AGORA_BASE_URL_LOCAL"] } else { "http://localhost" }
$vpsBase = if ($envMap.ContainsKey("AGORA_BASE_URL_VPS")) { $envMap["AGORA_BASE_URL_VPS"] } else { "http://85.17.246.141" }
$resolvedBase = if ($target -eq "vps") { $vpsBase } else { $localBase }
$resolvedBase = $resolvedBase.TrimEnd("/")
$resolvedLangfuse = "$resolvedBase/admin/observability"

$effectiveNextAuth = if ($envMap.ContainsKey("NEXTAUTH_URL") -and $envMap["NEXTAUTH_URL"]) { $envMap["NEXTAUTH_URL"] } else { $resolvedLangfuse }
$effectiveLangfuseHost = if ($envMap.ContainsKey("LANGFUSE_HOST") -and $envMap["LANGFUSE_HOST"]) { $envMap["LANGFUSE_HOST"] } else { $resolvedLangfuse }

$outLines = New-Object System.Collections.Generic.List[string]
Get-Content $envFile | ForEach-Object {
  $line = $_
  if ($line -match '^\s*AGORA_RESOLVED_BASE_URL=') { return }
  if ($line -match '^\s*NEXTAUTH_URL=') { return }
  if ($line -match '^\s*LANGFUSE_HOST=') { return }
  $outLines.Add($line)
}
$outLines.Add("AGORA_RESOLVED_BASE_URL=$resolvedBase")
$outLines.Add("NEXTAUTH_URL=$effectiveNextAuth")
$outLines.Add("LANGFUSE_HOST=$effectiveLangfuseHost")

Set-Content -Path $runtimeEnvFile -Value $outLines -Encoding UTF8

Write-Output "Resolved env -> target=$target base_url=$resolvedBase"
Write-Output "Resolved env file: $runtimeEnvFile"
