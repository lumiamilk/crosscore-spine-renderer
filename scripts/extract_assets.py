"""
CrossCore AssetBundle 批量解包脚本 v3 - 多进程并行版
用法:
  python extract_assets.py                  # 自动检测核心数
  python extract_assets.py --workers 8      # 指定 8 个并行进程
  python extract_assets.py --skip-existing  # 断点续传
"""
import os, sys, json, time, struct, re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager, cpu_count, Lock
import traceback

import UnityPy
from UnityPy.enums import ClassIDType

BASE_DIR      = Path(r"D:\soft\to_run\ai\game_live2d")
CUSTOM_DIR    = BASE_DIR / "CrossCore" / "source"
OUTPUT_DIR    = BASE_DIR / "CrossCore" / "output"
LOG_FILE      = BASE_DIR / "CrossCore" / "extract_assets.log"
PROGRESS_FILE = BASE_DIR / "CrossCore" / "extract_progress.json"

_OUTPUT_SUBDIRS = {
    'character_tex':    "characters",
    'character_prefab': "characters",
    'spine':            "characters",
    'ui_rolehead':      "ui_icons/role_head",
    'ui_icon':          "ui_icons/icons",
    'effect':           "effects",
    'scene':            "scenes",
    'dormitory':        "prefabs/dormitory",
    'texture_other':    "other/textures",
    'font':             "other/fonts",
    'hash_bundle':      "other/hash_bundles",
    'other':            "other/other",
}

def sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip().rstrip('.')

def extract_inner_bundle(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    positions = []
    pos = 0
    while True:
        pos = data.find(b'UnityFS', pos)
        if pos == -1:
            break
        positions.append(pos)
        pos += 1
    if len(positions) < 1:
        return None, "no UnityFS signature"
    inner = data[positions[-1]:]
    if len(inner) < 64:
        return None, f"too small ({len(inner)} bytes)"
    return inner, None

def classify_bundle(filename):
    name = filename.lower()
    if re.match(r'^-\d+$', name):
        return 'hash_bundle', None, None
    if 'textures_bigs_character_' in name:
        m = re.search(r'character_(\d+)_(.+?)(?:_draw)', name)
        if m:
            return 'character_tex', m.group(1), m.group(2)
        m = re.search(r'character_(\d+)_(.+)', name)
        if m:
            return 'character_tex', m.group(1), m.group(2)
    if 'rolehead' in name:
        return 'ui_rolehead', None, None
    if 'textures_uis_icons' in name:
        return 'ui_icon', None, None
    if 'prefabs_spine_' in name:
        m = re.search(r'spine_(\d+)_(.+?)(?:_spine|$)', name)
        if m:
            return 'spine', m.group(1), m.group(2)
        return 'spine', None, None
    if 'prefabs_characters_g' in name:
        m = re.search(r'characters_g(\d+)', name)
        if m:
            return 'character_prefab', m.group(1), None
        return 'character_prefab', None, None
    if 'prefabs_effects_' in name:
        return 'effect', None, None
    if 'prefabs_scenes_' in name:
        return 'scene', None, None
    if 'dormitory' in name:
        return 'dormitory', None, None
    if 'textures_' in name:
        return 'texture_other', None, None
    if 'font_' in name:
        return 'font', None, None
    return 'other', None, None

def make_output_dir(category, char_id, variant, bundle_name, output_root):
    name = sanitize(bundle_name)
    base = output_root / _OUTPUT_SUBDIRS.get(category, "other/other")

    if category == 'character_tex':
        if char_id and variant:
            return base / char_id / "art" / sanitize(variant)
        elif char_id:
            return base / char_id / "art"
        else:
            return base / "_unknown" / name
    elif category == 'character_prefab':
        if char_id:
            return base / char_id / "prefab"
        else:
            return base / "_unknown" / name
    elif category == 'spine':
        if char_id and variant:
            return base / char_id / "spine" / sanitize(variant)
        elif char_id:
            return base / char_id / "spine"
        else:
            return base / "_unknown" / name
    else:
        return base / name

def process_bundle(filepath, output_root, shared_counters):
    """
    处理单个 AssetBundle，返回 (filename, stats_dict, errors_list).
    shared_counters 用于全局纹理去重 (跨进程)
    """
    filename = os.path.basename(filepath)
    stats = {'processed': 1, 'with_exports': 0, 'textures': 0, 'text_assets': 0, 'skipped': 0}
    errors = []

    inner_data, error = extract_inner_bundle(filepath)
    if error:
        errors.append((filename, error))
        return filename, stats, errors

    try:
        env = UnityPy.load(inner_data)
    except Exception as e:
        errors.append((filename, f"load: {e}"))
        return filename, stats, errors

    category, char_id, variant = classify_bundle(filename)
    out_dir = make_output_dir(category, char_id, variant, filename, output_root)

    # 确保目录存在
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    tex_count = 0
    for obj in env.objects:
        if obj.type == ClassIDType.Texture2D:
            try:
                data = obj.read()
                tex_name = getattr(data, 'name', '')
                if not tex_name:
                    tex_name = "texture"

                base = sanitize(tex_name)
                if not base:
                    base = "texture"

                # 全局去重计数器 (进程安全的 dict)
                key = str(out_dir)
                if key not in shared_counters:
                    shared_counters[key] = {}
                local = shared_counters[key]
                if base in local:
                    local[base] += 1
                    safe_name = f"{base}_{local[base]}.png"
                else:
                    local[base] = 0
                    safe_name = f"{base}.png"

                if len(safe_name) > 120:
                    safe_name = f"tex_{abs(obj.path_id)}.png"

                out_path = out_dir / safe_name
                out_path.parent.mkdir(parents=True, exist_ok=True)

                img = data.image
                img.save(str(out_path), 'PNG')
                tex_count += 1
            except Exception as e:
                pass  # silently skip individual texture errors in parallel mode

        elif obj.type == ClassIDType.TextAsset:
            try:
                data = obj.read()
                script_data = bytes(data.script) if hasattr(data, 'script') else b''
                if len(script_data) > 0:
                    asset_name = getattr(data, 'name', f'text_{obj.path_id}')
                    safe_name = sanitize(asset_name)
                    out_path = out_dir / safe_name
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(out_path, 'wb') as f:
                        f.write(script_data)
                    stats['text_assets'] += 1
            except Exception:
                pass

    stats['textures'] = tex_count
    stats['with_exports'] = 1 if tex_count > 0 or stats['text_assets'] > 0 else 0
    return filename, stats, errors

def main():
    start_time = time.time()

    # 参数
    workers = cpu_count()
    skip_existing = False
    for i, arg in enumerate(sys.argv):
        if arg == '--workers' and i + 1 < len(sys.argv):
            workers = int(sys.argv[i + 1])
        if arg == '--skip-existing':
            skip_existing = True
        if arg == '--source' and i + 1 < len(sys.argv):
            global CUSTOM_DIR
            CUSTOM_DIR = Path(sys.argv[i + 1])
        if arg == '--output' and i + 1 < len(sys.argv):
            global OUTPUT_DIR
            OUTPUT_DIR = Path(sys.argv[i + 1])

    # 初始化
    CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] CrossCore Extractor v3 (parallel)")
    print(f"  Source:  {CUSTOM_DIR}")
    print(f"  Output:  {OUTPUT_DIR}")
    print(f"  Workers: {workers}")
    print()

    if not CUSTOM_DIR.exists() or not any(CUSTOM_DIR.iterdir()):
        print("ERROR: Custom/ 为空！请先拉取文件。")
        sys.exit(1)

    # 断点续传
    processed_set = set()
    if PROGRESS_FILE.exists() and skip_existing:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            processed_set = set(data.get('processed', []))
        print(f"Resuming: {len(processed_set)} already processed")

    all_files = sorted([f for f in CUSTOM_DIR.glob("*") if f.is_file()], key=lambda f: f.name)
    pending = [str(f) for f in all_files if f.name not in processed_set]
    total = len(all_files)
    remaining = len(pending)

    print(f"Total: {total}, Pending: {remaining}")
    print()

    if remaining == 0:
        print("All files already processed.")
        sys.exit(0)

    # 共享状态
    manager = Manager()
    shared_counters = manager.dict()

    # 汇总统计
    agg_stats = {'processed': 0, 'with_exports': 0, 'textures': 0, 'text_assets': 0, 'skipped': len(processed_set), 'errors': []}

    # ---- 并行处理 ----
    chunk_size = max(1, remaining // (workers * 4))
    last_report = time.time()
    report_interval = 3  # seconds

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for filepath in pending:
            f = executor.submit(process_bundle, filepath, OUTPUT_DIR, shared_counters)
            futures[f] = filepath

        completed = 0
        for future in as_completed(futures):
            completed += 1
            try:
                fname, stats, errors = future.result()
                agg_stats['processed'] += stats['processed']
                agg_stats['with_exports'] += stats['with_exports']
                agg_stats['textures'] += stats['textures']
                agg_stats['text_assets'] += stats['text_assets']
                agg_stats['errors'].extend(errors)
                processed_set.add(fname)
            except Exception as e:
                agg_stats['errors'].append((futures[future], f"worker crash: {e}"))

            # 定期报告
            now = time.time()
            if now - last_report >= report_interval or completed == remaining:
                elapsed = now - start_time
                done_total = agg_stats['processed'] + agg_stats['skipped']
                rate = done_total / elapsed if elapsed > 0 else 0
                eta = (total - done_total) / rate if rate > 0 else 0
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] "
                      f"[{done_total}/{total}] {done_total*100//total}% | "
                      f"tex={agg_stats['textures']} txt={agg_stats['text_assets']} "
                      f"err={len(agg_stats['errors'])} | "
                      f"{rate:.0f} files/s | ETA {int(eta)}s",
                      end='', flush=True)
                last_report = now

            # 定期保存进度
            if completed % 1000 == 0:
                with open(PROGRESS_FILE, 'w', encoding='utf-8') as pf:
                    json.dump({'processed': list(processed_set), 'timestamp': datetime.now().isoformat()}, pf)

    print()  # newline after progress

    # 保存最终进度
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as pf:
        json.dump({'processed': list(processed_set), 'timestamp': datetime.now().isoformat()}, pf)

    elapsed = time.time() - start_time
    print()
    print("=" * 60)
    print(" Extraction Complete")
    print("=" * 60)
    print(f" Total files:      {total}")
    print(f" Processed:        {agg_stats['processed']}")
    print(f" Skipped:          {agg_stats['skipped']}")
    print(f" Files w/ exports: {agg_stats['with_exports']}")
    print(f" Textures:         {agg_stats['textures']} (unique files)")
    print(f" TextAssets:       {agg_stats['text_assets']}")
    print(f" Errors:           {len(agg_stats['errors'])}")
    print(f" Workers:          {workers}")
    print(f" Time:             {elapsed/60:.1f} min")
    print(f" Speed:            {agg_stats['processed']/elapsed:.0f} files/s")
    print(f" Output:           {OUTPUT_DIR}")

    if agg_stats['errors']:
        print()
        print("--- Errors ---")
        for fname, err in agg_stats['errors'][:30]:
            print(f"  {fname}: {err}")
        if len(agg_stats['errors']) > 30:
            print(f"  ... and {len(agg_stats['errors']) - 30} more")

    # 输出目录概要
    print()
    print("--- Output summary ---")
    dir_counts = {}
    for subdir in sorted(OUTPUT_DIR.glob("**/"), key=str):
        cnt = len([f for f in subdir.iterdir() if f.is_file()])
        if cnt > 0:
            rel = subdir.relative_to(OUTPUT_DIR)
            dir_counts[str(rel)] = cnt
    for d, c in sorted(dir_counts.items(), key=lambda x: -x[1])[:30]:
        print(f"  {d}/ ({c} files)")

    print(f"\nDone at {datetime.now()}")

if __name__ == '__main__':
    __spec__ = None  # for multiprocessing freeze support
    main()
