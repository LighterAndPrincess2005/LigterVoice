$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv\Scripts\python.exe' -m PyInstaller --clean --noconfirm --distpath release-companion --workpath build-companion 'Ligter Voice.spec'
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Output 'Built: release-companion\Ligter Voice\Ligter Voice.exe'
