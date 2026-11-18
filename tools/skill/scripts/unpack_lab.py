import struct, sys, os, zlib

src, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
data = open(src, "rb").read()
off = 0
entries = []
while off + 616 <= len(data):
    name_raw = data[off:off+200]
    path_raw = data[off+200:off+600]
    a, b, c, hdr = struct.unpack_from("<IIII", data, off+600)
    n2 = name_raw.decode("utf-16-le", errors="replace").split("\x00")[0]
    p2 = path_raw.decode("utf-16-le", errors="replace").split("\x00")[0]
    if not n2:
        break
    stored = a if c == 0 else b
    payload = data[off+616:off+616+stored]
    if c == 2:
        payload = zlib.decompressobj(-15).decompress(payload)
    entries.append((n2, p2, a, b, c, off))
    rel = (p2 + n2).replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    dest = os.path.join(out_dir, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(payload)
    off += 616 + stored
for e in entries:
    print(f"{e[1]}{e[0]}  orig={e[2]} stored={e[3]} method={e[4]}")
print(f"total={len(entries)} parsed={off} file={len(data)} match={off==len(data)}")