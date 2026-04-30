$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PreviousSymbol = $env:CNT_SYMBOL

try {
    $env:CNT_SYMBOL = "ALGOUSDT"
    & (Join-Path $RepoRoot "run.ps1")
    exit $LASTEXITCODE
}
finally {
    if ($null -eq $PreviousSymbol) {
        Remove-Item Env:\CNT_SYMBOL -ErrorAction SilentlyContinue
    }
    else {
        $env:CNT_SYMBOL = $PreviousSymbol
    }
}
