"""
多进程提取 Spine 完整数据: .atlas + .json + .png
"""
import UnityPy, os, json, re, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count

BASE = Path(r"D:\soft\to_run\ai\game_live2d")
CUSTOM = BASE / "CrossCore" / "source"
OUTPUT = BASE / "CrossCore" / "source"

def process_spine_bundle(filepath):
    fname = filepath.name
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        positions = [j for j in range(len(data) - 6) if data[j:j + 7] == b"UnityFS"]
        if len(positions) < 2:
            return (fname, "no_inner", None)

        inner = data[positions[-1]:]
        env = UnityPy.load(inner)

        atlas_data = None
        atlas_name = None
        json_data = None
        json_name = None
        tex_obj = None

        for obj in env.objects:
            if obj.type.name == "TextAsset":
                d = obj.read()
                name = getattr(d, "m_Name", "")
                script = getattr(d, "m_Script", b"")
                if isinstance(script, str):
                    script = script.encode("utf-8")

                if name.endswith(".atlas") or "atlas" in name.lower():
                    atlas_data = script
                    atlas_name = name
                elif len(script) > 10 and script[:1] == b"{":
                    json_data = script
                    json_name = name
            elif obj.type.name == "Texture2D":
                if tex_obj is None:
                    tex_obj = obj

        if not atlas_data and not json_data:
            return (fname, "no_textasset", None)

        m = re.search(r"spine_(\d+)_(.+?)(?:_spine|$)", fname)
        if m:
            role_id = m.group(1)
            variant = m.group(2)
        else:
            role_id = fname.replace("prefabs_spine_", "").replace("_spine", "")
            variant = "default"

        out_dir = OUTPUT / f"{role_id}_{variant}"
        out_dir.mkdir(parents=True, exist_ok=True)

        if atlas_data:
            atlas_path = out_dir / "skeleton.atlas"
            atlas_text = atlas_data.decode("utf-8", errors="replace")
            lines = atlas_text.split("\n")
            if lines and lines[0].rstrip().endswith(".png"):
                lines[0] = "skeleton.png"
            atlas_path.write_text("\n".join(lines), encoding="utf-8")

        if json_data:
            json_path = out_dir / "skeleton.json"
            try:
                json_text = json_data.decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(json_text)
                    json_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
                except:
                    json_path.write_text(json_text, encoding="utf-8")
            except:
                json_path.write_bytes(json_data)

        if tex_obj:
            try:
                img = tex_obj.read()
                tex_path = out_dir / "skeleton.png"
                img.image.save(str(tex_path), "PNG")
            except:
                pass

        return (fname, "ok", f"{role_id}_{variant}")

    except Exception as e:
        return (fname, f"error:{e}", None)

def main():
    workers = cpu_count()
    if "--workers" in sys.argv:
        idx = sys.argv.index("--workers")
        workers = int(sys.argv[idx + 1])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    all_files = sorted(
        [f for f in CUSTOM.glob("*") if f.is_file() and "spine" in f.name.lower()],
        key=lambda f: f.name
    )
    print(f"Spine bundles: {len(all_files)}, workers: {workers}")
    print(f"Output: {OUTPUT}\n")

    stats = {"ok": 0, "no_inner": 0, "no_textasset": 0, "error": 0}
    done = 0

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(process_spine_bundle, f): f for f in all_files}
        for future in futures:
            done += 1
            fname, status, info = future.result()
            if status == "ok":
                stats["ok"] += 1
            elif status == "no_textasset":
                stats["no_textasset"] += 1
            else:
                stats[status] = stats.get(status, 0) + 1

            if done % 50 == 0 or done == len(all_files):
                print(f"\r[{done}/{len(all_files)}] ok={stats['ok']} no_data={stats['no_textasset']} err={stats['error']}", end="", flush=True)

    print()
    print(f"\nDone: {stats['ok']} extracted, {stats['no_textasset']} without data, {stats['error']} errors")
    print(f"Output: {OUTPUT}")

if __name__ == "__main__":
    main()
