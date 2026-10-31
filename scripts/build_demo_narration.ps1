[CmdletBinding()]
param(
    [string]$VoiceName = 'Microsoft David Desktop',
    [ValidateRange(-10, 10)][int]$Rate = 0
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sourcePath = Join-Path $workspaceRoot 'docs/submission/demo-narration.txt'
$outputRoot = Join-Path $workspaceRoot 'output/submission-qa'
$narrationRoot = Join-Path $outputRoot 'narration'
$captionPath = Join-Path $outputRoot 'demo-captions.srt'
$manifestPath = Join-Path $outputRoot 'demo-narration-manifest.json'
$ffprobeCommand = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not $ffprobeCommand) { throw 'ffprobe is required to measure generated WAV durations.' }
if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) { throw 'Narration source is missing.' }

Add-Type -AssemblyName System.Speech
$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voice = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -eq $VoiceName } | Select-Object -First 1
    if (-not $voice) { throw "Requested local Windows speech voice is unavailable: $VoiceName" }
    $synth.SelectVoice($voice.VoiceInfo.Name)
    $synth.Rate = $Rate
    $synth.Volume = 90
    $source = Get-Content -LiteralPath $sourcePath -Raw -Encoding utf8
    $chapterMatches = [regex]::Matches($source, '(?ms)^## (?<number>\d{2}) \| (?<start>\d+):(\d{2})-(?<end>\d+):(\d{2}) \| (?<title>[^\r\n]+)\r?\n\r?\n(?<text>.*?)(?=\r?\n## |\z)')
    if ($chapterMatches.Count -ne 6) { throw "Expected six narration chapters; found $($chapterMatches.Count)." }
    New-Item -ItemType Directory -Path $narrationRoot -Force | Out-Null
    $captions = [System.Collections.Generic.List[string]]::new()
    $chapters = [System.Collections.Generic.List[object]]::new()
    $captionIndex = 0
    foreach ($match in $chapterMatches) {
        $number = $match.Groups['number'].Value
        $startSeconds = ([int]$match.Groups['start'].Value * 60) + [int]$match.Groups[3].Value
        $endSeconds = ([int]$match.Groups['end'].Value * 60) + [int]$match.Groups[5].Value
        $slotSeconds = $endSeconds - $startSeconds
        $title = $match.Groups['title'].Value.Trim()
        $text = ($match.Groups['text'].Value -replace '\s+', ' ').Trim()
        if ($slotSeconds -le 0 -or -not $text) { throw "Chapter $number has invalid timing or empty narration." }
        $wavPath = Join-Path $narrationRoot "chapter-$number.wav"
        $synth.SetOutputToWaveFile($wavPath)
        $synth.Speak($text)
        $synth.SetOutputToNull()
        $durationRaw = (& $ffprobeCommand.Source -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $wavPath).Trim()
        $duration = [double]::Parse($durationRaw, [Globalization.CultureInfo]::InvariantCulture)
        if ($duration -ge $slotSeconds) { throw "Chapter $number speech ($([math]::Round($duration,2))s) does not fit its $slotSeconds second window." }
        $words = $text -split '\s+'
        $chunkSize = 12
        $chunkCount = [math]::Ceiling($words.Count / $chunkSize)
        if ($duration -lt $chunkCount) { throw "Chapter $number is too short for readable timed captions." }
        for ($wordStart = 0; $wordStart -lt $words.Count; $wordStart += $chunkSize) {
            $wordEnd = [math]::Min($wordStart + $chunkSize, $words.Count)
            $cueStart = $startSeconds + ($duration * $wordStart / $words.Count)
            $cueEnd = $startSeconds + ($duration * $wordEnd / $words.Count)
            $captionIndex++
            $formatTime = { param([double]$Total) $time=[timespan]::FromSeconds($Total); '{0:00}:{1:00}:{2:00},{3:000}' -f [math]::Floor($time.TotalHours),$time.Minutes,$time.Seconds,$time.Milliseconds }
            $captions.Add([string]$captionIndex)
            $captions.Add("$(& $formatTime $cueStart) --> $(& $formatTime $cueEnd)")
            $captions.Add(($words[$wordStart..($wordEnd - 1)] -join ' '))
            $captions.Add('')
        }
        $chapters.Add([ordered]@{
            chapter = [int]$number; title = $title; start_seconds = $startSeconds; end_seconds = $endSeconds
            slot_seconds = $slotSeconds; audio_seconds = [math]::Round($duration, 3)
            wav = "narration/chapter-$number.wav"; narration = $text
        })
    }
    [IO.File]::WriteAllText($captionPath, ($captions -join "`r`n"), [Text.UTF8Encoding]::new($false))
    $manifest = [ordered]@{
        schema_version = 'ai4brain-demo-narration-v1'; voice = $voice.VoiceInfo.Name
        voice_culture = $voice.VoiceInfo.Culture.Name; synthesis = 'Windows System.Speech, local only'
        provider_calls = 0; synthetic_narration = $true; target_runtime_seconds = 255
        chapters = @($chapters.ToArray()); captions = 'demo-captions.srt'
        disclosure = 'Automated browser QA, not participant or cognitive-performance data.'
    }
    [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    Write-Output "Generated $($chapters.Count) local synthetic narration WAV files, timed captions, and duration manifest in $outputRoot"
}
finally {
    $synth.Dispose()
}
