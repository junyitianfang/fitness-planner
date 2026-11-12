param(
    [string]$EnvironmentName = 'langchain1.2',
    [string]$PythonPath,
    [ValidateRange(1024, 65535)][int]$Port = 8010,
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot

if (-not $PythonPath) {
    if ($env:CONDA_PREFIX -and (Split-Path $env:CONDA_PREFIX -Leaf) -eq $EnvironmentName) {
        $PythonPath = Join-Path $env:CONDA_PREFIX 'python.exe'
    } else {
        $condaCommand = Get-Command conda -ErrorAction SilentlyContinue
        if (-not $condaCommand) {
            throw 'Conda is not on PATH. Open Anaconda PowerShell Prompt, or pass -PythonPath with your environment python.exe.'
        }
        $environmentList = (& conda env list --json) | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0) { throw 'Could not read Conda environments.' }
        $environmentDirectory = @($environmentList.envs | Where-Object { (Split-Path $_ -Leaf) -eq $EnvironmentName })
        if ($environmentDirectory.Count -ne 1) { throw "Cannot uniquely find Conda environment: $EnvironmentName" }
        $PythonPath = Join-Path $environmentDirectory[0] 'python.exe'
    }
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
Write-Host "Python: $PythonPath"
& $PythonPath (Join-Path $projectRoot 'backend\check_environment.py')
if ($LASTEXITCODE -ne 0) {
    throw "Missing dependencies. Run: & '$PythonPath' -m pip install -r '$projectRoot\backend\requirements.txt'"
}

if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Choose a different port with -Port."
}

if (-not $SkipBuild) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\node_modules\vite\package.json'))) {
        throw 'Frontend dependencies are missing. Run scripts/use-existing-frontend.ps1 -DependencyPath with your installed dependency directory.'
    }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) {
    throw 'Frontend build is missing. Run this script without -SkipBuild.'
}

$previousOrigin = $env:FITNESS_ORIGIN
$previousSecure = $env:FITNESS_SECURE_COOKIE
Push-Location (Join-Path $projectRoot 'backend')
try {
    $env:FITNESS_ORIGIN = "http://127.0.0.1:$Port"
    $env:FITNESS_SECURE_COOKIE = 'false'
    Write-Host "Open http://127.0.0.1:$Port in your browser. Press Ctrl+C to stop."
    & $PythonPath -m uvicorn main:app --host 127.0.0.1 --port $Port --no-proxy-headers
    if ($LASTEXITCODE -notin @(0, 130, -1073741510)) { throw "Server exited with code $LASTEXITCODE" }
} finally {
    $env:FITNESS_ORIGIN = $previousOrigin
    $env:FITNESS_SECURE_COOKIE = $previousSecure
    Pop-Location
}
