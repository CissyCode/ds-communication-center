# 스크랩 초안 도구 설치·업데이트. 관리자 권한 PowerShell에서 실행.
#   .\install_update.ps1                                  다운로드 폴더의 최신 scrapdraft_tool*.zip 을 D:\Multimedia\Scrapdraft 에 설치
#   .\install_update.ps1 -Zip "C:\경로\scrapdraft_tool_v23.zip" -Dest "D:\Multimedia\Scrapdraft"
# output 폴더(실행 기록·원장·저장본)는 그대로 두고, 프로그램 파일만 바꿉니다. 기존 config.yaml은 백업해 둡니다.
param(
  [string]$Zip = "",
  [string]$Dest = "D:\Multimedia\Scrapdraft"
)
$ErrorActionPreference = "Stop"
if (-not $Zip) {
  $cand = Get-ChildItem "$env:USERPROFILE\Downloads\scrapdraft_tool*.zip" -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $cand) { throw "다운로드 폴더에 scrapdraft_tool*.zip 이 없습니다. -Zip 으로 경로를 지정해 주세요." }
  $Zip = $cand.FullName
}
Write-Host "설치 파일: $Zip"
Write-Host "설치 위치: $Dest"
$tmp = Join-Path $env:TEMP ("scrapdraft_" + (Get-Date -Format "yyyyMMddHHmmss"))
Expand-Archive -Path $Zip -DestinationPath $tmp -Force
$src = Join-Path $tmp "scrapdraft_tool"
if (-not (Test-Path $src)) { $src = $tmp }

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$cfg = Join-Path $Dest "config.yaml"
if (Test-Path $cfg) {
  $bak = Join-Path $Dest ("config.yaml.bak_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
  Copy-Item $cfg $bak
  Write-Host "기존 설정 백업: $bak"
}
# output 폴더는 건드리지 않고 나머지를 덮어쓴다
Get-ChildItem $src -Force | Where-Object { $_.Name -ne "output" } | ForEach-Object {
  Copy-Item $_.FullName -Destination $Dest -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $Dest "output") | Out-Null
Remove-Item $tmp -Recurse -Force

Write-Host "필요한 패키지 설치…"
python -m pip install -q -r (Join-Path $Dest "requirements.txt")
$ver = (Select-String -Path (Join-Path $Dest "sm5_run.py") -Pattern 'VERSION = "(.+)"').Matches[0].Groups[1].Value
Write-Host "설치 완료: sm5_run $ver  ($Dest)"
Write-Host "새벽 예약을 이미 등록했다면 위치가 바뀐 경우 한 번 더: cd `"$Dest`"; .\register_schedule.ps1"
