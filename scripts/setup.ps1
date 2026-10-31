$ErrorActionPreference='Stop'
$pythonCommand=Get-Command python.exe -ErrorAction SilentlyContinue
if(!$pythonCommand){throw 'Install Python 3.11 or later.'}
$nodeCommand=Get-Command node.exe -ErrorAction SilentlyContinue
if(!$nodeCommand){throw 'Install Node.js 20.19 or later with npm.'}
$npmCommand=Get-Command npm.cmd -ErrorAction SilentlyContinue
if(!$npmCommand){throw 'Install Node.js 20.19 or later with npm.'}
$pythonVersionText=(& $pythonCommand.Source --version 2>&1 | Out-String).Trim()
if($LASTEXITCODE -ne 0 -or $pythonVersionText -notmatch '^Python\s+(\d+\.\d+\.\d+)'){
  throw 'Could not determine the installed Python version.'
}
$pythonVersion=[version]$Matches[1]
if($pythonVersion -lt [version]'3.11.0'){throw "Python 3.11 or later is required; found $pythonVersionText."}
$nodeVersionText=(& $nodeCommand.Source --version 2>&1 | Out-String).Trim()
if($LASTEXITCODE -ne 0 -or $nodeVersionText -notmatch '^v?(\d+\.\d+\.\d+)'){
  throw 'Could not determine the installed Node.js version.'
}
$nodeVersion=[version]$Matches[1]
if($nodeVersion -lt [version]'20.19.0'){throw "Node.js 20.19 or later is required; found $nodeVersionText."}
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if(!(Test-Path -LiteralPath '.venv\Scripts\python.exe')){
  & $pythonCommand.Source -m venv .venv
  if($LASTEXITCODE -ne 0){throw 'venv creation failed'}
}
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
if($LASTEXITCODE -ne 0){throw 'Backend dependency installation failed'}
Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
try{
  & $npmCommand.Source ci
  if($LASTEXITCODE -ne 0){throw 'Frontend dependency installation failed'}
}finally{Pop-Location}
if(!(Test-Path -LiteralPath '.env')){
  $localPassword=[guid]::NewGuid().ToString('N')
  (Get-Content -LiteralPath '.env.example') -replace 'replace-with-local-password',$localPassword | Set-Content -LiteralPath '.env' -Encoding utf8
}
Write-Host 'Setup complete. Run .\scripts\start.ps1. Docker remains off.'
