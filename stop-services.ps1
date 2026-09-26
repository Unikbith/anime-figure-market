<#
  ============================================================================
  次元模仓 · 停止本地服务（Windows PowerShell）
  ----------------------------------------------------------------------------
  停止 start-services.ps1 拉起的 Redis、MinIO、Celery worker。
  按「命令行特征」精确匹配，不会误杀其它 python / node 进程。
  MySQL 是 Windows 服务，保持常驻，不在此停止；
  Flask 与 Vue 由你在 IDE 里停止，本脚本也不碰。
  ============================================================================
#>
#Requires -Version 5.1

$ErrorActionPreference = 'Continue'

Write-Host ''
Write-Host '次元模仓 · 停止本地服务...' -ForegroundColor Magenta
Write-Host ''

# 顺序：先停消费者，再停依赖
$patterns = @(
  @{ name = 'Celery worker'; like = '*celery*app.celery*' },
  @{ name = 'MinIO';         like = '*minio*server*' },
  @{ name = 'Redis';         like = '*redis-server*' }
)

$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine }
foreach ($p in $patterns) {
  $matched = $procs | Where-Object { $_.CommandLine -like $p.like }
  if ($matched) {
    $matched | ForEach-Object {
      try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
    }
    Write-Host ("  ✓ {0} 已停止 ({1} 个进程)" -f $p.name, @($matched).Count) -ForegroundColor Green
  } else {
    Write-Host ("  · {0} 未运行" -f $p.name) -ForegroundColor DarkGray
  }
}

Write-Host ''
Write-Host '说明：MySQL 为系统服务，未在此停止；Flask / Vue 请在各自 IDE 中停止。' -ForegroundColor DarkGray
Write-Host ''
