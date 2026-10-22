param(
    [Parameter(Mandatory=$true)][string]$CloudflaredPath,
    [Parameter(Mandatory=$true)][string]$CloudflaredLicensePath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{64}$')][string]$CloudflaredSha256
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Chỉ build EXE trên Windows x64, không cross-compile từ Linux.' }
Set-Location (Split-Path $PSScriptRoot -Parent)
$repo = (Get-Location).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Cần Python 3.12 x64' }
}
if (-not (Test-Path $CloudflaredPath -PathType Leaf)) { throw 'Thiếu cloudflared.exe từ bản phát hành chính thức' }
if ((Get-FileHash $CloudflaredPath -Algorithm SHA256).Hash -ne $CloudflaredSha256) { throw 'SHA256 cloudflared không khớp; dừng build.' }
$bundleTools = Join-Path $repo '.local\bundle-tools'
New-Item -ItemType Directory -Force $bundleTools | Out-Null
Copy-Item $CloudflaredPath (Join-Path $bundleTools 'cloudflared.exe') -Force
Copy-Item $CloudflaredLicensePath (Join-Path $bundleTools 'LICENSE-cloudflared.txt') -Force
& $python -m pip install -r requirements-build.txt -c requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Cài build dependency thất bại' }
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $repo '.local\browsers'
& $python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Tải Chromium thất bại; không tắt xác minh TLS.' }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Kiểm thử thất bại; không tạo bộ cài.' }
& $python -m PyInstaller --noconfirm --clean --windowed --onedir --name GPT-PC-Control `
    --paths $repo --collect-all playwright --collect-submodules uvicorn `
    --add-data 'gpt_pc_control\static;gpt_pc_control\static' `
    --add-data 'integrations;integrations' `
    --add-data '.local\browsers;browsers' `
    --add-data ($bundleTools + ';tools') --add-data 'LICENSE;licenses/project' desktop_entry.py
if ($LASTEXITCODE -ne 0) { throw 'Đóng gói ứng dụng thất bại' }
$report = Join-Path $repo '.local\packaged-smoke.json'
# Do not let the bundled executable accidentally use a build-machine browser path.
Remove-Item Env:PLAYWRIGHT_BROWSERS_PATH -ErrorAction SilentlyContinue
Remove-Item Env:GPT_PC_CHROMIUM -ErrorAction SilentlyContinue
$smoke = Start-Process -FilePath '.\dist\GPT-PC-Control\GPT-PC-Control.exe' `
    -ArgumentList @('--self-test', '--report', ('"' + $report + '"')) -Wait -PassThru
if ($smoke.ExitCode -ne 0 -or -not (Test-Path $report)) { throw 'Bản EXE chưa vượt qua smoke test' }
if (-not (Get-Content $report -Raw | ConvertFrom-Json).passed) { throw 'Smoke test của bản EXE thất bại' }
$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path $iscc)) { throw 'Cài Inno Setup 6 từ nguồn chính thức trước khi tạo Setup.exe' }
& $iscc '.\packaging\windows-installer.iss'
if ($LASTEXITCODE -ne 0) { throw 'Build bộ cài thất bại' }
Get-FileHash '.\dist\installer\GPT-PC-Control-Setup.exe' -Algorithm SHA256 |
    Format-List | Out-File '.\dist\installer\SHA256.txt' -Encoding utf8
Write-Host 'Đã build: dist\installer\GPT-PC-Control-Setup.exe. Cần nghiệm thu GUI/cài-gỡ trên Windows 11 trước khi phát hành.'
