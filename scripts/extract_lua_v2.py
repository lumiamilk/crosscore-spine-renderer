"""
Extract all Lua files from luascripts binary - robust version.
The format: each .lua file is stored as raw LuaJIT bytecode with source embedded.
We'll extract ALL files and write them as .lua for decompilation.
"""
import os, sys, struct

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH = r"D:\soft\to_run\ai\game_live2d\CrossCore\source\luascripts"
OUTDIR = r"D:\soft\to_run\ai\game_live2d\_extracted_lua"
OUTDIR_RAW = r"D:\soft\to_run\ai\game_live2d\_extracted_lua\_raw"

with open(PATH, 'rb') as f:
    data = f.read()

os.makedirs(OUTDIR, exist_ok=True)
os.makedirs(OUTDIR_RAW, exist_ok=True)

# Find all .lua positions
lua_ends = []
pos = 0
while True:
    pos = data.find(b'.lua', pos)
    if pos == -1:
        break
    lua_ends.append(pos + 4)  # end of .lua extension
    pos += 1

print(f"Found {len(lua_ends)} .lua markers")

# For each .lua, find the full filename and extract the content
extracted = 0

for i, lua_end in enumerate(lua_ends):
    # Find filename start (scan back for non-printable or control char)
    fname_start = lua_end - 4  # start of .lua
    while fname_start > 0:
        b = data[fname_start - 1]
        # Stop at null, non-printable bytes, or known separators
        if b == 0 or b == 0xFF or (b < 32 and b not in (0x2E,)):  # 0x2E = '.'
            break
        fname_start -= 1
    
    fname = data[fname_start:lua_end]
    
    try:
        fn = fname.decode('utf-8', errors='replace')
    except:
        fn = f"unknown_{i:04d}"
    
    # Skip files with empty or corrupted names
    fn_clean = fn.strip().replace('\x00', '').replace('\r', '').replace('\n', '')
    if len(fn_clean) < 3 or fn_clean == '.lua':
        continue
    
    if not fn_clean.endswith('.lua'):
        fn_clean = fn_clean.rsplit('.lua', 1)[0] + '.lua'
    
    # Find the BOM (ef bb bf) marking start of content
    # Content may start right after lua_end with some header bytes
    search_start = lua_end
    if i + 1 < len(lua_ends):
        search_end = min(lua_ends[i + 1] - 4, lua_end + 1000)
    else:
        search_end = min(len(data), lua_end + 1000)
    
    bom_pos = data.find(b'\xef\xbb\xbf', search_start, search_end)
    
    # Content region: from BOM+3 to next .lua's filename_start
    content_start = (bom_pos + 3) if bom_pos >= 0 else lua_end
    
    if i + 1 < len(lua_ends):
        # Next entry's filename start
        next_pos = lua_ends[i + 1] - 4
        while next_pos > 0 and 32 <= data[next_pos - 1] < 127:
            next_pos -= 1
        content_end = next_pos
    else:
        content_end = len(data)
    
    # Limit content size (max 5MB)
    content_end = min(content_end, content_start + 5000000)
    
    raw_content = data[content_start:content_end]
    
    if len(raw_content) < 10:
        continue
    
    # Save raw bytecode for future decompilation
    # Sanitize filename: remove all non-ASCII and special chars
    safe_fn = ''.join(c if c.isalnum() or c in '._-' else '_' for c in fn_clean)
    safe_fn = safe_fn.strip('_')
    if not safe_fn or len(safe_fn) < 3:
        safe_fn = f"lua_file_{i:04d}.lua"
    
    raw_path = os.path.join(OUTDIR_RAW, safe_fn + '.raw')
    with open(raw_path, 'wb') as f:
        f.write(raw_content)
    
    # Also try to make a "best effort" text extraction
    # The Lua source is embedded within the bytecode
    text_lines = []
    current_line = []
    in_string = False
    j = 0
    
    while j < len(raw_content):
        b = raw_content[j]
        
        if b == 0x0A or b == 0x0D:
            if current_line:
                line = ''.join(current_line)
                if len(line.strip()) > 0:
                    text_lines.append(line)
                current_line = []
            if b == 0x0D and j + 1 < len(raw_content) and raw_content[j + 1] == 0x0A:
                j += 1
        elif 32 <= b < 127:
            current_line.append(chr(b))
        elif b >= 0xC0:
            # UTF-8 multi-byte
            try:
                if b < 0xE0:
                    clen = 2
                elif b < 0xF0:
                    clen = 3
                else:
                    clen = 4
                if j + clen <= len(raw_content):
                    ch = raw_content[j:j+clen].decode('utf-8', errors='replace')
                    current_line.append(ch)
                    j += clen - 1
            except:
                pass
        elif b == 0x09:
            current_line.append('\t')
        elif b == 0x00:
            if current_line:
                current_line.append(' ')
        else:
            if current_line:
                current_line.append(' ')
        
        j += 1
    
    if current_line:
        line = ''.join(current_line)
        if len(line.strip()) > 0:
            text_lines.append(line)
    
    if text_lines:
        text_path = os.path.join(OUTDIR, safe_fn)
        with open(text_path, 'w', encoding='utf-8', errors='replace') as f:
            f.write('\n'.join(text_lines))
    
    extracted += 1

print(f"Extracted {extracted} Lua files")
print(f"Raw bytecode: {OUTDIR_RAW}")
print(f"Text (best-effort): {OUTDIR}")

# Now search all extracted text files for model/spine related content
print("\n=== Files with spine/skeleton/model keywords ===")
for fn in sorted(os.listdir(OUTDIR)):
    fl = fn.lower()
    if any(k in fl for k in ['model', 'spine', 'cspine', 'skin', 'character', '10010', 'ctrl', 'init', 'hide']):
        fpath = os.path.join(OUTDIR, fn)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        found = []
        search_patterns = [
            'SetAttachment', 'SetEmptySlot', 'skeleton', 'slot', 'eye', 'mouth',
            'redL', 'redR', 'face_sh', 'hideSlot', 'initialSkin', 'SetupPose',
            'AnimationState', 'drawOrder', 'SetSlotColor', 'CSpine', 'SkeletonGraphic',
            'ModelCtrl', 'modelCtrl'
        ]
        for pat in search_patterns:
            if pat.lower() in content.lower():
                found.append(pat)
        if found:
            print(f"  {fn}: {found}")
            # Print first 300 chars
            preview = content[:400].replace('\n', '\\n')
            print(f"    > {preview}")

# Also search content of ALL files for model-related terms
print("\n=== ALL files containing 'SetAttachment' or 'SetEmptySlot' ===")
for fn in sorted(os.listdir(OUTDIR)):
    fpath = os.path.join(OUTDIR, fn)
    with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    if 'SetAttachment' in content or 'SetEmptySlot' in content:
        print(f"  {fn}: {len(content)} chars")
        # Find the relevant section
        idx = content.find('SetAttachment')
        if idx < 0:
            idx = content.find('SetEmptySlot')
        start = max(0, idx - 200)
        end = min(len(content), idx + 200)
        print(f"    ...{content[start:end]}...")

print("\n=== Searching for 'eye' in file content ===")
for fn in sorted(os.listdir(OUTDIR)):
    fpath = os.path.join(OUTDIR, fn)
    with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    if 'eye' in content.lower():
        # Find context
        for term in ['eye', 'Eye']:
            idx = content.lower().find(term.lower())
            if idx >= 0:
                start = max(0, idx - 100)
                end = min(len(content), idx + 100)
                print(f"  {fn}: ...{content[start:end]}...")
                break
