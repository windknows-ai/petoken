param(
    [switch]$Package,
    [string]$PythonPath,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$python = if ($PythonPath) { $PythonPath } else { Join-Path $repo '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Provide -PythonPath for an existing environment, or create .venv with requirements-dev.txt.'
}
$site = & $python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate the selected Python environment.' }
$distributionDirectory = if ($OutputDirectory) {
    [System.IO.Path]::GetFullPath($OutputDirectory)
} else { Join-Path $repo 'dist' }
$workDirectory = if ($OutputDirectory) {
    Join-Path $distributionDirectory '.build'
} else { Join-Path $repo 'build' }
$specDirectory = if ($OutputDirectory) { $workDirectory } else { $repo }
New-Item -ItemType Directory -Path $specDirectory -Force | Out-Null

$originalPath = $env:PATH
# Codex desktop adds its document/runtime helpers to PATH. They contain an
# unrelated versioned ICU build that PyInstaller can mistake for Qt's Windows
# system ICU dependency, producing a QtCore entry-point failure at startup.
$env:PATH = (($originalPath -split ';') | Where-Object { $_ -notmatch '[\\/]\.cache[\\/]codex-runtimes[\\/]' }) -join ';'
try {
    & $python -m PyInstaller --noconfirm --clean --windowed `
        --name petoken `
        --distpath $distributionDirectory `
        --workpath $workDirectory `
        --specpath $specDirectory `
        --icon (Join-Path $repo 'assets\skirk-pet.png') `
        --add-data "$(Join-Path $repo 'assets');assets" `
        --collect-submodules winrt `
        (Join-Path $repo 'widget.py')
    $pyInstallerExit = $LASTEXITCODE
} finally {
    $env:PATH = $originalPath
}
if ($pyInstallerExit -ne 0) { throw "PyInstaller failed with exit code $pyInstallerExit" }

$app = Join-Path $distributionDirectory 'petoken'
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
foreach ($document in 'ROADMAP.md','DESIGN.md','SECURITY.md','CONTRIBUTING.md','CHANGELOG.md') {
    Copy-Item -LiteralPath (Join-Path $repo $document) -Destination $app -Force
}
$documentation = Join-Path $app 'docs'
New-Item -ItemType Directory -Path $documentation -Force | Out-Null
foreach ($document in 'USAGE_MODEL.md','PROVIDERS.md','TOKEN_ACCOUNTING.md','ARTWORK.md','RELEASE_NOTES_v1.2.0.md','V1_3_VISUAL_QA.md') {
    Copy-Item -LiteralPath (Join-Path $repo "docs\$document") -Destination $documentation -Force
}
Copy-Item -LiteralPath (Join-Path $repo 'docs\V1_3_VISUAL_QA.md') -Destination $app -Force
Copy-Item -LiteralPath (Join-Path $repo 'tools\launch_v1_3_preview.cmd') -Destination (Join-Path $app 'preview-v1.3.cmd') -Force

$licenses = Join-Path $app 'THIRD_PARTY_LICENSES'
New-Item -ItemType Directory -Path $licenses -Force | Out-Null
$dependencyPatterns = 'comtypes-*','psutil-*','pycaw-*','pyside6_essentials-*','shiboken6-*','typing_extensions-*','uiautomation-*','winrt_runtime-*','winrt_windows_*'
foreach ($pattern in $dependencyPatterns) {
    Get-ChildItem -LiteralPath $site -Directory -Filter "$pattern.dist-info" -ErrorAction SilentlyContinue | ForEach-Object {
        $packageName = $_.BaseName
        Get-ChildItem -LiteralPath $_.FullName -Recurse -File | Where-Object { $_.Name -match '^(LICENSE|COPYING|NOTICE)' } | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $licenses "$packageName-$($_.Name)") -Force
        }
    }
}

# Some wheels omit their full upstream terms. Ship pinned copies as well as
# installed notices, and require the selected Python/bootloader licenses.
Copy-Item -Path (Join-Path $repo 'docs\third_party_licenses\*') -Destination $licenses -Force
$pythonBase = & $python -c "import sys; print(sys.base_prefix)"
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate the selected Python license.' }
Copy-Item -LiteralPath (Join-Path $pythonBase 'LICENSE.txt') -Destination (Join-Path $licenses 'Python-LICENSE.txt') -Force
$pyInstallerMetadata = Get-ChildItem -LiteralPath $site -Directory -Filter 'pyinstaller-*.dist-info' | Select-Object -First 1
if (-not $pyInstallerMetadata) { throw 'Cannot locate the installed PyInstaller license.' }
Copy-Item -LiteralPath (Join-Path $pyInstallerMetadata.FullName 'licenses\COPYING.txt') -Destination (Join-Path $licenses 'PyInstaller-COPYING.txt') -Force

if ($Package) {
    $zip = Join-Path $distributionDirectory 'petoken-Windows-x64.zip'
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -Path $app -DestinationPath $zip -CompressionLevel Optimal
    Write-Host "Created $zip"
}

Write-Host "Built $app\petoken.exe"
