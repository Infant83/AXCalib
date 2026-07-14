[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("status", "next", "validate", "test", "eval")]
    [string]$Command = "status",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
$WorkspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $VenvPython) {
    $Python = $VenvPython
}
else {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

& $Python (Join-Path $WorkspaceRoot "harness\prep.py") $Command @RemainingArgs
exit $LASTEXITCODE
