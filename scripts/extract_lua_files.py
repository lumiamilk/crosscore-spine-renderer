"""
Extract all .lua files from luascripts binary by pattern matching.
Key finding: the format is NOT standard BinaryFormatter - the Lua data is stored
as raw source code chunks with bytecode interleaving, following this pattern:
  [size][filename.lua][BOM][content...]
  
We extract the content between consecutive .lua entries.
"""
import os

PATH = r"D:\soft\to_run\ai\game_live2d\CrossCore\source\luascripts"
OUTDIR = r"D:\soft\to_run\ai\game_live2d\_extracted_lua"

with open(PATH, 'rb') as f:
    data = f.read()

# Strategy: Find all .lua positions, then extract content between them
# Each entry: [prefix header][filename.lua][more header][BOM][Lua content...]

# Find all positions of .lua in the file
lua_positions = []
pos = 0
while True:
    pos = data.find(b'.lua', pos)
    if pos == -1:
        break
    lua_positions.append(pos)
    pos += 1

print(f"Found {len(lua_positions)} .lua markers")

# For each .lua position, find the filename and extract content
os.makedirs(OUTDIR, exist_ok=True)

# First pass: find filename boundaries
entries = []
for lua_pos in lua_positions:
    # Find filename start (scan back)
    fname_start = lua_pos
    while fname_start > 0:
        b = data[fname_start - 1]
        if not (32 <= b < 127) or b in (0, 10, 13):
            break
        fname_start -= 1
    
    fname_end = lua_pos + 4
    fname = data[fname_start:fname_end]
    
    # Find the BOM after the filename + header
    # The BOM is EF BB BF, followed by Lua source
    bom_pos = data.find(b'\xef\xbb\xbf', fname_end)
    if bom_pos == -1:
        # Try searching within 200 bytes
        bom_pos = data.find(b'\xef\xbb\xbf', fname_end, fname_end + 500)
    
    entries.append({
        'fname': fname,
        'fname_start': fname_start,
        'fname_end': fname_end,
        'bom_pos': bom_pos if bom_pos >= 0 else fname_end,
        'lua_pos': lua_pos,
    })

print(f"Entries with BOM: {sum(1 for e in entries if e['bom_pos'] >= 0)}/{len(entries)}")

# Extract content for each entry
extracted = 0
for i, entry in enumerate(entries):
    try:
        fn = entry['fname'].decode('utf-8', errors='replace')
    except:
        continue
    
    if not fn or fn == '.lua':
        continue
    
    # Content starts after the BOM (or after filename if no BOM)
    content_start = entry['bom_pos'] + 3 if entry['bom_pos'] >= 0 else entry['fname_end']
    
    # Content ends at the next .lua filename or a reasonable boundary
    if i + 1 < len(entries):
        content_end = entries[i + 1]['fname_start']
    else:
        content_end = min(len(data), content_start + 500000)
    
    # Limit to reasonable size (max 2MB per file)
    content_end = min(content_end, content_start + 2000000)
    
    raw_content = data[content_start:content_end]
    
    # Try to extract readable text from the bytecode
    # The content is LuaJIT bytecode with embedded source
    # Extract ASCII and UTF-8 readable parts
    def extract_readable(byte_data, max_len=50000):
        """Extract readable text from bytecode, preserving structure"""
        result = []
        i = 0
        while i < len(byte_data) and len(result) < max_len:
            b = byte_data[i]
            if 32 <= b < 127:
                # ASCII printable - collect a run
                run = []
                while i < len(byte_data) and 32 <= byte_data[i] < 127:
                    run.append(chr(byte_data[i]))
                    i += 1
                text = ''.join(run)
                if len(text) > 1:
                    result.append(text)
            elif b >= 0xC0:
                # UTF-8 multi-byte
                try:
                    # Determine length
                    if b < 0xE0:
                        clen = 2
                    elif b < 0xF0:
                        clen = 3
                    else:
                        clen = 4
                    if i + clen <= len(byte_data):
                        ch = byte_data[i:i+clen].decode('utf-8')
                        result.append(ch)
                        i += clen
                        continue
                except:
                    pass
                i += 1
            elif b == 0x0A:
                result.append('\n')
                i += 1
            elif b == 0x0D:
                result.append('\n')
                i += 1
            elif b == 0x09:
                result.append('\t')
                i += 1
            elif b == 0x00:
                result.append(' ')
                i += 1
            else:
                # Binary byte - skip
                i += 1
        
        return ''.join(result)
    
    readable = extract_readable(raw_content)
    
    if len(readable) < 20:
        continue
    
    # Clean filename
    safe_fn = fn.replace('/', '_').replace('\\', '_').replace(':', '_')
    if not safe_fn.endswith('.lua'):
        safe_fn += '.lua'
    
    outpath = os.path.join(OUTDIR, safe_fn)
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(readable)
    
    extracted += 1
    if extracted <= 30:
        print(f"  [{extracted}] {safe_fn}: {len(readable)} chars")
        # Print first few lines
        lines = readable.split('\n')
        preview_lines = [l for l in lines[:5] if l.strip()]
        if preview_lines:
            print(f"      {preview_lines[0][:100]}")

print(f"\nExtracted {extracted} Lua files to {OUTDIR}")

# Search for model-related files
print("\n=== Searching for model/spine related files ===")
for fn in os.listdir(OUTDIR):
    if any(k in fn.lower() for k in ['model', 'spine', 'cspine', 'skin', 'character', 'mouth', 'eye', 'slot', 'hide']):
        fpath = os.path.join(OUTDIR, fn)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Search for relevant patterns
        found = []
        for pat in ['SetAttachment', 'SetEmptySlot', 'skeleton', 'slot', 'eye', 'mouth', 'redL', 'redR', 'face_sh', 'hideSlot', 'initialSkin', 'SetupPose', 'AnimationState']:
            if pat.lower() in content.lower():
                found.append(pat)
        if found:
            print(f"\n  {fn} ({len(content)} chars)")
            print(f"    Contains: {', '.join(found)}")
            print(f"    Preview: {content[:300]}")
