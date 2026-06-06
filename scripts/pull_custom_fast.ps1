# ============================================================
# CrossCore Custom/ 文件快速拉取 (tar 流式传输)
# 用法:   .\pull_custom_fast.ps1          # 无压缩 (最快)
#         .\pull_custom_fast.ps1 -gzip    # gzip 压缩 (省流量)
# 速度:   预计 8-20 分钟 (vs 逐文件 30-60 分钟)
# 注意:   中断后需重新开始，需要断点续传请用 pull_custom.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$host.UI.RawUI.WindowTitle = "CrossCore - Fast Pull"

$adb     = "D:\soft\installed_soft\ld14\leidian\LDPlayer14\adb.exe"
$remote  = "/storage/emulated/0/Android/data/com.megagame.crosscore/files/Custom"
$local   = "D:\soft\to_run\ai\game_live2d\CrossCore\source"
$logfile = "D:\soft\to_run\ai\game_live2d\CrossCore\pull_fast.log"
$useGzip = $args -contains "-gzip"

# ---- 初始化 ----
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
@"
============================================================
CrossCore Fast Pull (tar stream)
Start:   $timestamp
Remote:  $remote
Local:   $local
Gzip:    $useGzip
============================================================

"@ | Out-File -LiteralPath $logfile -Encoding UTF8

function Write-Log {
    param([string]$msg)
    $line = "$(Get-Date -Format 'HH:mm:ss')  $msg"
    Write-Host $line
    $line | Out-File -LiteralPath $logfile -Encoding UTF8 -Append
}

# ---- 前置检查 ----
Write-Log "[1/5] Checking ADB..."
$devices = & $adb devices 2>&1 | Out-String
if ($devices -notmatch "(?m)device\s*$") {
    Write-Log "[ERROR] No emulator connected. Start LDPlayer first."
    pause; exit 1
}
Write-Log "[OK] emulator-5554"

Write-Log "[2/5] Remote size..."
$sizeStr = & $adb shell "du -sb '$remote' 2>&1" | Select-Object -First 1
if ($sizeStr -match "^(\d+)\s") { $totalBytes = [long]$matches[1] } else { $totalBytes = 0 }
Write-Log "  $([math]::Round($totalBytes/1GB,1)) GB / $([math]::Round($totalBytes/1MB,0)) MB"

Write-Log "[3/5] File count..."
$fileCount = (& $adb shell "ls -1 '$remote' 2>&1 | wc -l").Trim()
Write-Log "  $fileCount files"

# 创建本地目录，清空已有文件
Write-Log "[4/5] Preparing local dir..."
New-Item -ItemType Directory -Path $local -Force | Out-Null
Get-ChildItem -LiteralPath $local -File -ErrorAction SilentlyContinue | Remove-Item -Force

# ---- 流式拉取 ----
Write-Log "[5/5] Starting transfer..."
Write-Log ""

$startTime = Get-Date
$ext = if ($useGzip) { "tar.gz" } else { "tar" }
$tempArchive = "D:\soft\to_run\ai\game_live2d\CrossCore\custom.$ext"

try {
    # tar cf - -C <dir> .   → archive everything in <dir> to stdout
    # -C <dir>  = change to directory before archiving
    # .         = archive all files in that directory
    # f -       = output to stdout
    $tarFlags = if ($useGzip) { "czf" } else { "cf" }
    $tarCmd = "tar $tarFlags - -C $remote ."

    Write-Log "  Remote cmd: $tarCmd"
    Write-Log "  Local: $tempArchive"
    Write-Log ""

    $proc = Start-Process -FilePath $adb `
        -ArgumentList "exec-out", $tarCmd `
        -NoNewWindow -PassThru `
        -RedirectStandardOutput $tempArchive

    # Wait with periodic size check for progress
    while (-not $proc.HasExited) {
        Start-Sleep -Seconds 5
        if (Test-Path -LiteralPath $tempArchive) {
            $current = (Get-Item -LiteralPath $tempArchive).Length
            $pct = if ($totalBytes -gt 0) { [math]::Round($current * 100.0 / ($totalBytes * 0.9), 1) } else { 0 }
            $mb = [math]::Round($current / 1MB, 0)
            $elapsed = (Get-Date) - $startTime
            $speed = if ($elapsed.TotalSeconds -gt 0) { [math]::Round($current / $elapsed.TotalSeconds / 1MB, 1) } else { 0 }
            $eta = if ($speed -gt 0 -and $totalBytes -gt 0) { [math]::Round(($totalBytes - $current) / ($speed * 1MB), 0) } else { 0 }
            Write-Host "  `rReceived: ${mb}MB | ${pct}% | ${speed} MB/s | ETA ${eta}s" -NoNewline
        }
    }
    Write-Host ""  # newline

    $archiveSize = (Get-Item -LiteralPath $tempArchive).Length
    Write-Log "  Transfer done: $([math]::Round($archiveSize/1MB,1)) MB"

    # Extract
    Write-Log "  Extracting..."
    if ($useGzip) {
        tar xzf $tempArchive -C $local 2>&1 | Out-Null
    } else {
        tar xf $tempArchive -C $local 2>&1 | Out-Null
    }
    Write-Log "  Extraction done"

} catch {
    Write-Log "[ERROR] $_"
    Write-Log "Fallback: use pull_custom.ps1 for resumable per-file pull"
    pause; exit 1
} finally {
    if (Test-Path -LiteralPath $tempArchive) {
        Remove-Item -LiteralPath $tempArchive -Force
    }
}

$elapsed = (Get-Date) - $startTime
$downloaded = (Get-ChildItem -LiteralPath $local -File).Count
Write-Log ""
Write-Log "============================================================"
Write-Log "  Done"
Write-Log "============================================================"
Write-Log "  Remote:  $fileCount files, $([math]::Round($totalBytes/1GB,1)) GB"
Write-Log "  Local:   $downloaded files"
Write-Log "  Time:    $([math]::Round($elapsed.TotalMinutes,1)) min"
Write-Log "  Speed:   $([math]::Round($totalBytes/$elapsed.TotalSeconds/1MB,1)) MB/s"
Write-Log "============================================================"

Write-Host ""
Write-Host "Next step:" -ForegroundColor Yellow
Write-Host "  python D:\soft\to_run\ai\game_live2d\extract_assets.py" -ForegroundColor White
Write-Host ""
pause
