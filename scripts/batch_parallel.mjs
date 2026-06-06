// batch_parallel.mjs — spawns N workers, each renders a chunk of dirs
import { readdirSync } from 'fs';
import { fork } from 'child_process';
import os from 'os';

const SPINE_DIR = 'D:/soft/to_run/ai/game_live2d/CrossCore/source';
const WORKER_FILE = 'D:/soft/to_run/ai/game_live2d/CrossCore/scripts/batch_worker.mjs';

const workers = parseInt(process.argv[2]) || Math.min(8, os.cpus().length);

const dirs = readdirSync(SPINE_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => d.name)
    .sort();

console.log(`Total: ${dirs.length} dirs, ${workers} workers`);

const chunkSize = Math.ceil(dirs.length / workers);
let done = 0, ok = 0, fail = 0;
const start = Date.now();

for (let i = 0; i < workers; i++) {
    const chunk = dirs.slice(i * chunkSize, (i + 1) * chunkSize);
    if (!chunk.length) break;

    const child = fork(WORKER_FILE, [JSON.stringify(chunk), String(i)], { stdio: 'pipe', silent: false });
    child.stdout.on('data', d => process.stdout.write(d));
    child.stderr.on('data', d => process.stderr.write(d));
    child.on('close', code => {
        done++;
        ok += (code === 0) ? 1 : 0;
        fail += (code !== 0) ? 1 : 0;
        if (done === Math.min(workers, Math.ceil(dirs.length / chunkSize))) {
            console.log(`\nAll done in ${Math.round((Date.now()-start)/1000)}s`);
        }
    });
}
