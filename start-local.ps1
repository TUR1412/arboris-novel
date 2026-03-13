Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
chcp 65001 > $null

$projectRoot = Split-Path -Parent $PSCommandPath
$frontendDir = Join-Path $projectRoot "frontend"
$backendDir = Join-Path $projectRoot "backend"
$frontendDistIndex = Join-Path $frontendDir "dist\\index.html"
$frontendNodeModules = Join-Path $frontendDir "node_modules"
$backendPython = Join-Path $backendDir ".venv\\Scripts\\python.exe"
$backendEnv = Join-Path $backendDir ".env"
$appPort = 8088
$launchUrl = "http://127.0.0.1:$appPort"

function Test-FrontendBuildNeeded {
    if (-not (Test-Path $frontendDistIndex)) {
        return $true
    }

    $distTime = (Get-Item $frontendDistIndex).LastWriteTimeUtc
    $trackedFiles = @(
        (Join-Path $frontendDir "index.html"),
        (Join-Path $frontendDir "package.json"),
        (Join-Path $frontendDir "package-lock.json"),
        (Join-Path $frontendDir "vite.config.ts")
    )

    foreach ($path in $trackedFiles) {
        if ((Get-Item $path).LastWriteTimeUtc -gt $distTime) {
            return $true
        }
    }

    foreach ($file in Get-ChildItem (Join-Path $frontendDir "src") -Recurse -File) {
        if ($file.LastWriteTimeUtc -gt $distTime) {
            return $true
        }
    }

    return $false
}

if (-not (Test-Path $backendPython)) {
    throw "Missing backend virtualenv: $backendPython"
}

if (-not (Test-Path $backendEnv)) {
    throw "Missing backend env file: $backendEnv"
}

if (-not (Test-Path $frontendNodeModules)) {
    throw "Missing frontend dependencies: $frontendNodeModules"
}

if (Test-FrontendBuildNeeded) {
    Write-Host "[arboris] Building frontend..." -ForegroundColor Cyan
    Push-Location $frontendDir
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed."
        }
    }
    finally {
        Pop-Location
    }
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:UVICORN_NO_COLOR = "1"

Write-Host "[arboris] Opening $launchUrl" -ForegroundColor Green
Write-Host "[arboris] Browser will open automatically after the server is ready." -ForegroundColor DarkGray
Write-Host "[arboris] Press Ctrl+C to stop." -ForegroundColor DarkGray

$browserLaunchCommand = @"
`$ProgressPreference = 'SilentlyContinue'
for (`$i = 0; `$i -lt 60; `$i++) {
    try {
        Invoke-WebRequest -UseBasicParsing '$launchUrl/api/health' | Out-Null
        Start-Process '$launchUrl'
        exit 0
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
"@

Start-Process `
    -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -WindowStyle Hidden `
    -ArgumentList "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $browserLaunchCommand `
    | Out-Null

Push-Location $backendDir
try {
    & $backendPython -m uvicorn app.main:app --host 127.0.0.1 --port $appPort
}
finally {
    Pop-Location
}
