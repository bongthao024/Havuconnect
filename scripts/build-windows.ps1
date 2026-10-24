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
Remove-Item '.local\pytest-results.xml' -ErrorAction SilentlyContinue
& $python -m pytest -q --junitxml '.local\pytest-results.xml'
if ($LASTEXITCODE -ne 0) { throw 'Kiểm thử thất bại; không tạo bộ cài.' }
& $python -m PyInstaller --noconfirm --clean --windowed --onedir --name GPT-PC-Control `
    --paths $repo --collect-all playwright --collect-submodules uvicorn `
    --add-data 'gpt_pc_control\static;gpt_pc_control\static' `
    --add-data 'integrations;integrations' `
    --add-data '.local\browsers;browsers' `
    --add-data ($bundleTools + ';tools') --add-data 'LICENSE;licenses/project' desktop_entry.py
if ($LASTEXITCODE -ne 0) { throw 'Đóng gói ứng dụng thất bại' }
$report = Join-Path $repo '.local\packaged-smoke.json'
Remove-Item $report -ErrorAction SilentlyContinue
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
# Exercise the actual installer only on the disposable GitHub Windows runner.
# Refuse an existing installation instead of redirecting its uninstall registration.
if ($env:GITHUB_ACTIONS -eq 'true') {
    $installDir = Join-Path $repo '.local\installer-smoke'
    $installedExe = Join-Path $installDir 'GPT-PC-Control.exe'
    $uninstaller = Join-Path $installDir 'unins000.exe'
    $installedReport = Join-Path $repo '.local\installed-smoke.json'
    $lifecycleReport = Join-Path $repo '.local\installer-smoke.json'
    $setupLog = Join-Path $repo '.local\installer-setup.log'
    $uninstallLog = Join-Path $repo '.local\installer-uninstall.log'
    $uninstallKeys = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{DB309293-32A8-4370-8CD7-F3B8CDCA4AA9}_is1',
        'HKCU:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{DB309293-32A8-4370-8CD7-F3B8CDCA4AA9}_is1',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{DB309293-32A8-4370-8CD7-F3B8CDCA4AA9}_is1',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{DB309293-32A8-4370-8CD7-F3B8CDCA4AA9}_is1'
    )
    if (Test-Path -LiteralPath $installDir) { throw 'Installer smoke directory already exists; refusing to overwrite it.' }
    foreach ($key in $uninstallKeys) {
        if (Test-Path -LiteralPath $key) { throw 'An existing GPT PC Control installation was found; refusing installer smoke.' }
    }
    Remove-Item $installedReport, $lifecycleReport -ErrorAction SilentlyContinue
    $lifecycle = [ordered]@{ passed=$false; install_exit=$null; installed_smoke_exit=$null; uninstall_exit=$null; executable_removed=$false }
    $testError = $null
    $cleanupError = $null
    try {
        $installer = Join-Path $repo 'dist\installer\GPT-PC-Control-Setup.exe'
        $install = Start-Process -FilePath $installer -ArgumentList @(
            '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
            ('/DIR="' + $installDir + '"'), ('/LOG="' + $setupLog + '"')
        ) -Wait -PassThru
        $lifecycle.install_exit = $install.ExitCode
        if ($install.ExitCode -ne 0) { throw "Installer smoke failed with exit code $($install.ExitCode)." }
        if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf)) { throw 'Installer did not create the application executable.' }
        $installedSmoke = Start-Process -FilePath $installedExe -ArgumentList @(
            '--self-test', '--report', ('"' + $installedReport + '"')
        ) -Wait -PassThru
        $lifecycle.installed_smoke_exit = $installedSmoke.ExitCode
        if ($installedSmoke.ExitCode -ne 0) { throw "Installed executable smoke failed with exit code $($installedSmoke.ExitCode)." }
        if (-not (Test-Path -LiteralPath $installedReport -PathType Leaf)) { throw 'Installed executable did not create a fresh smoke report.' }
        $installedResult = Get-Content -LiteralPath $installedReport -Raw | ConvertFrom-Json
        if (-not $installedResult.passed -or $installedResult.platform -ne 'win32') { throw 'Installed executable smoke report did not pass on Windows.' }
    }
    catch {
        $testError = $_
    }
    finally {
        try {
            if (Test-Path -LiteralPath $uninstaller -PathType Leaf) {
                $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @(
                    '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/LOG="' + $uninstallLog + '"')
                ) -Wait -PassThru
                $lifecycle.uninstall_exit = $uninstall.ExitCode
                if ($uninstall.ExitCode -ne 0) { throw "Installer smoke cleanup failed with exit code $($uninstall.ExitCode)." }
            }
            elseif (Test-Path -LiteralPath $installDir) {
                throw 'Installer smoke left a directory without its uninstaller; preserving files for investigation.'
            }
            if (Test-Path -LiteralPath $installedExe) { throw 'Uninstall left the installed application executable behind.' }
            foreach ($key in $uninstallKeys) {
                if (Test-Path -LiteralPath $key) { throw 'Uninstall left its application registration behind.' }
            }
            $lifecycle.executable_removed = $true
        }
        catch {
            $cleanupError = $_
        }
        $lifecycle.passed = ($null -eq $testError -and $null -eq $cleanupError)
        if ($testError) { $lifecycle['test_error'] = $testError.Exception.Message }
        if ($cleanupError) { $lifecycle['cleanup_error'] = $cleanupError.Exception.Message }
        $lifecycle | ConvertTo-Json | Set-Content -LiteralPath $lifecycleReport -Encoding utf8
    }
    if ($testError) {
        if ($cleanupError) { Write-Warning $cleanupError.Exception.Message }
        throw $testError
    }
    if ($cleanupError) { throw $cleanupError }
}
Get-FileHash '.\dist\installer\GPT-PC-Control-Setup.exe' -Algorithm SHA256 |
    Format-List | Out-File '.\dist\installer\SHA256.txt' -Encoding utf8
Write-Host 'Đã build: dist\installer\GPT-PC-Control-Setup.exe. Cần nghiệm thu GUI/cài-gỡ trên Windows 11 trước khi phát hành.'
