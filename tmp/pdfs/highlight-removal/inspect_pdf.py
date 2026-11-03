import sys,json,collections
from pypdf import PdfReader
from pypdf.generic import ContentStream
r=PdfReader(sys.argv[1])
result=[]
for pn,p in enumerate(r.pages,1):
 c=ContentStream(p.get_contents(),r)
 colors=collections.Counter();yellow=[]
 for i,(args,op) in enumerate(c.operations):
  if op in (b"rg",b"RG",b"k",b"K",b"g",b"G"):
   key=(op.decode(),tuple(str(v) for v in args));colors[key]+=1
  if op==b"rg" and len(args)==3 and float(args[0])>.7 and float(args[1])>.6 and float(args[2])<.7:
   yellow.append({"index":i,"color":[float(v) for v in args],"next":[[str(v) for v in a]+[o.decode()] for a,o in c.operations[i+1:i+8]]})
 result.append({"page":pn,"colors":[[k[0],k[1],n] for k,n in colors.most_common()],"yellow":yellow[:3]})
print(json.dumps(result))
