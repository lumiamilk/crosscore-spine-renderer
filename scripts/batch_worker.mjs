// batch_worker.mjs — renders a chunk of dirs sequentially
import { execSync } from 'child_process';
const chunk = JSON.parse(process.argv[2]);
const workerId = process.argv[3];
const FPS = 15, SCALE = 0.7, MAX_S = 5, WEBP_Q = 100;
const RENDERER = 'D:/soft/to_run/ai/game_live2d/CrossCore/scripts/render_canvas_v14.mjs';
let ok = 0, fail = 0;
for (let i = 0; i < chunk.length; i++) {
    const d = chunk[i];
    try {
        const out = execSync(`node "${RENDERER}" --fps ${FPS} --scale ${SCALE} --max-s ${MAX_S} --webp-q ${WEBP_Q} --target "${d}"`, { stdio: 'pipe', timeout: 300000, maxBuffer: 10*1024*1024 });
        ok++;
    } catch(e) {
        fail++;
        if (fail <= 3) console.log(`W${workerId}_ERR: ${d} — ${e.stderr?.toString()?.slice(-200) || e.message}`);
    }
    if ((i+1) % 10 === 0) console.log(`W${workerId}: ${i+1}/${chunk.length}`);
}
console.log(`W${workerId}_DONE: ${ok} OK, ${fail} FAIL`);
