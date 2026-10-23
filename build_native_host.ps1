$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m PyInstaller --onefile --name job_companion_native_host_v10 --distpath browser_companion --workpath work/native_host_build_v10 --specpath work/native_host_build_v10 companion/native_host.py
    if ($LASTEXITCODE -ne 0) { throw 'Native Host build failed. Install PyInstaller and retry.' }
    Write-Host 'Build complete. Run install_native_host.ps1 with your Chrome extension ID.'
} finally {
    Pop-Location
}
