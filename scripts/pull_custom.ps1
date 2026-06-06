# ============================================================
# CrossCore Custom/ AssetBundle 拉取脚本
# 从雷电模拟器拉取全部 AssetBundle 文件到本地
# 用法: 在新终端窗口中执行 .\pull_custom.ps1
# ============================================================

$ErrorActionPreference = "Continue"
$host.UI.RawUI.WindowTitle = "CrossCore - ADB Pull Custom/"

# ---- 路径配置 ----
$adb     = "D:\soft\installed_soft\ld14\leidian\LDPlayer14\adb.exe"
$remote  = "/storage/emulated/0/Android/data/com.megagame.crosscore/files/Custom"
$local   = "D:\soft\to_run\ai\game_live2d\CrossCore\source"
$logfile = "D:\soft\to_run\ai\game_live2d\CrossCore\pull_custom.log"

# ---- 初始化 ----
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logHeader = @"
============================================================
CrossCore ADB Pull Script
Start Time: $timestamp
Remote: $remote
Local:  $local
============================================================

"@
$logHeader | Out-File -LiteralPath $logfile -Encoding UTF8

function Write-Log {
    param([string]$msg)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $line
    $line | Out-File -LiteralPath $logfile -Encoding UTF8 -Append
}

# ---- 检查 ADB 连接 ----
Write-Log "========== Step 1: 检查 ADB 连接 =========="
$devices = & $adb devices 2>&1 | Out-String
Write-Log "ADB devices:`n$devices"

if ($devices -notmatch "(?m)device\s*$") {
    Write-Log "[ERROR] 未检测到模拟器连接，请确认雷电模拟器已启动！"
    Write-Host ""
    Write-Host "Press any key to exit..." -NoNewline
    $null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
Write-Log "[OK] 模拟器已连接"

# ---- 获取文件列表和大小 ----
Write-Log "========== Step 2: 获取远程文件列表 =========="
Write-Log "正在获取文件列表..."

$fileList = & $adb shell "cd '$remote' && ls -1p" 2>&1 | Where-Object { $_ -ne "" -and $_ -notmatch "/$" }
$totalFiles = $fileList.Count
Write-Log "共发现 $totalFiles 个文件"

# 获取每个文件大小（用于进度）
Write-Log "正在获取文件大小信息..."
$fileSizes = @{}
$totalBytes = 0

# 使用 stat 批量获取大小（更快）
$sizeOutput = & $adb shell "stat -c '%n:%s' '$remote'/*" 2>&1
foreach ($line in $sizeOutput) {
    if ($line -match "^(.*?):(\d+)$") {
        $name = $matches[1] -replace ".*/", ""
        $size = [long]$matches[2]
        $fileSizes[$name] = $size
        $totalBytes += $size
    }
}

# 如果 stat 不工作，回退到逐个 ls -l
if ($fileSizes.Count -eq 0) {
    Write-Log "stat 命令不可用，使用 ls -l 获取大小..."
    & $adb shell "ls -l '$remote'" 2>&1 | ForEach-Object {
        if ($_ -match "^\S+\s+\S+\s+\S+\s+\S+\s+(\d+)\s+\S+\s+\S+\s+(.+)$") {
            $size = [long]$matches[1]
            $name = $matches[2]
            if ($name -notmatch "/$") {
                $fileSizes[$name] = $size
                $totalBytes += $size
            }
        }
    }
}

$totalMB = [math]::Round($totalBytes / 1MB, 2)
$totalGB = [math]::Round($totalBytes / 1GB, 2)
Write-Log "总大小: $totalGB GB ($totalMB MB), 文件数: $($fileSizes.Count)"
Write-Log ""

# ---- 创建本地目录 ----
Write-Log "========== Step 3: 开始拉取文件 =========="
New-Item -ItemType Directory -Path $local -Force | Out-Null

# ---- 逐文件拉取 ----
$startTime = Get-Date
$downloaded = 0
$skipped = 0
$failed = 0
$bytesDone = 0
$errorFiles = @()

for ($i = 0; $i -lt $totalFiles; $i++) {
    $file = $fileList[$i]
    $remotePath = "$remote/$file"
    $localPath  = Join-Path $local $file
    $fileSize   = if ($fileSizes.ContainsKey($file)) { $fileSizes[$file] } else { 0 }

    # 检查是否已存在且大小一致
    if (Test-Path -LiteralPath $localPath) {
        $localSize = (Get-Item -LiteralPath $localPath).Length
        if ($localSize -eq $fileSize -and $fileSize -gt 0) {
            $skipped++
            $bytesDone += $fileSize
            # 每 200 个文件输出一次跳过信息
            if ($skipped % 200 -eq 0) {
                Write-Log "[SKIP] 已跳过 $skipped 个已存在文件..."
            }
            continue
        }
    }

    # 拉取文件
    try {
        $pullResult = & $adb pull $remotePath $localPath 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            $downloaded++
            $bytesDone += $fileSize
        } else {
            $failed++
            $errorFiles += $file
            Write-Log "[FAIL] $file -- $pullResult"
        }
    } catch {
        $failed++
        $errorFiles += $file
        Write-Log "[FAIL] $file -- $_"
    }

    # 进度显示 (每 10 个文件或最后一个)
    if ($i % 10 -eq 0 -or $i -eq $totalFiles - 1) {
        $elapsed = (Get-Date) - $startTime
        $pct = if ($totalBytes -gt 0) { [math]::Round($bytesDone * 100.0 / $totalBytes, 1) } else { 0 }
        $speed = if ($elapsed.TotalSeconds -gt 0) { [math]::Round($bytesDone / $elapsed.TotalSeconds / 1MB, 1) } else { 0 }
        $eta = if ($speed -gt 0) { [math]::Round(($totalBytes - $bytesDone) / 1MB / $speed, 0) } else { 0 }
        $doneMB = [math]::Round($bytesDone / 1MB, 1)
        $totalMB2 = [math]::Round($totalBytes / 1MB, 1)

        $progress = ("[{0}/{1}] {2}% | {3}/{4} MB | {5} MB/s | ETA {6}s | done:{7} skip:{8} fail:{9}" -f
            ($i+1), $totalFiles, $pct, $doneMB, $totalMB2, $speed, $eta, $downloaded, $skipped, $failed)
        Write-Log $progress
    }
}

# ---- 完成汇总 ----
$endTime = Get-Date
$totalTime = $endTime - $startTime
Write-Log ""
Write-Log "============================================================"
Write-Log "                        拉取完成"
Write-Log "============================================================"
Write-Log "总文件数:    $totalFiles"
Write-Log "成功拉取:    $downloaded"
Write-Log "已存在跳过:  $skipped"
Write-Log "失败:        $failed"
Write-Log "总耗时:      $([math]::Round($totalTime.TotalMinutes, 1)) 分钟"
Write-Log "完成时间:    $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Log "输出目录:    $local"
Write-Log "日志文件:    $logfile"

if ($failed -gt 0) {
    Write-Log ""
    Write-Log "失败文件列表:"
    foreach ($f in $errorFiles) {
        Write-Log "  - $f"
    }
}

Write-Log "============================================================"
Write-Host ""
Write-Host "拉取完成！日志已保存到: $logfile"
Write-Host "输出目录: $local"
Write-Host ""
Write-Host "Press any key to exit..." -NoNewline
$null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
