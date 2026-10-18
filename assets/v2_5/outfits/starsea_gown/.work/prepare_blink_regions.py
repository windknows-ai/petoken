import json
from pathlib import Path
from PIL import Image,ImageChops,ImageFilter,ImageDraw
work=Path(__file__).resolve().parent
s=json.loads((work/'STEP2_STATE.json').read_text(encoding='utf-8'))
assert s.get('blinkCompositingConsent',{}).get('approved') is True
folder=work.parent; rows=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((work/'blinks').glob('*.json'))]
coq=json.loads((work/'BLINK_DRAFT.json').read_text(encoding='utf-8'));coq['target']=str(folder/'fanxing'/coq['master']);rows.insert(0,coq)
plans=[]
for r in rows:
 if not r.get('generated'):continue
 base=Image.open(r['target']).convert('RGBA');draft=Image.open(r['generated']).convert('RGBA')
 dif=ImageChops.difference(base.convert('RGB'),draft.convert('RGB'))
 chans=[c.point(lambda x:255 if x>55 else 0) for c in dif.split()]
 mask=ImageChops.lighter(ImageChops.lighter(chans[0],chans[1]),chans[2])
 opaque=ImageChops.darker(base.getchannel('A'),draft.getchannel('A')).point(lambda x:255 if x>250 else 0)
 mask=ImageChops.multiply(mask,opaque).filter(ImageFilter.MaxFilter(3))
 data=bytearray(mask.tobytes());w,h=mask.size;comps=[]
 for y in range(300,min(h,1150)):
  for x in range(250,min(w,1120)):
   start=y*w+x
   if data[start]==0:continue
   stack=[start];data[start]=0;area=0;x0=x;x1=x;y0=y;y1=y
   while stack:
    k=stack.pop();ky,kx=divmod(k,w);area+=1
    x0=min(x0,kx);x1=max(x1,kx);y0=min(y0,ky);y1=max(y1,ky)
    for z in (k-1,k+1,k-w,k+w):
     if 0<=z<len(data) and data[z]:
      data[z]=0;stack.append(z)
   bw=x1-x0+1;bh=y1-y0+1;density=area/(bw*bh)
   if area>=18 and 12<=bw<=260 and 5<=bh<=180 and density>.10:
    comps.append({'bbox':[x0,y0,x1+1,y1+1],'area':area,'density':round(density,3)})
 comps.sort(key=lambda c:c['area'],reverse=True)
 selected=sorted(comps[:2],key=lambda c:c['bbox'][0])
 plan={**r,'candidates':comps[:8],'selected':selected,'status':'MASK_REVIEW_REQUIRED'}
 plans.append(plan)
(work/'BLINK_REGIONS_PROPOSAL.json').write_text(json.dumps(plans,indent=2),encoding='utf-8')
out=Path(r'C:\Users\fengz\.codex\visualizations\2026\10\12\01a12eca-2b82-7dc1-8cbb-263b2d6b985b')
for page in range((len(plans)+5)//6):
 sheet=Image.new('RGB',(1200,1020),(36,44,64));d=ImageDraw.Draw(sheet)
 for i,r in enumerate(plans[page*6:(page+1)*6]):
  x=(i%2)*600;y=(i//2)*340;d.text((x+5,y+5),r['frame'],fill='white')
  boxes=[c['bbox'] for c in r['selected']]
  if not boxes:continue
  crop=(max(0,min(b[0] for b in boxes)-75),max(0,min(b[1] for b in boxes)-70),min(1254,max(b[2] for b in boxes)+75),min(1254,max(b[3] for b in boxes)+70))
  for j,p in enumerate([r['target'],r['generated']]):
   im=Image.open(p).convert('RGBA');dd=ImageDraw.Draw(im)
   for b in boxes:dd.rectangle(tuple(b),outline=(0,255,80,255),width=3)
   im=im.crop(crop);im.thumbnail((290,245),Image.Resampling.LANCZOS)
   sheet.paste(im,(x+5+j*300,y+35),im)
  d.text((x+5,y+290),str(boxes),fill='white')
 sheet.save(out/('starsea-blink-region-review-'+str(page+1)+'.png'))
print(json.dumps({r['frame']:[c['bbox'] for c in r['selected']] for r in plans}))
