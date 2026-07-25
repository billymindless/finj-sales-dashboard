$ErrorActionPreference = "SilentlyContinue"

$root = git rev-parse --show-toplevel 2>$null
if (-not $root) { exit 0 }

Set-Location $root

$inside = git rev-parse --is-inside-work-tree 2>$null
if ($inside -ne "true") { exit 0 }

git pull --rebase --autostash 2>$null
if ($LASTEXITCODE -ne 0) {
    git pull 2>$null
}

exit 0
