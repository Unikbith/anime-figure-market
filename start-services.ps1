<#
  ============================================================================
  次元模仓 · 本地服务一键启动（Windows PowerShell）
  ----------------------------------------------------------------------------
  本脚本只负责这三件事，Flask 与 Vue 由你自己在 IDE 里启动：

    [1/3] Redis  :6379   缓存 + Celery 消息队列 + JWT 黑名单 + 分布式锁
    [2/3] MinIO  :9000   商品图片对象存储（控制台 :9001）
    [3/3] Celery worker  异步任务消费者（用 .env 里的 VENV_PYTHON 启动）

  另外会顺便检测 MySQL :3306 是否在跑（Windows 服务，脚本不负责启动）。

  你自己在 IDE 里启动的部分：
    · PyCharm 运行 Flask/app.py                     → http://127.0.0.1:5000
    · VSCode 终端（目录 Vue/）npm run dev            → http://localhost:5173

  所有配置取自项目根目录 .env（模板见 .env.example），脚本不硬编码任何口令。
  运行： powershell -ExecutionPolicy Bypass -File start-services.ps1
  ============================================================================
#>
#Requires -Version 5.1
param(
  # Celery 并发模型：Windows 上用 solo 最稳；也可传 prefork / threads
  [string]$Pool = 'solo'
)

$ErrorActionPreference = 'Continue'

# ============================== 1. 加载 .env ==============================
$ProjectRoot = Split-Path $MyInvocation.MyCommand.Path
$FlaskDir    = Join-Path $ProjectRoot 'Flask'
$EnvFile     = Join-Path $ProjectRoot '.env'

if (Test-Path $EnvFile) {
  Write-Host ("[配置] 加载 " + $EnvFile) -ForegroundColor DarkGray
  foreach ($line in Get-Content -LiteralPath $EnvFile -Encoding UTF8) {
    $text = $line.Trim()
    if ($text -eq '' -or $text.StartsWith('#')) { continue }
    $eq = $text.IndexOf('=')
    if ($eq -lt 1) { continue }
    $key   = $text.Substring(0, $eq).Trim()
    $value = $text.Substring($eq + 1).Trim()
    Set-Item -Path ("env:" + $key) -Value $value
  }
} else {
  Write-Host '[配置] 未找到 .env —— 请先复制 .env.example 为 .env 并填写真实值' -ForegroundColor Yellow
}

$RedisPort    = if ($env:REDIS_PORT) { $env:REDIS_PORT } else { '6379' }
$MinioRoot    = if ($env:MINIO_ACCESS_KEY) { $env:MINIO_ACCESS_KEY } else { 'minioadmin' }
$MinioRootPwd = if ($env:MINIO_SECRET_KEY) { $env:MINIO_SECRET_KEY } else { 'minioadmin' }
$MinioConsole = if ($env:MINIO_CONSOLE_ADDRESS) { $env:MINIO_CONSOLE_ADDRESS } else { '127.0.0.1:9001' }

# ============================== 2. 工具函数 ==============================
function Test-TcpPort($port) {
  # 用 TcpClient 探测，不依赖 NetTCPIP 模块（部分环境没有 Get-NetTCPConnection）
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect('127.0.0.1', [int]$port, $null, $null)
    if ($async.AsyncWaitHandle.WaitOne(600)) {
      $client.EndConnect($async)
      return $true
    }
    return $false
  } catch {
    return $false
  } finally {
    $client.Close()
  }
}

function Write-Step($icon, $color, $text) {
  Write-Host ('  ' + $icon + ' ') -ForegroundColor $color -NoNewline
  Write-Host $text
}

function Resolve-Tool([string]$fromEnv, [string[]]$candidates) {
  if ($fromEnv -and (Test-Path $fromEnv)) { return $fromEnv }
  foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
  return $null
}

# 启动一个后台进程；端口已在监听则跳过（可重复执行）
function Start-OnPort($label, $port, $exe, $arguments, $workdir, $envVars) {
  if (-not $exe) {
    Write-Step '✗' 'Red' "$label 未配置可执行文件路径（请在 .env 中设置）"
    return
  }
  if (Test-TcpPort $port) {
    Write-Step '✓' 'Green' "$label 已在端口 $port 运行，跳过"
    return
  }
  if ($envVars) { foreach ($k in $envVars.Keys) { Set-Item -Path "env:$k" -Value $envVars[$k] } }
  # 工作目录留空时回退到可执行文件所在目录（Start-Process 不接受空的工作目录）
  if (-not $workdir) { $workdir = Split-Path $exe }
  $p = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $workdir `
        -WindowStyle Hidden -PassThru
  Start-Sleep -Seconds 2
  if (Test-TcpPort $port) {
    Write-Step '▶' 'Cyan' "$label 已启动 (PID $($p.Id)) → 端口 $port"
  } else {
    Write-Step '✗' 'Red' "$label 未能在端口 $port 监听，请检查可执行文件路径"
  }
}

# 已在该命令行运行则跳过（幂等）
function Test-Running($like) {
  $procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like $like }
  return @($procs).Count -gt 0
}

# ============================== 3. 启动服务 ==============================
Write-Host ''
Write-Host '╔════════════════════════════════════════════════════════════╗' -ForegroundColor Magenta
Write-Host '║            次元模仓 · 本地服务启动（Redis/Celery/MinIO）    ║' -ForegroundColor Magenta
Write-Host '╚════════════════════════════════════════════════════════════╝' -ForegroundColor Magenta
Write-Host ''

# --- Redis ---
Write-Host '[1/3] Redis — 缓存 / Celery 队列 / JWT 黑名单' -ForegroundColor Yellow
$RedisBin = Resolve-Tool $env:REDIS_BIN @(
  (Get-Command 'redis-server' -ErrorAction SilentlyContinue).Source
)
# 工作目录设为 Redis 自身目录，避免 dump.rdb 落到项目里
$RedisDir = if ($RedisBin) { Split-Path $RedisBin } else { $null }
Start-OnPort 'Redis' ([int]$RedisPort) $RedisBin @('--port', $RedisPort) $RedisDir $null

# --- MinIO ---
Write-Host '[2/3] MinIO — 商品图片对象存储（S3 兼容）' -ForegroundColor Yellow
$MinioBin  = Resolve-Tool $env:MINIO_BIN @(
  (Get-Command 'minio' -ErrorAction SilentlyContinue).Source
)
$MinioData = if ($env:MINIO_DATA) { $env:MINIO_DATA } else { Join-Path $ProjectRoot 'minio-data' }
if (-not (Test-Path $MinioData)) { New-Item -ItemType Directory -Path $MinioData -Force | Out-Null }
$minioArgs = @('server', $MinioData, '--address', '127.0.0.1:9000', '--console-address', $MinioConsole)
$minioEnv  = @{ MINIO_ROOT_USER = $MinioRoot; MINIO_ROOT_PASSWORD = $MinioRootPwd }
Start-OnPort 'MinIO' 9000 $MinioBin $minioArgs $null $minioEnv

# --- Celery ---
Write-Host '[3/3] Celery — 异步任务 worker（依赖 Redis）' -ForegroundColor Yellow
if (Test-Running '*celery*app.celery*') {
  Write-Step '✓' 'Green' 'Celery worker 已在运行，跳过'
} else {
  $VenvPython = Resolve-Tool $env:VENV_PYTHON @(
    (Join-Path $FlaskDir '.venv\Scripts\python.exe'),
    (Join-Path $ProjectRoot '.venv\Scripts\python.exe'),
    (Get-Command 'python' -ErrorAction SilentlyContinue).Source
  )
  if (-not $VenvPython) {
    Write-Step '✗' 'Red' '未找到 Python —— 请在 .env 中设置 VENV_PYTHON'
  } else {
    # 让 celery 能 import 到 Flask/app.py
    $env:PYTHONPATH = $FlaskDir
    $celeryArgs = @('-m', 'celery', '-A', 'app.celery', 'worker', '--loglevel=info', '--pool', $Pool)
    $cp = Start-Process -FilePath $VenvPython -ArgumentList $celeryArgs `
            -WorkingDirectory $FlaskDir -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 5
    if (Get-Process -Id $cp.Id -ErrorAction SilentlyContinue) {
      Write-Step '▶' 'Cyan' "Celery worker 已启动 (PID $($cp.Id), pool=$Pool)"
      Write-Host ("       解释器: " + $VenvPython) -ForegroundColor DarkGray
    } else {
      Write-Step '✗' 'Red' 'Celery worker 启动后立即退出 —— 多半是该解释器没装 celery，'
      Write-Host '       或在 PyCharm 终端手动跑一次看报错：celery -A app.celery worker --loglevel=info --pool=solo' -ForegroundColor DarkGray
    }
  }
}

# --- MySQL（仅检测）---
Write-Host ''
Write-Host '[检测] MySQL — 业务主数据库（用户 / 商品 / 订单）' -ForegroundColor Yellow
if (Test-TcpPort 3306) {
  Write-Step '✓' 'Green' 'MySQL 已在端口 3306 运行'
} else {
  Write-Step '!' 'Yellow' 'MySQL 未在 3306 监听 —— 请先在「服务」中启动 MySQL57'
}

# ============================== 4. 完成提示 ==============================
Write-Host ''
Write-Host '  服务就绪。接下来在 IDE 里启动前后端：' -ForegroundColor Magenta
Write-Host '   · PyCharm 运行 Flask/app.py                      → http://127.0.0.1:5000'
Write-Host '   · VSCode  终端（目录 Vue/）npm run dev            → http://localhost:5173'
Write-Host ("   · MinIO 控制台：http://" + $MinioConsole)
Write-Host ''
Write-Host '  停止： .\stop-services.ps1' -ForegroundColor DarkGray
Write-Host ''
