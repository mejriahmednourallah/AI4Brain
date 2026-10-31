param([switch]$Install)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$outputDir=Join-Path $projectRoot 'output\runtime'
$pidFile=Join-Path $outputDir 'processes.json'
$ownedProcesses=@()
function Test-Url([string]$Url){
  try{
    $response=Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
    if($Url.EndsWith('/health')){return (($response.Content | ConvertFrom-Json).application -eq 'AI4BRAIN')}
    return ($response.Content -match 'AI4BRAIN')
  }catch{return $false}
}
function Get-ProcessCommandLine([int]$ProcessId){
  $details=Get-CimInstance Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction SilentlyContinue
  if($details){return $details.CommandLine}
  return $null
}
function Test-WorkspaceCommand([int]$ProcessId){
  $commandLine=Get-ProcessCommandLine $ProcessId
  return ($commandLine -and $commandLine.IndexOf($projectRoot,[System.StringComparison]::OrdinalIgnoreCase) -ge 0)
}
function Test-RecordedProcess($Entry){
  if(!$Entry -or !$Entry.id -or !$Entry.start_ticks){return $false}
  $process=Get-Process -Id ([int]$Entry.id) -ErrorAction SilentlyContinue
  if(!$process){return $false}
  try{$sameStart=$process.StartTime.ToUniversalTime().Ticks -eq [long]$Entry.start_ticks}catch{$sameStart=$false}
  return ($sameStart -and (Test-WorkspaceCommand $process.Id))
}
function Get-ValidatedPreviousProcesses{
  if(!(Test-Path -LiteralPath $pidFile)){return @()}
  $parsed=$null
  try{$parsed=Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json}catch{return @()}
  # ConvertFrom-Json can return the whole array as one item; flatten so each entry is
  # a single record and never an array of ids.
  $entries=@()
  foreach($item in $parsed){if($item){$entries+=@($item)}}
  $valid=@()
  foreach($entry in $entries){
    if($entry.id -isnot [int] -and $entry.id -isnot [long]){continue}
    if($entry.start_ticks -isnot [int] -and $entry.start_ticks -isnot [long]){continue}
    if(Test-RecordedProcess $entry){$valid+=@{id=[int]$entry.id;role=[string]$entry.role;start_ticks=[long]$entry.start_ticks}}
  }
  return $valid
}
function Add-OwnedProcess($Process,[string]$Role){
  if(!$Process){return}
  try{$startTicks=$Process.StartTime.ToUniversalTime().Ticks}catch{return}
  $script:ownedProcesses+=@{id=$Process.Id;role=$Role;start_ticks=$startTicks}
}
function Add-OwnedListeners([int[]]$Ports){
  $processTable=@{}
  Get-CimInstance Win32_Process | ForEach-Object {$processTable[[int]$_.ProcessId]=$_}
  foreach($port in $Ports){
    $listener=Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    if(!$listener){continue}
    $listenerPid=[int]$listener.OwningProcess
    $rootIds=@($script:ownedProcesses | ForEach-Object {[int]$_.id})
    $isOwned=($rootIds -contains $listenerPid)
    if(!$isOwned){
      $cursor=$listenerPid
      $seen=@{}
      while($processTable.ContainsKey($cursor) -and !$seen.ContainsKey($cursor)){
        $seen[$cursor]=$true
        $parentPid=[int]$processTable[$cursor].ParentProcessId
        if($rootIds -contains $parentPid){$isOwned=$true;break}
        if($parentPid -le 0){break}
        $cursor=$parentPid
      }
    }
    if($isOwned -and !($script:ownedProcesses | Where-Object {$_.id -eq $listenerPid})){
      $listenerProcess=Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
      if($listenerProcess -and (Test-WorkspaceCommand $listenerPid)){Add-OwnedProcess $listenerProcess ('listener-'+$port)}
    }
  }
}
function Stop-OwnedProcesses{
  foreach($entry in @($script:ownedProcesses)){
    if(!(Test-RecordedProcess $entry)){continue}
    Stop-Process -Id ([int]$entry.id) -Force -ErrorAction SilentlyContinue
  }
}
$previousOwnedProcesses=@(Get-ValidatedPreviousProcesses)
try{
  if($Install){ & (Join-Path $PSScriptRoot 'setup.ps1'); if($LASTEXITCODE -ne 0){throw 'Setup failed'} }
  $pythonExe=Join-Path $projectRoot '.venv\Scripts\python.exe'
  $viteScript=Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
  if(!(Test-Path -LiteralPath $pythonExe) -or !(Test-Path -LiteralPath $viteScript)){throw 'Run .\scripts\setup.ps1 first.'}
  New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
  if(!(Test-Url 'http://127.0.0.1:8000/health')){
    $api=Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $outputDir 'backend.log') -RedirectStandardError (Join-Path $outputDir 'backend.err.log') -PassThru
    Add-OwnedProcess $api 'backend'
  }
  if(!(Test-Url 'http://127.0.0.1:5173')){
    $web=Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @(('"'+$viteScript+'"'),'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $outputDir 'frontend.log') -RedirectStandardError (Join-Path $outputDir 'frontend.err.log') -PassThru
    Add-OwnedProcess $web 'frontend'
  }
  $ready=$false
  for($attempt=0;$attempt -lt 30;$attempt++){
    if((Test-Url 'http://127.0.0.1:8000/health') -and (Test-Url 'http://127.0.0.1:5173')){$ready=$true;break}
    Start-Sleep -Seconds 1
  }
  if(!$ready){throw "Startup did not finish. Inspect $outputDir"}
  Add-OwnedListeners @(8000,5173)
  $records=@()
  foreach($entry in @($previousOwnedProcesses)+@($script:ownedProcesses)){
    if(!(Test-RecordedProcess $entry)){continue}
    if($records | Where-Object {$_.id -eq [int]$entry.id}){continue}
    $records+=@{id=[int]$entry.id;role=[string]$entry.role;start_ticks=[long]$entry.start_ticks}
  }
  ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $pidFile -Encoding utf8
  Write-Host 'AI4BRAIN is running: http://127.0.0.1:5173'
  Write-Host 'API docs: http://127.0.0.1:8000/docs'
  Write-Host 'Docker is not started by this script. Graph availability is shown in the app.'
}catch{
  Add-OwnedListeners @(8000,5173)
  Stop-OwnedProcesses
  throw
}

