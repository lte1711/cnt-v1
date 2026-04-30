$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$DataDir = Join-Path $RepoRoot "data"
$LogsDir = Join-Path $RepoRoot "logs"
$LockFile = Join-Path $DataDir "engine.lock"
$HeartbeatFile = Join-Path $DataDir "scheduler_heartbeat.json"
$StdoutLog = Join-Path $LogsDir "scheduler_stdout.log"
$StderrLog = Join-Path $LogsDir "scheduler_stderr.log"
$SchedulerExpectedIntervalMinutes = 10
$SchedulerGapThresholdMinutes = 20
$PythonCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe",
    "python.exe"
)

function Write-Utf8Log {
    param(
        [string]$Path,
        [string]$Message
    )

    if ([string]::IsNullOrEmpty($Message)) {
        return
    }

    Add-Content -Path $Path -Value $Message -Encoding utf8
}

function Write-SchedulerHeartbeat {
    param(
        [string]$Event,
        [Nullable[int]]$ExitCode = $null,
        [string]$ErrorMessage = $null
    )

    $now = Get-Date
    $previous = $null
    if (Test-Path $HeartbeatFile) {
        try {
            $previous = Get-Content $HeartbeatFile -Raw -Encoding utf8 | ConvertFrom-Json
        }
        catch {
            $previous = $null
        }
    }

    $previousFinishTime = $null
    $previousStartTime = $null
    if ($previous -and $previous.last_finish_time) {
        $previousFinishTime = [string]$previous.last_finish_time
    }
    if ($previous -and $previous.last_start_time) {
        $previousStartTime = [string]$previous.last_start_time
    }

    $gapDetected = $false
    $gapDurationMinutes = $null
    if ($Event -eq "start" -and $previousFinishTime) {
        try {
            $lastFinish = [datetime]::Parse($previousFinishTime)
            $gapDurationMinutes = [math]::Round(($now - $lastFinish).TotalMinutes, 2)
            $gapDetected = $gapDurationMinutes -gt $SchedulerGapThresholdMinutes
        }
        catch {
            $gapDetected = $false
            $gapDurationMinutes = $null
        }
    }

    $lastStartTime = $previousStartTime
    $lastFinishTime = $previousFinishTime
    if ($Event -eq "start") {
        $lastStartTime = $now.ToString("yyyy-MM-dd HH:mm:ss")
    }
    if ($Event -in @("finish", "skip", "exception")) {
        $lastFinishTime = $now.ToString("yyyy-MM-dd HH:mm:ss")
    }

    $payload = [ordered]@{
        last_event = $Event
        current_time = $now.ToString("yyyy-MM-dd HH:mm:ss")
        last_start_time = $lastStartTime
        last_finish_time = $lastFinishTime
        expected_interval_minutes = $SchedulerExpectedIntervalMinutes
        gap_threshold_minutes = $SchedulerGapThresholdMinutes
        gap_detected = $gapDetected
        gap_duration_minutes = $gapDurationMinutes
        exit_code = $ExitCode
        error_message = $ErrorMessage
    }

    $payload | ConvertTo-Json -Depth 4 | Set-Content -Path $HeartbeatFile -Encoding utf8
}

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
}

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

if (Test-Path $LockFile) {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Utf8Log -Path $StdoutLog -Message "[$now] scheduler_skip reason=lock_exists"
    Write-SchedulerHeartbeat -Event "skip" -ExitCode 0 -ErrorMessage "lock_exists"
    exit 0
}

New-Item -ItemType File -Path $LockFile | Out-Null

try {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Utf8Log -Path $StdoutLog -Message "[$now] scheduler_start"
    Write-SchedulerHeartbeat -Event "start"

    $PythonExe = $null
    foreach ($candidate in $PythonCandidates) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
            $PythonExe = $candidate
            break
        }
    }

    if (-not $PythonExe) {
        $PythonExe = "python.exe"
    }

    $ProcessStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $ProcessStartInfo.FileName = $PythonExe
    $ProcessStartInfo.Arguments = ".\\main.py"
    $ProcessStartInfo.WorkingDirectory = $RepoRoot
    $ProcessStartInfo.UseShellExecute = $false
    $ProcessStartInfo.RedirectStandardOutput = $true
    $ProcessStartInfo.RedirectStandardError = $true

    try {
        $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        $ProcessStartInfo.StandardOutputEncoding = $Utf8NoBom
        $ProcessStartInfo.StandardErrorEncoding = $Utf8NoBom
    }
    catch {
    }

    $Process = New-Object System.Diagnostics.Process
    $Process.StartInfo = $ProcessStartInfo
    $null = $Process.Start()

    $CapturedStdout = $Process.StandardOutput.ReadToEnd()
    $CapturedStderr = $Process.StandardError.ReadToEnd()
    $Process.WaitForExit()

    if (-not [string]::IsNullOrWhiteSpace($CapturedStdout)) {
        Write-Utf8Log -Path $StdoutLog -Message ($CapturedStdout.TrimEnd("`r", "`n"))
    }

    if (-not [string]::IsNullOrWhiteSpace($CapturedStderr)) {
        Write-Utf8Log -Path $StderrLog -Message ($CapturedStderr.TrimEnd("`r", "`n"))
    }

    $LASTEXITCODE = $Process.ExitCode

    $ReportProcessStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $ReportProcessStartInfo.FileName = $PythonExe
    $ReportProcessStartInfo.Arguments = ".\tools\generate_symbol_validation_report.py --symbol ALGOUSDT"
    $ReportProcessStartInfo.WorkingDirectory = $RepoRoot
    $ReportProcessStartInfo.UseShellExecute = $false
    $ReportProcessStartInfo.RedirectStandardOutput = $true
    $ReportProcessStartInfo.RedirectStandardError = $true

    try {
        $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        $ReportProcessStartInfo.StandardOutputEncoding = $Utf8NoBom
        $ReportProcessStartInfo.StandardErrorEncoding = $Utf8NoBom
    }
    catch {
    }

    try {
        $ReportProcess = New-Object System.Diagnostics.Process
        $ReportProcess.StartInfo = $ReportProcessStartInfo
        $null = $ReportProcess.Start()

        $ReportStdout = $ReportProcess.StandardOutput.ReadToEnd()
        $ReportStderr = $ReportProcess.StandardError.ReadToEnd()
        $ReportProcess.WaitForExit()

        if (-not [string]::IsNullOrWhiteSpace($ReportStdout)) {
            Write-Utf8Log -Path $StdoutLog -Message ($ReportStdout.TrimEnd("`r", "`n"))
        }

        if (-not [string]::IsNullOrWhiteSpace($ReportStderr)) {
            Write-Utf8Log -Path $StderrLog -Message ($ReportStderr.TrimEnd("`r", "`n"))
        }
    }
    catch {
        $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Write-Utf8Log -Path $StderrLog -Message "[$now] symbol_validation_report_exception $_"
    }

    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Utf8Log -Path $StdoutLog -Message "[$now] scheduler_finish exit_code=$LASTEXITCODE"
    Write-SchedulerHeartbeat -Event "finish" -ExitCode $LASTEXITCODE

    exit $LASTEXITCODE
}
catch {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Utf8Log -Path $StderrLog -Message "[$now] scheduler_exception $_"
    Write-SchedulerHeartbeat -Event "exception" -ExitCode 1 -ErrorMessage "$_"
    exit 1
}
finally {
    if (Test-Path $LockFile) {
        Remove-Item $LockFile -ErrorAction SilentlyContinue
    }
}
