# 조간 스크랩 초안 자동 실행 예약(Windows 작업 스케줄러). 관리자 권한 PowerShell에서 실행.
#   .\register_schedule.ps1                       기본 03:45, 04:03, 04:12
#   .\register_schedule.ps1 -Times "03:50","04:12" 시각 지정
#   .\register_schedule.ps1 -Remove               예약 삭제
# 조건: PC 켜짐, 로그인·화면 잠금 해제 상태, 스크랩마스터 실행·로그인 상태(화면 자동화이므로).
# 같은 날 여러 번 실행해도 이미 담긴 기사는 다시 담지 않고 새로 들어온 신문 기사만 추가합니다.
param(
  [string[]]$Times = @("03:45", "04:03", "04:12"),
  [string[]]$Sources = @("all"),
  [switch]$Remove
)
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$prefix = "DS조간스크랩초안_"

Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "$prefix*" } |
  ForEach-Object { Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false }
if ($Remove) { Write-Host "예약을 삭제했습니다."; exit 0 }

$py = (Get-Command python).Source
$src = ($Sources | ForEach-Object { "--source `"$_`"" }) -join " "
New-Item -ItemType Directory -Force -Path (Join-Path $dir "output") | Out-Null
$cmd = "/c set PYTHONIOENCODING=utf-8&& cd /d `"$dir`" && `"$py`" sm5_run.py $src >> output\run_log.txt 2>&1"

foreach ($t in $Times) {
  $name = $prefix + $t.Replace(":", "")
  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmd -WorkingDirectory $dir
  $trigger = New-ScheduledTaskTrigger -Daily -At $t
  $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
  Write-Host "등록: $name ($t)"
}
Write-Host "실행 기록: $dir\output\run_log.txt"
