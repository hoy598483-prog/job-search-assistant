param([Parameter(Mandatory=$true)][string]$ExtensionId)
$root = (Resolve-Path $PSScriptRoot).Path
$python = (Get-Command python).Source
$hostScript = Join-Path $root "companion\native_host.py"
$launcher = Join-Path $root "browser_companion\job_companion_native_host_v10.exe"
$manifest = Join-Path $root "browser_companion\native_host.json"
$config = Join-Path $root "browser_companion\native_host_config.json"
$launcherText = $null
$template = Get-Content (Join-Path $root "browser_companion\native_host_manifest.template.json") -Raw
$manifestText = $template.Replace("HOST_LAUNCHER_PATH", $launcher.Replace('\','/')).Replace("EXTENSION_ID", $ExtensionId)
Set-Content -LiteralPath $manifest -Value $manifestText -Encoding utf8
Set-Content -LiteralPath $config -Value (@{extension_id=$ExtensionId} | ConvertTo-Json) -Encoding utf8
$registry = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.local.job_companion"
New-Item -Path $registry -Force | Out-Null
Set-ItemProperty -Path $registry -Name '(default)' -Value $manifest
Write-Host "Native Messaging Host registered. Reload the extension at chrome://extensions."
