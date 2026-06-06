# CrossCore Spine Renderer

交错战线 (CrossCore) 游戏 Spine 立绘提取与渲染工具链。从雷电模拟器拉取 AssetBundle、提取 Spine 骨骼数据、渲染为 animated WebP。

## 目录结构

```
CrossCore/
├── source/                             ← 拉取的源数据 (spine .json/.atlas/.png)
├── output/                             ← 渲染输出的 animated WebP
├── scripts/                            ← 全部脚本与文档
│   ├── render_canvas_v14.mjs           ← 核心渲染器
│   ├── batch_worker.mjs                ← 批量渲染 worker
│   ├── batch_parallel.mjs              ← 多进程批量调度
│   ├── gen_viewer.mjs                  ← 生成 HTML 查看器
│   ├── pull_custom_fast.ps1            ← 快速拉取 AssetBundle (推荐)
│   ├── pull_custom.ps1                 ← 断点续传拉取
│   ├── extract_spine_data.py           ← 提取 Spine 数据
│   ├── extract_assets.py               ← 通用资源提取
│   ├── extract_cspine.py               ← CSpine/Lua 脚本提取
│   ├── extract_lua_files.py            ← Lua 文件提取
│   ├── extract_lua_v2.py               ← Lua v2 提取
│   ├── extract_luascripts.py           ← Lua 脚本提取
│   ├── extract_prefab_data.py          ← Prefab 数据提取
│   ├── link_art.ps1                    ← 立绘链接整理
│   ├── organize_assets.ps1             ← 资源分类整理
│   ├── crosscore_bounds_batch_patch_notes.md  ← 补丁说明
│   └── gpt_advices_1.md                ← 修复建议
├── crosscore-spine-renderer-master/    ← 末次正确版本的干净副本 (参考)
└── crosscore-spine-renderer-master.zip
```

## 环境要求

- **Windows 10+** / WSL2
- **Node.js 18+** + npm
- **Python 3.x** + `UnityPy` (`pip install UnityPy`)
- **ffmpeg** (需在 PATH 中)
- **雷电模拟器** (ADB 路径: `D:\soft\installed_soft\ld14\leidian\LDPlayer14\adb.exe`)

```powershell
npm install
pip install UnityPy
```

## 快速开始

### 1. 从模拟器拉取数据

```powershell
# 快速拉取 (推荐，约 3 分钟 / 7.6GB)
.\CrossCore\scripts\pull_custom_fast.ps1

# 或断点续传
.\CrossCore\scripts\pull_custom.ps1
```

### 2. 提取 Spine 数据

```powershell
python CrossCore\scripts\extract_spine_data.py
```

### 3. 渲染单个角色

```powershell
node CrossCore\scripts\render_canvas_v14.mjs --target <角色名> --fps 15 --scale 0.7 --max-s 5 --webp-q 100
```

示例:
```powershell
# 阿尔卑斯 (alps04)
node CrossCore\scripts\render_canvas_v14.mjs --target alps04 --fps 15 --scale 0.7 --max-s 5 --webp-q 100

# 快速预览 (低分辨率)
node CrossCore\scripts\render_canvas_v14.mjs --target alps04 --fps 10 --scale 0.35 --max-s 1 --webp-q 80
```

### 4. 批量渲染全部角色

```powershell
# 4 个并行 worker
node CrossCore\scripts\batch_parallel.mjs 4
```

### 5. 生成 HTML 查看器

```powershell
node CrossCore\scripts\gen_viewer.mjs
```

## 技术细节

### 核心修复 (v14)

| 问题 | 修复方案 |
|------|----------|
| PMA 灰圈 | Raw PNG unpremultiply (绕过 Canvas 精度损失) |
| 低 alpha 边缘 | `alphaCut=8` 阈值清理 + `alphaFade=48` 渐变 |
| 三角拼接缝 | 3x supersampling + 0.5px 三角形扩展 |
| **半身照问题** | 完整 idle 动画逐帧 union bounds 采样 |

### 半身照根因

旧版只采样单个静态姿态的 bounds，且当 bounds 面积被判定"异常"时回退到 skeleton 自带的 `sd.width/height`。如果 skeleton 的导出 bounds 只有上半身，结果永远是高清半身照。

**修复**: `computeAnimationBounds()` 遍历 idle 动画每一帧，取所有可见顶点 bounds 的并集，外加 4% 边距。画布尺寸由完整动画 bounds 驱动。

### 角色对照

| 目录名 | 中文名 | 角色 ID |
|--------|--------|---------|
| `10010_skin_alps03` | 阿尔卑斯 (皮肤3) | 10010 |
| `10010_skin_alps04` | 阿尔卑斯 (皮肤4) | 10010 |
| `10010_skin_alps05` | 阿尔卑斯 (皮肤5) | 10010 |

## 获取无删减立绘

> 国内游戏通常有反和谐开关。以下为交错战线的设置方法：

使用 MT 文件管理器，找到交错战线 apk 安装目录:

```
手机内部存储/Android/data/com.megagame.crosscore/files
```

1. 找到 `internation.txt`（如果没有，手动创建一个）
2. 将文件内容从 `0` 改为 `1`，保存
3. 找到 `internation_close.txt` 并**删除它**（`internation.txt` **不能删**）
4. 重启游戏，游戏会自动下载新的无删减资源

## 已知问题

- 某些角色动画 bounds 极大 (如 alps04 全身 17920x12886)，渲染耗时较长
- ffmpeg WebP 编码大画布时需较长超时（已设为 30 分钟）
- Canvas2D CPU 渲染为主要性能瓶颈，大画幅建议降低 `--scale`

## License

MIT
