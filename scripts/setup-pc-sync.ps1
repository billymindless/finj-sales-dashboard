# PC(Windows)에서 Cursor Git 자동 동기화를 설정/검증합니다.
# 사용법: PowerShell에서 프로젝트 루트로 이동 후
#   powershell -ExecutionPolicy Bypass -File scripts/setup-pc-sync.ps1

$ErrorActionPreference = "Stop"

function Write-Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

function Write-Ok($message) {
    Write-Host "[OK] $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "[WARN] $message" -ForegroundColor Yellow
}

function Write-Fail($message) {
    Write-Host "[FAIL] $message" -ForegroundColor Red
}

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

Write-Step "프로젝트 경로: $projectRoot"

Write-Step "1. Git 설치 확인"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Fail "Git이 설치되어 있지 않습니다. https://git-scm.com/download/win 에서 설치하세요."
    exit 1
}
Write-Ok "Git $(git --version)"

Write-Step "2. Git 사용자 정보 확인"
$userName = git config user.name
$userEmail = git config user.email
if (-not $userName -or -not $userEmail) {
    Write-Warn "Git user.name / user.email 이 없습니다."
    Write-Host "  git config --global user.name `"Your Name`""
    Write-Host "  git config --global user.email `"you@example.com`""
} else {
    Write-Ok "Git 사용자: $userName <$userEmail>"
}

Write-Step "3. 원격 저장소 확인"
$remote = git remote get-url origin 2>$null
if (-not $remote) {
    Write-Fail "origin 원격 저장소가 없습니다."
    exit 1
}
Write-Ok "origin = $remote"

Write-Step "4. 최신 코드 pull"
$branch = git branch --show-current
Write-Host "현재 브랜치: $branch"
git pull --rebase --autostash 2>$null
if ($LASTEXITCODE -ne 0) {
    git pull
}
if ($LASTEXITCODE -ne 0) {
    Write-Fail "git pull 실패. 인증 또는 충돌을 확인하세요."
    exit 1
}
Write-Ok "pull 완료"

Write-Step "5. Cursor Hook 파일 확인"
$requiredFiles = @(
    ".cursor/hooks.json",
    ".cursor/hooks.windows.json",
    ".cursor/hooks/sync-on-start.ps1",
    ".cursor/hooks/sync-on-end.ps1",
    ".cursor/plans"
)
foreach ($file in $requiredFiles) {
    if (-not (Test-Path (Join-Path $projectRoot $file))) {
        Write-Fail "누락: $file"
        exit 1
    }
}
Write-Ok "Hook 파일 모두 존재"

Write-Step "6. Windows용 hooks.json 적용"
Copy-Item -Path ".cursor/hooks.windows.json" -Destination ".cursor/hooks.json" -Force
Write-Ok "hooks.json -> PowerShell Hook으로 설정"

Write-Step "7. push 인증 테스트"
git push --dry-run 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Warn "push 인증이 아직 설정되지 않았습니다."
    Write-Host "  HTTPS: Git Credential Manager 또는 Personal Access Token"
    Write-Host "  SSH: ssh-keygen 후 GitHub에 공개키 등록"
    Write-Host "  테스트: git push --dry-run"
} else {
    Write-Ok "push 인증 정상"
}

Write-Step "8. Cursor 설정 체크리스트"
Write-Host @"

PC에서 마무리할 항목:
  1. Cursor에서 이 프로젝트 폴더 열기
  2. Settings -> Hooks 탭에서 Hook 로드 확인
  3. Settings -> Sync 켜기 (User Rules, 확장 등)
  4. Plan 만든 후 ... 메뉴 -> Save to Workspace
     -> .cursor/plans/*.plan.md 로 저장되면 Git으로 동기화됨
  5. Hook이 안 보이면 Cursor 재시작

동작:
  - 에이전트 세션 시작: git pull
  - 에이전트 세션 종료: 변경 있으면 git commit + push

"@

Write-Ok "PC 동기화 설정 스크립트 완료"
