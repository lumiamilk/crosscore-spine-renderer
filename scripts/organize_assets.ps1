# ============================================================
# Spine 动画纹理硬链接展平 + 清理无价值数据
# 用法: .\organize_assets.ps1
# ============================================================

$sourceDir = "D:\soft\to_run\ai\game_live2d\CrossCore\output\characters"
$spineDir  = "D:\soft\to_run\ai\game_live2d\CrossCore\output\spine_flat"
$logFile   = "D:\soft\to_run\ai\game_live2d\organize_assets.log"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"Organize Assets - Start: $timestamp" | Out-File $logFile -Encoding UTF8

# ============================================
# 1. Spine 纹理展平
# ============================================
Write-Host "=== Phase 1: Spine textures -> spine_flat/ ==="
New-Item -ItemType Directory -Path $spineDir -Force | Out-Null

$spineFiles = Get-ChildItem -LiteralPath $sourceDir -Recurse -File |
    Where-Object { $_.DirectoryName -match "\\spine\\" }

$total = 0
$linked = 0
$copied = 0
$failed = 0
$dupes = @{}

foreach ($file in $spineFiles) {
    $total++

    # 解析: characters/{role_id}/spine/{variant}/texture.png
    $rel = $file.DirectoryName.Substring($sourceDir.Length).TrimStart("\")
    $parts = $rel -split "\\"
    # parts: ["10010", "spine", "skin_alps03"]

    if ($parts.Count -ge 3) {
        $roleId  = $parts[0]
        $variant = $parts[2]
    } else {
        $roleId  = "unknown"
        $variant = ($parts -join "_")
    }

    $ext = $file.Extension
    if ($ext -eq "") { $ext = ".png" }
    $newName = "${roleId}_${variant}${ext}"

    if ($dupes.ContainsKey($newName)) {
        $dupes[$newName]++
        $newName = "${roleId}_${variant}_$($dupes[$newName])${ext}"
    } else {
        $dupes[$newName] = 0
    }

    $targetPath = Join-Path $spineDir $newName

    try {
        New-Item -ItemType HardLink -Path $targetPath -Target $file.FullName -Force -ErrorAction Stop | Out-Null
        $linked++
    } catch {
        try {
            Copy-Item -LiteralPath $file.FullName -Destination $targetPath -Force -ErrorAction Stop
            $copied++
        } catch {
            Write-Host "FAIL: $($file.Name) -> $newName"
            $failed++
        }
    }

    if ($total % 50 -eq 0) { Write-Host "  $total files..." }
}

Write-Host "Spine: $total files, $linked hardlinks, $copied copied, $failed failed"
"Spine done: $total files, $linked links, $copied copies, $failed failed" | Out-File $logFile -Encoding UTF8 -Append

# ============================================
# 2. 清理无价值数据
#    - effects/      (特效)
#    - scenes/       (场景)
#    - prefabs/      (Q版3D小人, 宿舍)
#    - ui_icons/     (UI头像图标)
#    - other/        (散装资源)
#    - characters/*/prefab/ (角色3D预制体)
#    保留:
#    - characters/*/art/     (角色立绘原画)
#    - characters/*/spine/   (Spine动画纹理)
#    - art_flat/             (展平的立绘)
#    - spine_flat/           (展平的Spine)
# ============================================
Write-Host ""
Write-Host "=== Phase 2: Cleanup worthless data ==="

$toDelete = @(
    "effects",
    "scenes",
    "prefabs",
    "ui_icons",
    "other"
)

$deletedSize = 0
foreach ($dir in $toDelete) {
    $path = Join-Path $sourceDir "..\..\" $dir  # output/{dir}
    # Resolve to absolute
    try {
        $absPath = (Resolve-Path $path -ErrorAction Stop).Path
    } catch {
        # try relative to output/
        $absPath = Join-Path "D:\soft\to_run\ai\game_live2d\CrossCore\output" $dir
    }

    if (Test-Path -LiteralPath $absPath) {
        $size = (Get-ChildItem -LiteralPath $absPath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $sizeMB = [math]::Round($size / 1MB, 1)
        $fileCount = (Get-ChildItem -LiteralPath $absPath -Recurse -File -ErrorAction SilentlyContinue).Count
        Write-Host "  Deleting $dir/ ($fileCount files, $sizeMB MB)"
        Remove-Item -LiteralPath $absPath -Recurse -Force -ErrorAction SilentlyContinue
        $deletedSize += $size
    } else {
        Write-Host "  $dir/ not found, skip"
    }
}

# 删除角色3D预制体 (characters/*/prefab/)
Write-Host "  Deleting characters/*/prefab/ ..."
$prefabDirs = Get-ChildItem -LiteralPath $sourceDir -Directory | ForEach-Object {
    Join-Path $_.FullName "prefab"
} | Where-Object { Test-Path $_ }
$prefabCount = 0
foreach ($pd in $prefabDirs) {
    $s = (Get-ChildItem -LiteralPath $pd -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    $deletedSize += $s
    $prefabCount += (Get-ChildItem -LiteralPath $pd -Recurse -File -ErrorAction SilentlyContinue).Count
    Remove-Item -LiteralPath $pd -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "  Removed $prefabCount 3D prefab files"

$deletedMB = [math]::Round($deletedSize / 1MB, 1)
Write-Host ""
Write-Host "=== Cleanup Complete ==="
Write-Host "  Disk freed: ~$deletedMB MB"
Write-Host ""
Write-Host "Remaining:"
Write-Host "  characters/*/art/     (character illustrations)"
Write-Host "  characters/*/spine/   (spine animation textures)"
Write-Host "  art_flat/             (flat hardlinks of art)"
Write-Host "  spine_flat/           (flat hardlinks of spine)"

"Cleanup done: freed ~$deletedMB MB" | Out-File $logFile -Encoding UTF8 -Append
Write-Host ""
Write-Host "Done at $(Get-Date -Format 'HH:mm:ss')"
