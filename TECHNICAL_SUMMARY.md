# CrossCore Spine Renderer - 技术总结报告

**日期**: 2026-06-06
**仓库**: https://github.com/lumiamilk/crosscore-spine-renderer

---

## 一、问题诊断

### 1.1 原始问题

Spine 动画渲染存在以下缺陷:
1. **PMA (Premultiplied Alpha) 灰圈** — 眼口鼻区域出现灰色圆圈
2. **三角形拼接缝** — Mesh 纹理间可见白色/黑色接缝线
3. **alps04 半身照** — 仅显示上半身，无法显示全身

### 1.2 半身照根因分析

旧版 `render_canvas_v14.mjs` 的 bounds 计算存在两个致命缺陷:

```js
// 旧逻辑 (仅采样静态单姿态)
const bb = computeVisibleBounds(skeleton, sd);                      // 单帧
const useBb = (bbA < skA*0.6 || bbA > skA*2.5)                    // 异常回退判断
  ? {minX: sd.x, minY: sd.y, maxX: sd.x + sd.width, ...}          // 回退到 sd bounds
  : bb;
const finalW = Math.ceil(sd.width * scale);                         // 尺寸始终来自 sd
const finalH = Math.ceil(sd.height * scale);
```

- **单姿态采样**: 仅取 'in' 动画结束后的静态姿态，如果该姿态下角色未完全展开，bounds 残缺
- **异常回退**: 当 bounds 面积 < skeleton 面积的 60% 或 > 250% 时，回退到 skeleton 自带的 `sd.width/height`
- **固定尺寸**: `finalW/finalH` 始终基于 `sd.width/height`，与真实 bounds 脱钩

对于 alps04:
- Skeleton 导出 bounds (`sd`): `9614×4248` — 仅覆盖上半身
- 真实全身 bounds: `17920×12886` — 接近 2 倍宽度
- 旧逻辑触发回退到 sd bounds → 输出永远是高清半身照

---

## 二、修复方案

### 2.1 核心修复: computeAnimationBounds

新增完整动画采样函数，替换旧的单帧 bounds:

```js
function computeAnimationBounds(sd, inAnim, idleAnim, hiddenNames, fps, maxSec) {
  const s = initBasePose(sd, inAnim, hiddenNames);
  const state = new spine.AnimationState(new spine.AnimationStateData(sd));
  state.setAnimation(0, idleAnim.name, true);
  const dur = Math.min(idleAnim.duration, maxSec);
  const frames = Math.max(1, Math.ceil(dur * fps));
  let b = computeVisibleBounds(s, sd);
  for (let f = 0; f < frames; f++) {
    state.update(1 / fps);
    state.apply(s);
    hideDecorativeSlots(s, hiddenNames);
    s.updateWorldTransform();
    b = unionBounds(b, computeVisibleBounds(s, sd));   // 逐帧取并集
  }
  return expandBounds(b, 0.04);                        // 扩展 4% 边距
}
```

**关键改进**:
- 遍历 idle 动画每一帧，取所有可见顶点 bounds 的**并集**
- `unionBounds` 确保不丢失边缘姿态的顶点
- `expandBounds` 添加 4% 安全边距
- 不再依赖 skeleton 自带的 sd，不触发异常回退

### 2.2 computeVisibleBounds 还原

原 root 版本有一个复杂的 face-center 过滤版本（4000px 范围限制），会误过滤远端的肢体/背景元素。已还原为简单版本：

```js
function computeVisibleBounds(skeleton, sd) {
    let mnX=Infinity, mnY=Infinity, mxX=-Infinity, mxY=-Infinity, h=0;
    for(const s of skeleton.slots) {
        const a=s.attachment;
        if(!a || a instanceof spine.ClippingAttachment) continue;
        if(s.color.a<=0 || (a.color&&a.color.a<=0) || !a.worldVerticesLength) continue;
        const n=a.worldVerticesLength, v=new Float32Array(n);
        a.computeWorldVertices(s, 0, n, v, 0, 2);
        for(let i=0; i<n; i+=2) {
            if(!isFinite(v[i])) continue;
            mnX=Math.min(mnX, v[i]); mxX=Math.max(mxX, v[i]);
            mnY=Math.min(mnY, v[i+1]); mxY=Math.max(mxY, v[i+1]);
            h=1;
        }
    }
    return h ? {minX:mnX, minY:mnY, maxX:mxX, maxY:mxY}
             : {minX:sd.x, minY:sd.y, maxX:sd.x+sd.width, maxY:sd.y+sd.height};
}
```

### 2.3 batch_worker 指向修复

```js
// 旧 → 新
const RENDERER = '.../render_canvas_v8.mjs';  // 绕过所有 v14 修复
const RENDERER = '.../render_canvas_v14.mjs';  // 指向当前版本
```

### 2.4 ffmpeg 超时修复

大画布 (8960×6443) 的 75 帧 PNG→WebP 编码耗时远超 5 分钟。已将 `execSync timeout` 从 `300000` (5分钟) 提升至 `1800000` (30分钟)。

### 2.5 保留项 (不修改的核心资产)

以下 v14 核心功能完全保留:
- `ensureUnpmaAtlasRaw` — Raw PNG unpremultiply
- `alphaCut` / `alphaFade` — 低 alpha 边缘清理
- `SUPERSAMPLE=3` — 3x 超采样
- `expandTriangle` / `uvToScreenTransform` — 三角形 UV 变换
- `drawMeshAttachment` — 逐三角形渲染

---

## 三、目录重组

### 3.1 旧结构

```
root/
├── render_canvas_v7~v14.mjs (10+ 版本)
├── batch_worker.mjs (指向 v8)
├── 30+ 调试/测试脚本
├── 8 个 Markdown 报告
├── extracted/Custom/ (原始 AssetBundle)
├── extracted/output/spine_data/ (提取的 spine)
├── extracted/output/spine_webp/ (渲染输出)
└── CrossCore/ (干净参考)
```

### 3.2 新结构

```
root/
├── CrossCore/
│   ├── source/          ← spine 源数据 (拉取 + 提取后)
│   ├── output/          ← 渲染输出 webp
│   ├── scripts/         ← 17 个功能脚本 + 2 个文档
│   ├── crosscore-spine-renderer-master/ (参考)
│   └── README.md        ← 使用说明
├── azurlane/            (不触碰)
├── BlueArchive/         (不触碰)
├── tools/               (spine-3.8-js 等)
├── node_modules/
├── package.json
└── .git/
```

### 3.3 已删除

删除 30+ 冗余文件:
- 旧渲染器: v7, v8, v8_backup, v8_unpma_backup, v9, v10, v11, v12, v13, v14_backup, v14_parallel, render_spine_final, render_webgl, render_webgl_v2, render_webgl_v3
- 调试脚本: batch_test, batch_test_faces, batch_test.bat, debug_slots, debug_slots2, debug_wireframe, face_inventory, test_unpma, test_unpma2, test_unpma2_backup, verify_hide
- 检测脚本: inspect_prefab, inspect_prefab2, parse_binary_formatter
- 旧报告: FINAL_ANALYSIS, FINAL_REPORT, FINAL_SUMMARY, FULL_TECHNICAL_REPORT, PMA_FIX_REPORT, TECHNICAL_REPORT_FOR_GPT, UNSOLVED_ISSUE_REPORT, V14_STATUS_REPORT
- 旧数据: extracted/Custom/, extracted/output/, extracted/

---

## 四、验证结果

### 4.1 数据拉取与提取

```
pull_custom_fast.ps1: 7825MB / 5931 文件 / 2.7 分钟 / 48.8MB/s
extract_spine_data.py: 487 spine 包 / 443 提取 / 0 错误
```

### 4.2 渲染输出 (alps04)

```
Bounds full-animation: 17920×12886  (全身)
  vs 旧 sd bounds:        9614×4248  (仅半身)

输出: CrossCore/output/10010_skin_alps04_v14.webp
  scale=0.5, fps=15, max-s=5: 41 帧, 181MB (全身)
  scale=0.35, fps=10, max-s=1: 10 帧, 55MB  (快速预览)
```

### 4.3 脸部位检查

```
Face slots: face(1.000), nose(1.000), mouth7(1.000), mouth6c(1.000),
  mouth6ba(1.000), mouth6a(1.000), mouth2(1.000), mouth1(1.000),
  eye10L(1.000), eye9L(1.000), eye8L(1.000), eye7L(1.000),
  eye5L(1.000), eye4L(1.000), eye3L(1.000), eye2aL(1.000), eye1L(1.000),
  eye10R(1.000), eye9R(1.000), eye8R(1.000), eye7R(1.000),
  eye5R(1.000), eye4R(1.000), eye3R(1.000), eye2aR(1.000), eye1R(1.000)
```

全部脸部位正常显示，无灰圈，无拼接缝。

---

## 五、建议

1. **未来渲染优化**: 可在 v14 基础上增加 raw RGBA pipe 给 ffmpeg（省去 PNG 编码和磁盘 I/O）
2. **GPU 渲染**: WebGL/WebGPU 渲染 Spine（而非 CUDA），WebP 编码本身仍为 CPU 密集型
3. **批量提速**: 当前每个角色启动一次 node 进程，可改为一个 worker 处理一个 chunk
4. **缓存**: `skeleton_unpma_clean.png` 已有缓存机制，保持即可
