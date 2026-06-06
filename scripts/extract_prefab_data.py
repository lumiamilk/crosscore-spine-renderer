"""Extract AnimationClips, AnimatorControllers, and XLua data from character prefabs"""
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
        return None
    inner = data[positions[-1]:]
    return inner

import UnityPy

def inspect_character_prefab(path, label):
    inner = extract_inner_bundle(path)
    if not inner:
        print(f"ERROR: no inner bundle")
        return
    env = UnityPy.load(inner)
    
    print(f"\n{'='*70}")
    print(f"  Character Prefab: {label}")
    print(f"{'='*70}")
    
    # Find AnimatorController and dump state machine
    for obj in env.objects:
        if obj.type.name == "AnimatorController":
            data = obj.read()
            print(f"\n--- AnimatorController: {getattr(data, 'm_Name', '?')} ---")
            if hasattr(data, 'm_AnimatorParameters'):
                params = data.m_AnimatorParameters
                if params:
                    print(f"  Parameters: {len(params)}")
                    for p in params[:20]:
                        print(f"    {p.get('m_Name', '?')}: {p.get('m_Type', '?')}")
            
            if hasattr(data, 'm_Controller'):
                ctrl = data.m_Controller
                if hasattr(ctrl, 'm_Name'):
                    print(f"  Controller: {ctrl.m_Name}")
            
            # Try to get controller state machine
            if hasattr(data, 'controller') or hasattr(data, 'm_Controller'):
                try:
                    ctrl = getattr(data, 'controller', None) or getattr(data, 'm_Controller', None)
                    if ctrl and hasattr(ctrl, 'm_Name'):
                        print(f"  Controller: {ctrl.m_Name}")
                except:
                    pass
    
    # Find AnimationClips and dump basic info
    print(f"\n--- AnimationClips ---")
    for obj in env.objects:
        if obj.type.name == "AnimationClip":
            try:
                data = obj.read()
                name = getattr(data, 'm_Name', '?')
                duration = 0
                try:
                    duration = getattr(data, 'm_MuscleClip', None) or getattr(data, 'm_AnimationClipSettings', None)
                    if duration and hasattr(duration, 'm_StopTime'):
                        duration = duration.m_StopTime
                except:
                    pass
                print(f"  AnimationClip: {name} (duration: {duration})")
            except Exception as e:
                print(f"  AnimationClip: error reading ({e})")
    
    # Find XLuaMono and dump their data
    print(f"\n--- XLua MonoBehaviours ---")
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
        
        if script_name in ("XLuaMono", "XLuaAnimator", "XLuaParams", "XLuaParam_GO"):
            print(f"\n  [{script_name}] name='{getattr(data, 'm_Name', '?')}'")
            for attr_name in dir(data):
                if attr_name.startswith('_') or attr_name in ('assets_file', 'm_Enabled', 'm_Name', 'm_ObjectHideFlags'):
                    continue
                try:
                    val = getattr(data, attr_name)
                    if val is None or hasattr(val, '__call__') or hasattr(val, 'read'):
                        continue
                    if isinstance(val, (str, int, float, bool)):
                        print(f"    {attr_name}: {val}")
                    elif isinstance(val, (list, tuple)):
                        if len(val) < 50:
                            print(f"    {attr_name}: {val}")
                        else:
                            print(f"    {attr_name}: [list of {len(val)} items]")
                    else:
                        try:
                            s = str(val)
                            if len(s) > 300:
                                s = s[:300] + "..."
                            print(f"    {attr_name}: {s}")
                        except:
                            print(f"    {attr_name}: <{type(val).__name__}>")
                except:
                    pass
    
    # Find StateCustomBehaviour
    print(f"\n--- StateCustomBehaviour MonoBehaviours ---")
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
        
        if script_name in ("StateCustomBehaviour", "StateCustomBehaviourExtend"):
            print(f"\n  [{script_name}] name='{getattr(data, 'm_Name', '?')}'")
            for attr_name in dir(data):
                if attr_name.startswith('_') or attr_name in ('assets_file', 'm_Enabled', 'm_Name', 'm_ObjectHideFlags'):
                    continue
                try:
                    val = getattr(data, attr_name)
                    if val is None or hasattr(val, '__call__') or hasattr(val, 'read'):
                        continue
                    if isinstance(val, (str, int, float, bool)):
                        print(f"    {attr_name}: {val}")
                    elif isinstance(val, (list, tuple)):
                        if len(val) < 50:
                            print(f"    {attr_name}: {val}")
                        else:
                            print(f"    {attr_name}: [list of {len(val)} items]")
                    else:
                        try:
                            s = str(val)
                            if len(s) > 500:
                                s = s[:500] + "..."
                            print(f"    {attr_name}: {s}")
                        except:
                            print(f"    {attr_name}: <{type(val).__name__}>")
                except:
                    pass

# Inspect all three character prefabs
for path, label in [
    (r"D:\soft\to_run\ai\game_live2d\CrossCore\source\prefabs_characters_m1001003", "m1001003 (alps03)"),
    (r"D:\soft\to_run\ai\game_live2d\CrossCore\source\prefabs_characters_m1001004", "m1001004 (alps04)"),
    (r"D:\soft\to_run\ai\game_live2d\CrossCore\source\prefabs_characters_m1001005", "m1001005 (alps05)"),
]:
    inspect_character_prefab(path, label)
