param([string]$DependencyPath)
$ErrorActionPreference = 'Stop'
$fitnessRoot = Split-Path $PSScriptRoot -Parent
$linkPath = Join-Path $fitnessRoot 'frontend/node_modules'
if (Test-Path -LiteralPath $linkPath) {
    Write-Host 'Existing frontend dependencies are ready. No download performed.'
    exit 0
}
if (-not $DependencyPath) {
    $DependencyPath = Join-Path (Split-Path $fitnessRoot -Parent) 'frontend/node_modules'
}
$resolvedDependencies = (Resolve-Path -LiteralPath $DependencyPath).Path
foreach ($modulePath in @('vue/package.json', 'vite/package.json', '@vitejs/plugin-vue/package.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedDependencies $modulePath))) {
        throw "Missing installed module: $modulePath. Provide an existing compatible dependency directory."
    }
}
New-Item -ItemType Junction -Path $linkPath -Target $resolvedDependencies | Out-Null
Write-Host 'Linked existing frontend dependencies. No download performed.'
