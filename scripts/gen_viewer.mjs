/**
 * Spine 查看器 - 生成独立 HTML 页面，浏览器直接播放
 * 用法: node gen_viewer.mjs
 */
import { readdirSync, readFileSync, existsSync, mkdirSync, writeFileSync } from 'fs';
import { join, basename } from 'path';

const SPINE_DIR = 'D:/soft/to_run/ai/game_live2d/CrossCore/source';
const OUTPUT_DIR = 'D:/soft/to_run/ai/game_live2d/CrossCore/output';

mkdirSync(OUTPUT_DIR, { recursive: true });

// 读取 3.8 spine JS
const CORE_JS = readFileSync(
    'D:/soft/to_run/ai/game_live2d/tools/spine-runtimes/spine-ts/build/spine-core.js',
    'utf-8'
);
const WEBGL_JS = readFileSync(
    'D:/soft/to_run/ai/game_live2d/tools/spine-runtimes/spine-ts/build/spine-webgl.js',
    'utf-8'
);

const dirs = readdirSync(SPINE_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => d.name)
    .sort();

// Generate index page
const listItems = dirs.map(name => {
    const jsonPath = join(SPINE_DIR, name, 'skeleton.json');
    if (!existsSync(jsonPath)) return '';
    try {
        const raw = JSON.parse(readFileSync(jsonPath, 'utf-8'));
        const anims = raw.animations ? Object.keys(raw.animations).join(', ') : 'none';
        return `<li><a href="${name}.html">${name}</a> <small>(${anims})</small></li>`;
    } catch {
        return `<li><a href="${name}.html">${name}</a></li>`;
    }
}).filter(Boolean).join('\n');

const INDEX_HTML = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>CrossCore Spine Viewer</title>
<style>
body{font-family:monospace;background:#1a1a2e;color:#eee;padding:20px}
a{color:#e94560;text-decoration:none}
a:hover{text-decoration:underline}
li{margin:8px 0}
small{color:#888}
h1{color:#0f3460}
</style></head><body>
<h1>CrossCore Spine Animations (${dirs.length})</h1>
<ul>${listItems}</ul>
</body></html>`;

writeFileSync(join(OUTPUT_DIR, 'index.html'), INDEX_HTML);

// Copy atlas & png for each animation
let generated = 0;
for (const name of dirs) {
    const dir = join(SPINE_DIR, name);
    const jsonPath = join(dir, 'skeleton.json');
    const atlasPath = join(dir, 'skeleton.atlas');
    const pngPath = join(dir, 'skeleton.png');

    if (!existsSync(jsonPath) || !existsSync(pngPath)) continue;

    const outDir = join(OUTPUT_DIR, name);
    mkdirSync(outDir, { recursive: true });

    // Copy files
    const jsonData = readFileSync(jsonPath, 'utf-8');
    const atlasData = readFileSync(atlasPath, 'utf-8');
    const pngData = readFileSync(pngPath);

    writeFileSync(join(outDir, 'skeleton.json'), jsonData);
    writeFileSync(join(outDir, 'skeleton.atlas'), atlasData);
    writeFileSync(join(outDir, 'skeleton.png'), pngData);

    // Fix atlas first line
    const atlasLines = atlasData.split('\n');
    if (atlasLines[0] && atlasLines[0].trim().endsWith('.png')) {
        atlasLines[0] = 'skeleton.png';
        writeFileSync(join(outDir, 'skeleton.atlas'), atlasLines.join('\n'));
    }

    // Generate player HTML
    const ANIM_HTML = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${name}</title>
<style>
*{margin:0;padding:0}
body{background:#1a1a2e;display:flex;flex-direction:column;align-items:center;min-height:100vh}
#canvas-container{margin-top:20px}
canvas{background:#1a1a2e}
#controls{margin:15px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
button{padding:8px 16px;cursor:pointer;background:#e94560;color:#fff;border:none;border-radius:4px;font-size:14px}
button:hover{background:#c23152}
select{padding:8px;font-size:14px;border-radius:4px}
#fps{margin-left:10px;color:#888}
a.back{color:#e94560;position:absolute;top:10px;left:10px}
</style></head><body>
<a class="back" href="index.html">← Back</a>
<div id="canvas-container"><canvas id="canvas"></canvas></div>
<div id="controls">
  <select id="animSelect"></select>
  <button id="playBtn">Pause</button>
  <button id="resetBtn">Reset</button>
  <span id="fps">0 FPS</span>
</div>

<script>${CORE_JS}</script>
<script>${WEBGL_JS}</script>
<script>
(async function() {
    const canvas = document.getElementById('canvas');
    const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: true });
    if (!gl) { document.body.innerHTML = 'WebGL not supported'; return; }

    // Load assets
    const [jsonText, atlasText, pngBlob] = await Promise.all([
        fetch('skeleton.json').then(r => r.text()),
        fetch('skeleton.atlas').then(r => r.text()),
        fetch('skeleton.png').then(r => r.blob())
    ]);

    const img = new Image();
    img.src = URL.createObjectURL(pngBlob);
    await new Promise(r => img.onload = r);

    // Setup Spine
    const tex = new spine.webgl.GLTexture(gl, img);
    const atlas = new spine.TextureAtlas(atlasText, tex);
    const loader = new spine.AtlasAttachmentLoader(atlas);
    const parser = new spine.SkeletonJson(loader);
    parser.scale = 1;
    const skeletonData = parser.readSkeletonData(jsonText);
    const skeleton = new spine.Skeleton(skeletonData);
    const stateData = new spine.AnimationStateData(skeletonData);
    const state = new spine.AnimationState(stateData);

    // Renderer
    const renderer = new spine.webgl.SceneRenderer(canvas, gl);
    renderer.camera.position.y = 100;

    // Set first animation
    const anims = skeletonData.animations;
    const select = document.getElementById('animSelect');
    anims.forEach((a, i) => {
        const opt = document.createElement('option');
        opt.value = i;
        opt.textContent = a.name + ' (' + a.duration.toFixed(1) + 's)';
        select.appendChild(opt);
    });
    state.setAnimation(0, anims[0].name, true);

    // Controls
    let playing = true;
    document.getElementById('playBtn').onclick = () => {
        playing = !playing;
        document.getElementById('playBtn').textContent = playing ? 'Pause' : 'Play';
    };
    document.getElementById('resetBtn').onclick = () => {
        state.setAnimation(0, anims[select.value].name, true);
    };
    select.onchange = () => {
        state.setAnimation(0, anims[select.value].name, true);
    };

    // Resize
    function resize() {
        const w = Math.max(800, Math.min(window.innerWidth - 40, 1200));
        const h = Math.round(w * skeletonData.height / skeletonData.width);
        canvas.width = w;
        canvas.height = h;
        renderer.camera.viewportWidth = w;
        renderer.camera.viewportHeight = h;
        skeleton.x = skeletonData.width / 2;
        skeleton.y = skeletonData.height * 0.55;
        skeleton.updateWorldTransform();
    }
    resize();
    window.onresize = resize;

    // Render loop
    let lastTime = Date.now();
    let frameCount = 0;
    let fpsTime = lastTime;
    function render() {
        const now = Date.now();
        const delta = (now - lastTime) / 1000;
        lastTime = now;

        if (playing) {
            state.update(Math.min(delta, 0.1));
            state.apply(skeleton);
        }
        skeleton.updateWorldTransform();

        gl.clearColor(0.1, 0.1, 0.18, 1);
        gl.clear(gl.COLOR_BUFFER_BIT);
        renderer.begin();
        renderer.drawSkeleton(skeleton, true);
        renderer.end();

        frameCount++;
        if (now - fpsTime >= 1000) {
            document.getElementById('fps').textContent = frameCount + ' FPS';
            frameCount = 0;
            fpsTime = now;
        }
        requestAnimationFrame(render);
    }
    requestAnimationFrame(render);
})();
</script></body></html>`;

    writeFileSync(join(OUTPUT_DIR, `${name}.html`), ANIM_HTML);
    generated++;

    if (generated % 100 === 0 || generated === dirs.length) {
        console.log(`  ${generated}/${dirs.length} viewer pages generated`);
    }
}

console.log(`\nDone! ${generated} viewer pages`);
console.log(`Open: ${OUTPUT_DIR}/index.html`);
