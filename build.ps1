param(
    [switch]$Package
)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create .venv and install requirements-dev.txt before building.'
}

$originalPath = $env:PATH
# Codex desktop adds its document/runtime helpers to PATH. They contain an
# unrelated versioned ICU build that PyInstaller can mistake for Qt's Windows
# system ICU dependency, producing a QtCore entry-point failure at startup.
$env:PATH = (($originalPath -split ';') | Where-Object { $_ -notmatch '[\\/]\.cache[\\/]codex-runtimes[\\/]' }) -join ';'
try {
    & $python -m PyInstaller --noconfirm --clean --windowed `
        --name petoken `
        --icon (Join-Path $repo 'assets\skirk-pet.png') `
        --add-data "$(Join-Path $repo 'assets');assets" `
        --collect-submodules winrt `
        (Join-Path $repo 'widget.py')
    $pyInstallerExit = $LASTEXITCODE
} finally {
    $env:PATH = $originalPath
}
if ($pyInstallerExit -ne 0) { throw "PyInstaller failed with exit code $pyInstallerExit" }

$app = Join-Path $repo 'dist\petoken'
$site = Join-Path $repo '.venv\Lib\site-packages'
# Python 3.13 may contribute an older VC runtime at the bundle root. Windows
# loads that copy before PySide6's newer runtime, causing QtCore entry-point
# failures. The newer redistributable is backward-compatible, so keep one
# consistent runtime version at the loader's first search location.
$internal = Join-Path $app '_internal'
foreach ($runtime in 'vcruntime140.dll','vcruntime140_1.dll') {
    Copy-Item -LiteralPath (Join-Path $site "PySide6\$runtime") -Destination $internal -Force
}
Copy-Item -LiteralPath (Join-Path $repo 'README.md') -Destination $app -Force
Copy-Item -LiteralPath (Join-Path $repo 'LICENSE') -Destination $app -Force
Copy-Item -LiteralPath (Join-Path $repo 'THIRD_PARTY_NOTICES.md') -Destination $app -Force

$licenses = Join-Path $app 'THIRD_PARTY_LICENSES'
New-Item -ItemType Directory -Path $licenses -Force | Out-Null
$dependencyPatterns = 'comtypes-*','psutil-*','pycaw-*','pyside6_essentials-*','shiboken6-*','typing_extensions-*','uiautomation-*','winrt_runtime-*','winrt_Windows.*'
foreach ($pattern in $dependencyPatterns) {
    Get-ChildItem -LiteralPath $site -Directory -Filter "$pattern.dist-info" -ErrorAction SilentlyContinue | ForEach-Object {
        $packageName = $_.BaseName
        Get-ChildItem -LiteralPath $_.FullName -Recurse -File | Where-Object { $_.Name -match '^(LICENSE|COPYING|NOTICE)' } | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $licenses "$packageName-$($_.Name)") -Force
        }
    }
}

if ($Package) {
    $zip = Join-Path $repo 'dist\petoken-Windows-x64.zip'
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -Path $app -DestinationPath $zip -CompressionLevel Optimal
    Write-Host "Created $zip"
}

Write-Host "Built $app\petoken.exe"
