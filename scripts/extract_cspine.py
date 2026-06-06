"""Extract CSpine MonoBehaviour data and Lua scripts from prefabs"""
import os, json, struct, sys

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
    if not positions:
        return None, "no UnityFS signature"
    inner = data[positions[-1]:]
    return inner, None

import UnityPy

def dump_mono_behaviour(env, script_name_filter=None):
    """Dump detailed serialized data for MonoBehaviours matching a script name"""
    results = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            data = obj.read()
        except:
            continue
        
        script_name = "?"
        try:
            if hasattr(data, "m_Script") and data.m_Script:
                s = data.m_Script.read()
                script_name = getattr(s, "m_Name", "?")
        except:
            pass
        
        if script_name_filter and script_name_filter not in script_name:
            continue
        
        # Try to get serialized data
        result = {
            "path_id": obj.path_id,
            "name": getattr(data, "m_Name", "?"),
            "script": script_name,
        }
        
        # Dump all attributes
        attrs = {}
        for attr_name in dir(data):
            if attr_name.startswith('_') or attr_name.startswith('m_ObjectHideFlags'):
                continue
            try:
                val = getattr(data, attr_name)
                if val is None:
                    continue
                if hasattr(val, '__call__'):
                    continue
                if hasattr(val, 'read'):
                    continue
                # Try to convert to readable form
                if isinstance(val, (str, int, float, bool)):
                    attrs[attr_name] = val
                elif isinstance(val, (list, tuple)):
                    if len(val) < 20:
                        attrs[attr_name] = list(val)
                    else:
                        attrs[attr_name] = f"[list of {len(val)} items]"
                elif hasattr(val, 'm_Name'):
                    attrs[attr_name] = f"<{type(val).__name__}: {val.m_Name}>"
                else:
                    try:
                        attrs[attr_name] = str(val)[:200]
                    except:
                        attrs[attr_name] = f"<{type(val).__name__}>"
            except:
                pass
        
        result["attrs"] = attrs
        results.append(result)
    
    return results

def dump_all_mono(env, label):
    """Dump all MonoBehaviours with full attributes"""
    results = dump_mono_behaviour(env)
    for r in results:
        print(f"\n  [{r['path_id']}] {r['name']} ({r['script']})")
        for k, v in r['attrs'].items():
            if k in ('name', 'script', 'path_id'):
                continue
            print(f"    {k}: {v}")

# Inspect CSpine from each spine prefab
for name, path in [
    ("alps03_spine", r"D:\soft\to_run\ai\game_live2d\CrossCore\source\prefabs_spine_10010_skin_alps03_spine"),
    ("alps04_spine", r"D:\soft\to_run\ai\game_live2d\CrossCore\source\prefabs_spine_10010_skin_alps04_spine"),
    ("alps05_spine", r"D:\soft\to_run\ai\game_live2d\CrossCore\source\prefabs_spine_10010_skin_alps05_spine"),
]:
    print(f"\n{'='*70}")
    print(f"  CSpine from: {name}")
    print(f"{'='*70}")
    inner, err = extract_inner_bundle(path)
    if err:
        print(f"  ERROR: {err}")
        continue
    env = UnityPy.load(inner)
    cs_results = dump_mono_behaviour(env, "CSpine")
    for r in cs_results:
        print(f"\n  CSpine [{r['path_id']}] name='{r['name']}'")
        for k, v in r['attrs'].items():
            print(f"    {k}: {v}")
    
    # Also get SkeletonGraphic
    sg_results = dump_mono_behaviour(env, "SkeletonGraphic")
    for r in sg_results:
        print(f"\n  SkeletonGraphic [{r['path_id']}] name='{r['name']}'")
        for k, v in r['attrs'].items():
            print(f"    {k}: {v}")
    
    # Also get SkeletonDataAsset
    sd_results = dump_mono_behaviour(env, "SkeletonDataAsset")
    for r in sd_results:
        print(f"\n  SkeletonDataAsset [{r['path_id']}] name='{r['name']}'")
        for k, v in r['attrs'].items():
            print(f"    {k}: {v}")
