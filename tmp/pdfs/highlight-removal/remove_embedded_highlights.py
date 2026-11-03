import sys,json,hashlib
from pathlib import Path
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ContentStream
source,output,report=sys.argv[1:]
source_hash=hashlib.sha256(Path(source).read_bytes()).hexdigest()
r=PdfReader(source);w=PdfWriter();w.clone_document_from_reader(r)
target=(0.3203125,0.77734375,0.85546875)
expected=[b'q',b'gs',b'rg',b'w',b'd',b'cm',b'cm',b'cm',b'm',b'l',b'l',b'l',b'h',b'f',b'Q']
changes=[]
for pn,page in enumerate(w.pages,1):
 c=ContentStream(page.get_contents(),w);removals=set();rects=[]
 for i,(args,op) in enumerate(c.operations):
  if op!=b'rg' or len(args)!=3 or any(abs(float(x)-v)>1e-8 for x,v in zip(args,target)):continue
  start,end=i-2,i+13
  block=c.operations[start:end]
  if [o for _,o in block]!=expected:raise RuntimeError(f'Unexpected highlight structure on page {pn}, op {i}')
  coords=[tuple(float(v) for v in block[j][0]) for j in [8,9,10,11]]
  if not(0<coords[1][1]<=30 and coords[2][0]>0):raise RuntimeError(f'Unexpected rectangle on page {pn}: {coords}')
  removals.update(range(start,end));rects.append({'transform':[float(v) for v in block[5][0]],'width':coords[2][0],'height':coords[1][1]})
 if removals:
  c.operations=[entry for i,entry in enumerate(c.operations) if i not in removals]
  page.replace_contents(c)
  changes.append({'page':pn,'removed_rectangles':len(rects),'rectangles':rects})
with open(output,'wb') as f:w.write(f)
check=PdfReader(output)
assert len(check.pages)==len(r.pages)
for pn,(a,b) in enumerate(zip(r.pages,check.pages),1):
 assert a.extract_text()==b.extract_text(),f'Text changed on page {pn}'
 assert list(a.mediabox)==list(b.mediabox),f'Page size changed on page {pn}'
 assert len(a.get('/Annots',[]))==len(b.get('/Annots',[])),f'Annotations changed on page {pn}'
 for args,op in ContentStream(b.get_contents(),check).operations:
  assert not(op==b'rg' and len(args)==3 and all(abs(float(x)-v)<1e-8 for x,v in zip(args,target))),f'Highlight remains on page {pn}'
assert hashlib.sha256(Path(source).read_bytes()).hexdigest()==source_hash
summary={'pages':len(check.pages),'highlight_rectangles_removed':sum(x['removed_rectangles'] for x in changes),'changed_pages':len(changes),'all_text_identical':True,'page_sizes_identical':True,'annotation_counts_identical':True,'original_unchanged':True,'changes':changes}
Path(report).write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='changes'}))
