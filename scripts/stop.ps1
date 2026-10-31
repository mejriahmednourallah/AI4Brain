$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$pidFile=Join-Path $projectRoot 'output\runtime\processes.json'
if(!(Test-Path -LiteralPath $pidFile)){Write-Host 'No recorded AI4BRAIN processes.';exit 0}
$parsed=Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
$entries=@()
foreach($item in $parsed){if($item){$entries+=@($item)}}
foreach($entry in $entries){
  if($entry.id -isnot [int] -and $entry.id -isnot [long]){continue}
  if($entry.start_ticks -isnot [int] -and $entry.start_ticks -isnot [long]){continue}
  $process=Get-Process -Id ([int]$entry.id) -ErrorAction SilentlyContinue
  if(!$process){continue}
  $details=Get-CimInstance Win32_Process -Filter ('ProcessId='+$process.Id)
  $sameStart=$entry.start_ticks -and ($process.StartTime.ToUniversalTime().Ticks -eq [long]$entry.start_ticks)
  if($sameStart -and $details.CommandLine.Contains($projectRoot)){Stop-Process -Id $process.Id -Force;Write-Host ('Stopped '+$entry.role)}
}
Remove-Item -LiteralPath $pidFile
