import sys,json,collections
from pypdf import PdfReader
from pypdf.generic import ContentStream
r=PdfReader(sys.argv[1]); out=[]
for pn in [3,8,20,32,34]:
 c=ContentStream(r.pages[pn-1].get_contents(),r);hits=[]
 for i,(args,op) in enumerate(c.operations):
  if op==b"rg" and [round(float(v),6) for v in args]==[0.320312,0.777344,0.855469]:
   if len(hits)<4:hits.append({"i":i,"ops":[[str(v) for v in a]+[o.decode()] for a,o in c.operations[max(0,i-4):i+12]]})
 out.append({"page":pn,"hits":hits})
print(json.dumps(out))
