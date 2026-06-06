/**
 * Canvas2D v14 - Raw PNG unpremultiply + low-alpha cleanup + 3x supersampling + small expansion.
 * Fixes: (1) PMA grey circles via raw PNG unPMA, (2) low-alpha edge cleanup,
 *        (3) triangle seams via 3x supersampling + 0.5px expansion.
 */
import { readdirSync, readFileSync, existsSync, mkdirSync, writeFileSync, rmSync, statSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';
import c from '@napi-rs/canvas';
const { createCanvas, loadImage } = c;
import { PNG } from 'pngjs';
import vm from 'vm';

const SPINE_DIR = 'D:/soft/to_run/ai/game_live2d/CrossCore/source';
const OUTPUT_DIR = 'D:/soft/to_run/ai/game_live2d/CrossCore/output';
const TEMP_DIR = 'D:/soft/to_run/ai/game_live2d/CrossCore/output/_temp_frames';
const CORE_JS = 'D:/soft/to_run/ai/game_live2d/CrossCore/spine-3.8-js/spine-core.js';

const args = process.argv.slice(2);
const FPS = parseInt(args[args.indexOf('--fps') + 1]) || 15;
const SCALE = parseFloat(args[args.indexOf('--scale') + 1]) || 1.0;
const MAX_SEC = parseInt(args[args.indexOf('--max-s') + 1]) || 5;
const WEBP_Q = parseInt(args[args.indexOf('--webp-q') + 1]) || 90;
const TARGET = args.includes('--target') ? args[args.indexOf('--target') + 1] : null;
const SUPERSAMPLE = 3;
const EXPAND_PX = 0.5;

// Load spine
const coreCode = readFileSync(CORE_JS, 'utf-8');
const sandbox = {
    window: {}, document: { createElement: () => ({}), createElementNS: () => ({}) },
    navigator: { userAgent: 'node' }, HTMLImageElement: class {}, Image: class {},
    XMLHttpRequest: class {}, console, setTimeout, setInterval, clearTimeout, clearInterval,
};
vm.createContext(sandbox);
new vm.Script(coreCode).runInContext(sandbox);
const spine = sandbox.spine;
spine.FakeTexture.prototype.setFilters = function() {};
spine.FakeTexture.prototype.setWraps = function() {};

mkdirSync(OUTPUT_DIR, { recursive: true });
mkdirSync(TEMP_DIR, { recursive: true });

const staticDecoPattern = /^red[LR]$|^eye0[A-C][LR]$|^facered\d+$|^buzui[_\d]*$|^mouth3[aAbB]$|^mouth03[AaBb]$|^mouth_shy[\d_]*$|^mouth_think[\d_]*$|^mouth0[4-6]$|^eye_jing|^eye_kaixin|^eye_nu[\d_]*$|glasses|quan/i;

// ===== Raw PNG unpremultiply with low-alpha cleanup =====
function ensureUnpmaAtlasRaw(dir, pngPath) {
    const outPath = join(dir, 'skeleton_unpma_clean.png');
    if (existsSync(outPath)) return outPath;
    
    console.log(`  Creating raw unpremultiplied atlas...`);
    const png = PNG.sync.read(readFileSync(pngPath));
    const d = png.data;
    const alphaCut = 8;      // alpha <= 8: set to fully transparent
    const alphaFade = 48;    // alpha 8-48: fade out

    for (let i = 0; i < d.length; i += 4) {
        const a = d[i + 3];

        // 1) Raw unpremultiply (no Canvas precision loss)
        if (a > 0 && a < 255) {
            d[i]     = Math.min(255, Math.round(d[i]     * 255 / a));
            d[i + 1] = Math.min(255, Math.round(d[i + 1] * 255 / a));
            d[i + 2] = Math.min(255, Math.round(d[i + 2] * 255 / a));
        }

        // 2) Low-alpha cleanup: remove faint edges that cause remaining circles
        if (a > 0 && a < alphaFade) {
            if (a <= alphaCut) {
                // Below threshold: fully erase
                d[i] = 0; d[i + 1] = 0; d[i + 2] = 0; d[i + 3] = 0;
            } else {
                // Fade out between alphaCut and alphaFade
                const t = (a - alphaCut) / (alphaFade - alphaCut);
                d[i + 3] = Math.round(a * t);
            }
        }
    }

    writeFileSync(outPath, PNG.sync.write(png));
    return outPath;
}

// ===== Math =====
function expandTriangle(x0,y0,x1,y1,x2,y2,pad){
    const cx=(x0+x1+x2)/3,cy=(y0+y1+y2)/3;
    const e=(x,y)=>{const dx=x-cx,dy=y-cy;const l=Math.hypot(dx,dy)||1;return[x+dx/l*pad,y+dy/l*pad]};
    return[e(x0,y0),e(x1,y1),e(x2,y2)];
}

function uvToScreenTransform(x0,y0,x1,y1,x2,y2,u0,v0,u1,v1,u2,v2){
    const d=u0*(v1-v2)+u1*(v2-v0)+u2*(v0-v1);if(Math.abs(d)<1e-6)return null;
    const i=1/d;
    return{a:(x0*(v1-v2)+x1*(v2-v0)+x2*(v0-v1))*i,c:(x0*(u2-u1)+x1*(u0-u2)+x2*(u1-u0))*i,tx:(x0*(u1*v2-u2*v1)+x1*(u2*v0-u0*v2)+x2*(u0*v1-u1*v0))*i,b:(y0*(v1-v2)+y1*(v2-v0)+y2*(v0-v1))*i,d:(y0*(u2-u1)+y1*(u0-u2)+y2*(u1-u0))*i,ty:(y0*(u1*v2-u2*v1)+y1*(u2*v0-u0*v2)+y2*(u0*v1-u1*v0))*i};
}

function computeVisibleBounds(skeleton,sd){
    let mnX=Infinity,mnY=Infinity,mxX=-Infinity,mxY=-Infinity,h=0;
    for(const s of skeleton.slots){const a=s.attachment;if(!a||a instanceof spine.ClippingAttachment)continue;if(s.color.a<=0||(a.color&&a.color.a<=0)||!a.worldVerticesLength)continue;const n=a.worldVerticesLength,v=new Float32Array(n);a.computeWorldVertices(s,0,n,v,0,2);for(let i=0;i<n;i+=2){if(!isFinite(v[i]))continue;mnX=Math.min(mnX,v[i]);mxX=Math.max(mxX,v[i]);mnY=Math.min(mnY,v[i+1]);mxY=Math.max(mxY,v[i+1]);h=1;}}
    return h?{minX:mnX,minY:mnY,maxX:mxX,maxY:mxY}:{minX:sd.x,minY:sd.y,maxX:sd.x+sd.width,maxY:sd.y+sd.height};
}

function collectHiddenSlotNames(rawJson){const r=new Set();for(const s of rawJson.slots||[]){if(staticDecoPattern.test(s.name||''))r.add(s.name);}return r;}

function hideDecorativeSlots(skeleton,names){let c=0;for(const s of skeleton.slots){if(!names.has(s.data.name))continue;if(s.attachment===null)continue;s.attachment=null;s.color.a=0;c++;}return c;}

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

async function renderAnimation(dirName,fps,scale,maxSec){
    const d=join(SPINE_DIR,dirName),jp=join(d,'skeleton.json'),pp=join(d,'skeleton.png'),ap=join(d,'skeleton.atlas');
    if(!existsSync(jp)||!existsSync(pp))return null;
    const jsonText=readFileSync(jp,'utf-8'),rawJson=JSON.parse(jsonText),atlasText=readFileSync(ap,'utf-8');
    const pm=atlasText.match(/size:\s*(\d+)\s*,\s*(\d+)/);
    const pw=pm?parseInt(pm[1]):4096,ph=pm?parseInt(pm[2]):4096;
    const ft=new spine.FakeTexture({width:pw,height:ph}),atlas=new spine.TextureAtlas(atlasText,l=>ft);
    const sd=new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(jsonText);
    const hiddenNames=collectHiddenSlotNames(rawJson);
    const inAnim=sd.animations.find(a=>a.name==='in');
    const idleAnim=sd.animations.find(a=>a.name==='idle')||sd.animations[0];
    if(!idleAnim)return null;

    // Compute full-animation union bounds (sample entire idle loop)
    const bb=computeAnimationBounds(sd, inAnim, idleAnim, hiddenNames, fps, maxSec);
    console.log(`  Bounds full-animation: ${Math.round(bb.maxX-bb.minX)}x${Math.round(bb.maxY-bb.minY)} ` +
                `sd=${Math.round(sd.width)}x${Math.round(sd.height)}`);

    // Animation state: apply 'in' to skeleton, then idle
    const skeleton=initBasePose(sd, inAnim, hiddenNames);
    const stateData=new spine.AnimationStateData(sd);
    const state=new spine.AnimationState(stateData);
    state.setAnimation(0,idleAnim.name,true);

    // DEBUG: print visible face slots on frame 0
    state.update(1/fps);state.apply(skeleton);
    hideDecorativeSlots(skeleton,hiddenNames);skeleton.updateWorldTransform();
    const faceSlots = [];
    for(const slot of skeleton.slots){
        const att=slot.attachment;if(!att)continue;
        const name=`${slot.data.name}`;
        if(!/^(mouth|buzui|nose|eye|face|red)/i.test(name))continue;
        const alpha=skeleton.color.a*slot.color.a*(att.color?att.color.a:1);
        if(alpha<=0.001)continue;
        faceSlots.push({slot:slot.data.name,alpha:alpha.toFixed(3),verts:att.worldVerticesLength/2});
    }
    if(faceSlots.length)console.log(`  Face slots: ${faceSlots.map(s=>s.slot+'('+s.alpha+')').join(', ')}`);

    // Canvas: crop to face-centered body bounds
    const cw=Math.max(1,bb.maxX-bb.minX),ch=Math.max(1,bb.maxY-bb.minY);
    const maxSSDim=8192;
    const effectiveSS=Math.max(1,(cw*scale>maxSSDim)?1:Math.min(SUPERSAMPLE,Math.floor(maxSSDim/(cw*scale))));
    const finalW=Math.max(1,Math.ceil(cw*scale));
    const finalH=Math.max(1,Math.ceil(ch*scale));
    const outW=finalW*effectiveSS,outH=finalH*effectiveSS;
    const bbCx=(bb.minX+bb.maxX)/2;
    const bbCy=(bb.minY+bb.maxY)/2;
    const cs=Math.min(outW/cw,outH/ch);

    const unpmaPath=ensureUnpmaAtlasRaw(d,pp);
    const texImg=await loadImage(unpmaPath);

    const dur=Math.min(idleAnim.duration,maxSec),totalFrames=Math.max(1,Math.ceil(dur*fps));
    const frameDir=join(TEMP_DIR,dirName);mkdirSync(frameDir,{recursive:true});
    const canvas=createCanvas(outW,outH),ctx=canvas.getContext('2d');
    const canvasFinal=createCanvas(finalW,finalH),ctxFinal=canvasFinal.getContext('2d');
    ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
    ctxFinal.imageSmoothingEnabled=true;ctxFinal.imageSmoothingQuality='high';

    for(let f=0;f<totalFrames;f++){
        state.update(1/fps);state.apply(skeleton);
        hideDecorativeSlots(skeleton,hiddenNames);skeleton.updateWorldTransform();

        ctx.setTransform(1,0,0,1,0,0);
        ctx.clearRect(0,0,outW,outH);
        ctx.setTransform(cs,0,0,-cs,outW/2-bbCx*cs,outH/2+bbCy*cs);

        let clipEnd=null;
        for(const slot of skeleton.slots){
            const att=slot.attachment;if(!att)continue;
            if(att instanceof spine.ClippingAttachment){
                const n=att.worldVerticesLength,cv=new Float32Array(n);
                att.computeWorldVertices(slot,0,n,cv,0,2);
                ctx.save();ctx.beginPath();ctx.moveTo(cv[0],cv[1]);
                for(let vi=2;vi<n;vi+=2)ctx.lineTo(cv[vi],cv[vi+1]);
                ctx.closePath();ctx.clip();clipEnd=att.endSlot;continue;
            }
            const alpha=skeleton.color.a*slot.color.a*(att.color?att.color.a:1);
            if(alpha<=0)continue;
            ctx.globalAlpha=alpha;
            const isAdd=(()=>{try{return slot.data.blendMode===spine.BlendMode.Additive}catch{return false}})();
            ctx.globalCompositeOperation=isAdd?'lighter':'source-over';

            if(att instanceof spine.MeshAttachment){
                const n=att.worldVerticesLength,v=new Float32Array(n);
                att.computeWorldVertices(slot,0,n,v,0,2);
                const uvs=att.uvs,tris=att.triangles,iW=texImg.width,iH=texImg.height;
                for(let i=0;i<tris.length;i+=3){
                    const i0=tris[i]*2,i1=tris[i+1]*2,i2=tris[i+2]*2;
                    const sx0=v[i0],sy0=v[i0+1],sx1=v[i1],sy1=v[i1+1],sx2=v[i2],sy2=v[i2+1];
                    if(isNaN(sx0))continue;
                    const T=uvToScreenTransform(sx0,sy0,sx1,sy1,sx2,sy2,uvs[i0]*iW,uvs[i0+1]*iH,uvs[i1]*iW,uvs[i1+1]*iH,uvs[i2]*iW,uvs[i2+1]*iH);
                    if(!T)continue;
                    const pad=EXPAND_PX/cs*SUPERSAMPLE/effectiveSS;
                    const[e0,e1,e2]=expandTriangle(sx0,sy0,sx1,sy1,sx2,sy2,pad);
                    ctx.save();
                    ctx.beginPath();ctx.moveTo(e0[0],e0[1]);ctx.lineTo(e1[0],e1[1]);ctx.lineTo(e2[0],e2[1]);ctx.closePath();ctx.clip();
                    ctx.transform(T.a,T.b,T.c,T.d,T.tx,T.ty);
                    ctx.drawImage(texImg,0,0);
                    ctx.restore();
                }
            }else if(att instanceof spine.RegionAttachment){const r=att.region;if(r){const off=att.offset||[0,0],b=slot.bone;ctx.save();ctx.transform(b.a,b.c,b.b,b.d,b.worldX,b.worldY);if(r.rotate){ctx.translate(off[0],off[1]);ctx.rotate(-Math.PI/2);ctx.drawImage(texImg,r.x,r.y,r.width,r.height,-r.height/2,-r.width/2,r.height,r.width);}else ctx.drawImage(texImg,r.x,r.y,r.width,r.height,off[0]-r.width/2,off[1]-r.height/2,r.width,r.height);ctx.restore();}}
            ctx.globalCompositeOperation='source-over';ctx.globalAlpha=1;
            if(clipEnd&&slot.data===clipEnd){ctx.restore();clipEnd=null;}
        }

        // Downsample 3x → 1x with lanczos via canvas drawImage
        ctxFinal.setTransform(1,0,0,1,0,0);
        ctxFinal.clearRect(0,0,finalW,finalH);
        ctxFinal.drawImage(canvas,0,0,outW,outH,0,0,finalW,finalH);
        writeFileSync(join(frameDir,`frame_${String(f).padStart(5,'0')}.png`),canvasFinal.toBuffer('image/png'));
    }

    // APNG for extra-large renders (>16383 WebP limit), WebP otherwise
    const useAPNG = finalW > 16383 || finalH > 16383;
    const ext = useAPNG ? 'apng' : 'webp';
    const outPath = join(OUTPUT_DIR, `${dirName}_v14.${ext}`);
    const ffTimeout = 1800000;  // 30 min for large canvases
    try {
        const codec = useAPNG ? 'apng -plays 0' : 'libwebp_anim -lossless 0 -q:v 90 -loop 0';
        execSync(`ffmpeg -y -framerate ${fps} -i "${frameDir}\\frame_%05d.png" -c:v ${codec} "${outPath}"`, { stdio: 'pipe', timeout: ffTimeout });
    } catch {
        execSync(`ffmpeg -y -framerate ${fps} -i "${frameDir}\\frame_%05d.png" -c:v libwebp_anim -lossless 0 -q:v ${WEBP_Q} -loop 0 "${outPath}"`, { stdio: 'pipe', timeout: ffTimeout });
    }
    rmSync(frameDir, { recursive: true, force: true });
    return{name:`${dirName}_v14`,frames:totalFrames,sizeKb:Math.round(statSync(outPath).size/1024)};
}

let dirs=readdirSync(SPINE_DIR,{withFileTypes:true}).filter(d=>d.isDirectory()).map(d=>d.name).sort();
if(TARGET)dirs=dirs.filter(d=>d.toLowerCase().includes(TARGET.toLowerCase()));
console.log(`Canvas2D v14 (raw unPMA + alpha cleanup + ${SUPERSAMPLE}x supersample + ${EXPAND_PX}px expand)`);
async function p(){for(const d of dirs){try{const r=await renderAnimation(d,FPS,SCALE,MAX_SEC);console.log(`${r?.name}: ${r?.frames}f ${r?.sizeKb}KB`);}catch(e){console.log(`FAIL ${d}: ${e.message}`);}}}
p().catch(e=>{console.error(e);process.exit(1)});
