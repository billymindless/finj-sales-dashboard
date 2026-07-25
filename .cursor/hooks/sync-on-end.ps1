$ErrorActionPreference = "SilentlyContinue"

$root = git rev-parse --show-toplevel 2>$null
if (-not $root) { exit 0 }

Set-Location $root

$inside = git rev-parse --is-inside-work-tree 2>$null
if ($inside -ne "true") { exit 0 }

$diff = git diff --quiet 2>$null; $diffExit = $LASTEXITCODE
$staged = git diff --cached --quiet 2>$null; $stagedExit = $LASTEXITCODE
if ($diffExit -eq 0 -and $stagedExit -eq 0) { exit 0 }

$hostName = $env:COMPUTERNAME
if (-not $hostName) { $hostName = "unknown" }
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"

git add -A
git commit -m "sync: auto-save from ${hostName} at ${timestamp}"
if ($LASTEXITCODE -ne 0) { exit 0 }

git push 2>$null
exit 0
