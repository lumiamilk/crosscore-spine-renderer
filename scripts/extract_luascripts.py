"""Extract Lua scripts from the luascripts AssetBundle file"""
import os, sys, struct, json

path = r"D:\soft\to_run\ai\game_live2d\CrossCore\source\luascripts"

with open(path, 'rb') as f:
    data = f.read()

print(f"luascripts file size: {len(data)} bytes ({len(data)/1024/1024:.1f} MB)")

# Try to read as a Unity AssetBundle
# First, try to extract inner UnityFS bundle
positions = []
pos = 0
while True:
    pos = data.find(b'UnityFS', pos)
    if pos == -1:
        break
    positions.append(pos)
    pos += 1

print(f"Found {len(positions)} UnityFS markers")

if positions:
    # Use the last marker (assume it's the inner bundle)
    inner = data[positions[-1]:]
    print(f"Inner bundle size: {len(inner)} bytes")
    
    # Try loading with UnityPy
    import UnityPy
    try:
        env = UnityPy.load(inner)
        print(f"Loaded {len(env.objects)} objects from inner bundle")
        
        for obj in env.objects:
            t = obj.type.name
            try:
                d = obj.read()
                name = getattr(d, "m_Name", "?")
            except:
                name = "?"
            
            if t == "TextAsset":
                try:
                    script = getattr(d, "m_Script", b"")
                    if isinstance(script, str):
                        script_bytes = script.encode('utf-8', errors='replace')
                    else:
                        script_bytes = script
                    print(f"  TextAsset: {name} ({len(script_bytes)} bytes)")
                    
                    # Try to decode
                    if b"function" in script_bytes[:200] or b"--" in script_bytes[:200] or b"local" in script_bytes[:200]:
                        try:
                            text = script_bytes.decode('utf-8')
                            print(f"    First 500 chars: {text[:500]}")
                        except:
                            print(f"    Binary (not UTF-8 text), first 100 bytes hex: {script_bytes[:100].hex()}")
                    else:
                        print(f"    Binary, first 100 bytes hex: {script_bytes[:100].hex()}")
                except Exception as e:
                    print(f"  TextAsset: {name} (error: {e})")
            
            if t == "MonoBehaviour":
                try:
                    script_name = "?"
                    if hasattr(d, "m_Script") and d.m_Script:
                        s = d.m_Script.read()
                        script_name = getattr(s, "m_Name", "?")
                    print(f"  MonoBehaviour: {name} -> {script_name}")
                    # Look for string or bytes fields
                    for attr in dir(d):
                        if attr.startswith('_') or attr.startswith('m_ObjectHideFlags'):
                            continue
                        try:
                            val = getattr(d, attr)
                            if isinstance(val, bytes) and len(val) > 10:
                                print(f"    {attr}: bytes ({len(val)} bytes), first 100: {val[:100].hex()}")
                                if len(val) > 1000000:
                                    # Large binary blob - might be Lua bytecode
                                    print(f"    *** LARGE BINARY BLOB: {len(val)} bytes ***")
                            elif isinstance(val, str) and len(val) > 10:
                                print(f"    {attr}: str ({len(val)} chars): {val[:200]}")
                            elif isinstance(val, (list, tuple)) and len(val) > 0:
                                print(f"    {attr}: list of {len(val)} items")
                        except:
                            pass
                except Exception as e:
                    print(f"  MonoBehaviour: {name} (error: {e})")
    except Exception as e:
        print(f"UnityPy load error: {e}")

# Also try: maybe luascripts is just a raw .NET BinaryFormatter file
# Look for Lua patterns in the raw binary
print(f"\n--- Searching for Lua patterns in raw binary ---")
lua_patterns = [b'function ', b'local ', b'return ', b'-- ', b'end\n', b'ModelCtrl', b'xlua', b'CSpine', b'eye', b'mouth']
for pat in lua_patterns:
    idx = data.find(pat)
    if idx >= 0:
        try:
            context = data[max(0,idx-30):idx+200]
            print(f"  Found '{pat.decode('utf-8','replace')}' at offset {idx}")
            print(f"    Context: {context[:230]}")
            print(f"    Hex: {context[:50].hex()}")
        except:
            print(f"  Found b'{pat}' at offset {idx}")
