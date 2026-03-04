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

$publicUrl = if ($envMap.ContainsKey("AGORA_PUBLIC_URL")) { $envMap["AGORA_PUBLIC_URL"] } else { "" }
$localBase = if ($envMap.ContainsKey("AGORA_BASE_URL_LOCAL")) { $envMap["AGORA_BASE_URL_LOCAL"] } else { "http://localhost" }
$vpsBase = if ($envMap.ContainsKey("AGORA_BASE_URL_VPS")) { $envMap["AGORA_BASE_URL_VPS"] } else { "http://85.17.246.141" }
if ($target -eq "vps" -and $publicUrl) {
  $resolvedBase = $publicUrl
} elseif ($target -eq "vps") {
  $resolvedBase = $vpsBase
} else {
  $resolvedBase = $localBase
}
$resolvedBase = $resolvedBase.TrimEnd("/")
$resolvedObservability = "$resolvedBase/admin/observability"

$outLines = New-Object System.Collections.Generic.List[string]
($envMap.GetEnumerator() | Sort-Object Name) | ForEach-Object {
  $key = [string]$_.Key
  if ($key -in @("AGORA_RESOLVED_BASE_URL", "AGORA_OBSERVABILITY_URL", "AGORA_RUNTIME_CONTEXT", "NEXTAUTH_URL", "LANGFUSE_HOST")) {
    return
  }
  $outLines.Add("$key=$($_.Value)")
}
$outLines.Add("AGORA_RUNTIME_CONTEXT=docker")
$outLines.Add("AGORA_RESOLVED_BASE_URL=$resolvedBase")
$outLines.Add("AGORA_OBSERVABILITY_URL=$resolvedObservability")

Set-Content -Path $runtimeEnvFile -Value $outLines -Encoding UTF8

Write-Output "Resolved env -> target=$target base_url=$resolvedBase"
Write-Output "Resolved env file: $runtimeEnvFile"

if (-not $envMap.ContainsKey("POSTGRES_PASSWORD") -or [string]::IsNullOrWhiteSpace([string]$envMap["POSTGRES_PASSWORD"])) {
  throw "Resolved runtime environment is missing required values: POSTGRES_PASSWORD"
}
