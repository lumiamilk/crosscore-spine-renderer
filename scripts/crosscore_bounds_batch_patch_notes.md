# crosscore-spine-renderer patch notes

## Findings

1. `render_canvas_v14.mjs` has the PMA / low-alpha / supersampling fixes. Keep these parts.
2. The alps04 half-body issue is in framing/bounds, not rendering quality:
   - line 124 computes a single-pose visible bounds;
   - line 125 falls back to `sd.x/y/width/height` when the computed bounds is considered too small/large;
   - lines 150-155 size the output from `sd.width/height` while centering/fitting by `useBb`.
   If alps04's exported skeleton bounds are only upper-body, or the correct full-body visible bounds triggers the fallback, the renderer will produce a high-resolution half-body forever.
3. `batch_worker.mjs` still calls `render_canvas_v8.mjs`, so batch rendering does not use the v14 fixes.

## Minimal replacement for bounds in render_canvas_v14.mjs

Add helpers after `computeVisibleBounds`:

```js
function unionBounds(a, b) {
  if (!a) return b;
  if (!b) return a;
  return {
    minX: Math.min(a.minX, b.minX),
    minY: Math.min(a.minY, b.minY),
    maxX: Math.max(a.maxX, b.maxX),
    maxY: Math.max(a.maxY, b.maxY),
  };
}

function expandBounds(b, ratio = 0.04) {
  const w = Math.max(1, b.maxX - b.minX);
  const h = Math.max(1, b.maxY - b.minY);
  return {
    minX: b.minX - w * ratio,
    minY: b.minY - h * ratio,
    maxX: b.maxX + w * ratio,
    maxY: b.maxY + h * ratio,
  };
}

function initBasePose(sd, inAnim, hiddenNames) {
  const s = new spine.Skeleton(sd);
  s.setToSetupPose();
  if (inAnim) inAnim.apply(s, 0, inAnim.duration, false, null, 1, 2, 1);
  hideDecorativeSlots(s, hiddenNames);
  s.updateWorldTransform();
  return s;
}

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
    b = unionBounds(b, computeVisibleBounds(s, sd));
  }

  return expandBounds(b, 0.04);
}
```

Replace the current line-120 to line-155 bounds/output block with:

```js
const useBb = computeAnimationBounds(sd, inAnim, idleAnim, hiddenNames, fps, maxSec);
console.log(`  Bounds full-animation: ${Math.round(useBb.maxX-useBb.minX)}x${Math.round(useBb.maxY-useBb.minY)} ` +
            `sd=${Math.round(sd.width)}x${Math.round(sd.height)}`);

const skeleton = initBasePose(sd, inAnim, hiddenNames);
const stateData = new spine.AnimationStateData(sd);
const state = new spine.AnimationState(stateData);
state.setAnimation(0, idleAnim.name, true);

const bw = Math.max(1, useBb.maxX - useBb.minX);
const bh = Math.max(1, useBb.maxY - useBb.minY);
const finalW = Math.max(1, Math.ceil(bw * scale));
const finalH = Math.max(1, Math.ceil(bh * scale));
const outW = finalW * SUPERSAMPLE;
const outH = finalH * SUPERSAMPLE;
const bbCx = (useBb.minX + useBb.maxX) / 2;
const bbCy = (useBb.minY + useBb.maxY) / 2;
const cs = Math.min(outW / bw, outH / bh);
```

This uses the same real animation state as rendering, does not fall back to possibly wrong exported skeleton bounds, and sizes the canvas from the actual full-body bounds.

## Batch fix

At minimum change `batch_worker.mjs`:

```js
const RENDERER = 'D:/soft/to_run/ai/game_live2d/render_canvas_v14.mjs';
const FPS = 15, SCALE = 0.7, MAX_S = 5, WEBP_Q = 100;
```

The faster version is to add a `--targets-json` argument to `render_canvas_v14.mjs` and call the renderer once per worker instead of once per character.
