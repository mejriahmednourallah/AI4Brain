param([switch]$NoBuild, [int]$WaitTimeout = 240)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Install Docker Desktop with Linux containers before running this script.'
}
$envPath = Join-Path $projectRoot '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot '.env.example') -Destination $envPath
}
$contents = [System.IO.File]::ReadAllText($envPath)
if ($contents -notmatch '(?m)^NEO4J_PASSWORD=') {
    $contents += "`nNEO4J_PASSWORD=replace-with-local-password`n"
}
if ($contents -match '(?m)^NEO4J_PASSWORD=(?:replace-with-local-password|["'']{0,2})\s*$') {
    $randomBytes = New-Object byte[] 24
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($randomBytes) } finally { $generator.Dispose() }
    $password = [BitConverter]::ToString($randomBytes).Replace('-', '').ToLowerInvariant()
    $contents = [regex]::Replace($contents, '(?m)^NEO4J_PASSWORD=.*$', ('NEO4J_PASSWORD=' + $password))
    [System.IO.File]::WriteAllText($envPath, $contents, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host 'Created a local Neo4j password in ignored .env (value not displayed).'
}

docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait for the Linux engine, then retry.' }
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration is invalid; check the variable names reported above.' }
$composeArgs = @('compose', 'up', '--detach', '--wait', '--wait-timeout', [string]$WaitTimeout)
if (-not $NoBuild) { $composeArgs += '--build' }
& docker @composeArgs
if ($LASTEXITCODE -ne 0) { throw 'Compose did not become healthy. Inspect: docker compose ps; docker compose logs --tail 100' }
Write-Host 'AI4BRAIN is healthy. Web address:'
docker compose port web 8080
Write-Host 'Default URL: http://localhost:8080. Stop with: docker compose stop'
