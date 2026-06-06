# ============================================================
# 角色立绘硬链接展平
# 将 characters/*/art/*/texture.png → art_flat/{role_id}_{variant}.png
# 使用硬链接，不额外占用磁盘空间
# ============================================================

$sourceDir = "D:\soft\to_run\ai\game_live2d\CrossCore\output\characters"
$targetDir = "D:\soft\to_run\ai\game_live2d\CrossCore\output\art_flat"
$logFile   = "D:\soft\to_run\ai\game_live2d\art_link.log"

New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"Hardlink Art Flatten - Start: $timestamp" | Out-File $logFile -Encoding UTF8

$total = 0
$linked = 0
$copied = 0
$failed = 0
$duplicates = @{}  # detect name collisions

# 扫描所有角色立绘
$artFiles = Get-ChildItem -LiteralPath $sourceDir -Recurse -File -Filter "texture.png" |
    Where-Object { $_.DirectoryName -match "\\art\\" }

foreach ($file in $artFiles) {
    $total++

    # 解析路径: characters/{role_id}/art/{variant}/texture.png
    $parts = $file.DirectoryName -replace [regex]::Escape($sourceDir), "" -split "\\" | Where-Object { $_ }
    # parts: ["1001", "art", "alps01"]

    if ($parts.Count -ge 3) {
        $roleId  = $parts[0]
        $variant = $parts[2]
    } elseif ($parts.Count -eq 1) {
        $roleId  = $parts[0]
        $variant = "default"
    } else {
        $roleId  = "unknown"
        $variant = $file.Directory.Name
    }

    $newName = "${roleId}_${variant}.png"

    # 处理重名
    if ($duplicates.ContainsKey($newName)) {
        $duplicates[$newName]++
        $newName = "${roleId}_${variant}_$($duplicates[$newName]).png"
    } else {
        $duplicates[$newName] = 0
    }

    $targetPath = Join-Path $targetDir $newName

    try {
        # 尝试硬链接
        New-Item -ItemType HardLink -Path $targetPath -Target $file.FullName -Force -ErrorAction Stop | Out-Null
        $linked++
    } catch {
        try {
            # 硬链接失败(跨卷/不支持) → 回退到复制
            Copy-Item -LiteralPath $file.FullName -Destination $targetPath -Force -ErrorAction Stop
            $copied++
        } catch {
            Write-Host "FAIL: $($file.FullName) -> $targetPath : $_"
            "FAIL: $($file.FullName) -> $targetPath : $_" | Out-File $logFile -Encoding UTF8 -Append
            $failed++
        }
    }

    if ($total % 100 -eq 0) {
        Write-Host "  $total files..."
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host " Total:    $total"
Write-Host " Hardlink: $linked (0 disk cost)"
Write-Host " Copied:   $copied"
Write-Host " Failed:   $failed"
Write-Host " Output:   $targetDir"
Write-Host "========================================"

"Done: $total files, $linked hardlinks, $copied copies, $failed failed" | Out-File $logFile -Encoding UTF8 -Append
