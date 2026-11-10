import zlib, struct, sys
def load(p):
    d = open(p, "rb").read(); i = 8; idat = b""
    while i < len(d):
        n, t = struct.unpack(">I4s", d[i:i+8]); c = d[i+8:i+8+n]
        if t == b"IHDR": w, h, bd, ct = struct.unpack(">IIBB", c[:10])
        if t == b"IDAT": idat += c
        i += 12 + n
    bpp = {2: 3, 6: 4}[ct]; raw = zlib.decompress(idat); s = w * bpp; out = []; prev = bytearray(s)
    for y in range(h):
        f = raw[y*(s+1)]; line = bytearray(raw[y*(s+1)+1:(y+1)*(s+1)])
        for x in range(s):
            a = line[x-bpp] if x >= bpp else 0; b = prev[x]; c = prev[x-bpp] if x >= bpp else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2*c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out.append(line); prev = line
    return w, h, bpp, out
w, h, bpp, A = load(sys.argv[1]); _, _, _, B = load(sys.argv[2])
xs, ys, n, mx = [], [], 0, 0
for y in range(h):
    for x in range(w):
        dd = max(abs(A[y][x*bpp+k] - B[y][x*bpp+k]) for k in range(3))
        if dd: n += 1; xs.append(x); ys.append(y); mx = max(mx, dd)
print("pixels differing", n, "max", mx, "bbox", (min(xs), min(ys), max(xs), max(ys)) if n else None)
