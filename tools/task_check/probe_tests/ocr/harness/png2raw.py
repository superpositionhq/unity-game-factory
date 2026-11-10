import zlib, struct, sys
def read(path):
    d=open(path,'rb').read(); i=8; idat=b''
    while i<len(d):
        n=struct.unpack('>I',d[i:i+4])[0]; t=d[i+4:i+8]; c=d[i+8:i+8+n]; i+=12+n
        if t==b'IHDR': w,h,bd,ct=struct.unpack('>IIBB',c[:10])
        elif t==b'IDAT': idat+=c
    bpp={2:3,6:4}[ct]; raw=zlib.decompress(idat); out=bytearray(); prev=bytearray(w*bpp); p=0
    for y in range(h):
        f=raw[p]; p+=1; line=bytearray(raw[p:p+w*bpp]); p+=w*bpp
        for x in range(len(line)):
            a=line[x-bpp] if x>=bpp else 0; b=prev[x]; cc=prev[x-bpp] if x>=bpp else 0
            if f==1: line[x]=(line[x]+a)&255
            elif f==2: line[x]=(line[x]+b)&255
            elif f==3: line[x]=(line[x]+(a+b)//2)&255
            elif f==4:
                pa=abs(b-cc); pb=abs(a-cc); pc=abs(a+b-2*cc)
                pr=a if pa<=pb and pa<=pc else (b if pb<=pc else cc); line[x]=(line[x]+pr)&255
        prev=line
        for x in range(w): out+=line[x*bpp:x*bpp+3]
    return w,h,out
w,h,o=read(sys.argv[1]); open(sys.argv[2],'wb').write(struct.pack('<II',w,h)+o)
