param(
    [string]$TaskName = "同花顺板块趋势早报",
    [string]$ConfigPath = (Join-Path $PSScriptRoot "config.yaml")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
$config = (Resolve-Path $ConfigPath).Path
$pythonLauncher = (Get-Command py.exe -ErrorAction Stop).Source

$arguments = "-3 -m sector_report --config `"$config`" run --send"
$action = New-ScheduledTaskAction `
    -Execute $pythonLauncher `
    -Argument $arguments `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "11:00"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$userId = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "A股交易日上午11点生成并发送同花顺行业板块趋势早报；程序内部检查交易日。"

Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Write-Host "已创建定时任务：$TaskName" -ForegroundColor Green
Write-Host "执行时间：周一至周五 11:00（程序会过滤A股休市日）"
Write-Host "工作目录：$root"
Write-Host "配置文件：$config"
Write-Host "请确认已设置用户环境变量 SMTP_AUTH_CODE，并保持电脑在发送时段开机联网。" -ForegroundColor Yellow
