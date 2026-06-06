我看了 zip。关键点很明确：

## 1. alps04 半身照不是分辨率问题，是 bounds / framing 问题

`render_canvas_v14.mjs` 里问题集中在这里：

```js
const bb=computeVisibleBounds(...)
const useBb=(bbA<skA*0.6||bbA>skA*2.5)
  ? {minX:sd.x,minY:sd.y,maxX:sd.x+sd.width,maxY:sd.y+sd.height}
  : bb;

const finalW=Math.ceil(sd.width*scale);
const finalH=Math.ceil(sd.height*scale);
```

也就是说：

1. 只用一个静态姿态算 bounds。
2. 如果 bounds 面积被认为异常，就回退到 `skeleton.json` 自带的 `sd.x/y/width/height`。
3. 输出尺寸也永远按 `sd.width / sd.height` 算。

如果 alps04 的导出 bounds 本来就偏向上半身，或者真正的全身 bounds 因为装饰/腿/椅子导致面积超过 `skA * 2.5`，代码就会回退到错误的 `sd` bounds。结果就是：**无论你把分辨率提高多少，都会得到高清半身照。**

正确修法是：**用实际渲染动画采样一遍，求整个 idle 动画的 union bounds，然后用这个 bounds 建画布和居中。不要回退到 sd bounds。**

------

## 2. 还有一个很容易踩的坑：batch_worker 仍然在跑 v8

`batch_worker.mjs` 里现在是：

```js
const RENDERER = 'D:/soft/to_run/ai/game_live2d/render_canvas_v8.mjs';
```

这会绕过 v14 的 raw unPMA、low-alpha cleanup、3x supersampling 等修复。

所以如果你用 `batch_parallel.mjs` 跑批量，出现旧的三角缝/灰圈不奇怪：它根本没用 GitHub 里较新的 v14。

至少改成：

```js
const RENDERER = 'D:/soft/to_run/ai/game_live2d/render_canvas_v14.mjs';
const FPS = 15, SCALE = 0.7, MAX_S = 5, WEBP_Q = 100;
```

------

## 3. 建议只改取景代码，不要碰已经修好的 mesh 渲染

你这份仓库里，v14 的 PMA 修复和三角缝处理是核心资产。现在不要再让模型改这些部分：

```text
ensureUnpmaAtlasRaw
alphaCut / alphaFade
SUPERSAMPLE
EXPAND_PX
drawMeshAttachment / triangle UV transform
```

只改：

```text
compute bounds
output width/height
world → canvas transform
batch_worker 指向的 renderer
```

------

## 4. 我整理了一个补丁说明文件

我把具体替换思路写成了一个 patch notes 文件，里面包括：

- alps04 半身照的代码根因
- `computeAnimationBounds()` 采样整个 idle 动画的替换代码
- `batch_worker.mjs` 应该改到 v14 的位置

下载这里：

[查看补丁说明](sandbox:/mnt/data/crosscore_bounds_batch_patch_notes.md)

------

## 5. CUDA 加速这条路意义不大

当前瓶颈大概率是：

```text
Node.js Canvas2D CPU 渲染
PNG 帧写盘
ffmpeg libwebp_anim CPU 编码
每个角色重复启动 node 进程
```

CUDA 不会自动加速这些。RTX 2080 Ti / RTX 3060 对这条 Canvas2D → animated WebP 管线帮助有限。

更有效的提速顺序是：

1. **先修 batch_worker 指向 v14**，避免跑旧代码。
2. **不要每个角色启动一次 node**。现在 worker 对每个目录都 `execSync node render_canvas...`，启动开销很大。应改成一个 worker 进程处理一个 chunk。
3. **缓存 `skeleton_unpma_clean.png`**，这个 v14 已经做了，保留。
4. **把 PNG 帧写盘改为 raw RGBA pipe 给 ffmpeg**，省掉 PNG 编码和磁盘 I/O。
5. 真要用 GPU，应该考虑 WebGL/WebGPU 渲染 Spine，而不是 CUDA；WebP 编码本身仍然主要是 CPU。

最短修复路线：从 GitHub 备份版开新分支，先改 `batch_worker` 指向 v14，再把 v14 的 bounds 改成“采样完整动画 union bounds”。不要再重写 mesh 渲染核心。