import json,hashlib,sys,shutil,argparse
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops,ImageFilter
work=Path(__file__).resolve().parent;folder=work.parent
s=json.loads((work/'STEP2_STATE.json').read_text(encoding='utf-8'))
assert s.get('blinkCompositingConsent',{}).get('approved') is True
parser=argparse.ArgumentParser();parser.add_argument('--tier',default='fanxing');parser.add_argument('--finalize',action='store_true');args=parser.parse_args()
tier=args.tier
if tier=='fanxing':plans=json.loads((work/'BLINK_REGIONS_PROPOSAL.json').read_text(encoding='utf-8'))
else:plans=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((work/'blinks').glob(tier+'__*.json'))]
plans=[r for r in plans if r.get('status','CANDIDATE')=='CANDIDATE']
rects={
'coquettish_blink.png':[[535,580,748,710],[805,635,965,752]],
'bored_blink.png':[[683,780,884,884],[946,748,1112,844]],
'cheer_blink.png':[[485,435,710,598],[752,534,927,665]],
'clap_blink.png':[[466,497,678,618],[738,535,927,650]],
'curious_blink.png':[[480,493,655,643],[731,646,907,775]],
'focus_done_blink.png':[[486,472,657,582],[708,519,884,636]],
'focus_read_blink.png':[[512,565,772,718],[772,631,956,747]],
'greet_morning_blink.png':[[720,525,916,663]],
'headpat_happy_blink.png':[[529,625,749,714],[804,654,940,740]],
'hold_card_blink.png':[[444,469,636,607],[713,516,884,648]],
'hug_blink.png':[[439,424,665,560],[715,482,899,610]],
'landing_blink.png':[[539,610,791,755],[819,648,997,759]],
'packing_blink.png':[[473,450,660,579],[717,548,917,641]],
'pout_blink.png':[[479,481,740,605],[739,510,932,635]],
'ready_go_blink.png':[[492,459,707,578],[747,533,942,659]],
'stretch_break_blink.png':[[595,350,795,510],[769,489,961,640]],
'thinking_blink.png':[[514,543,743,664],[782,608,940,713]],
'thumbs_up_blink.png':[[505,464,718,577],[768,531,930,653]],
'worried_blink.png':[[535,505,747,616],[765,551,904,643]]
}
polys={
'pout_blink.png': [[(475,445),(525,455),(700,510),(745,550),(735,606),(490,606)]],
'ready_go_blink.png': [[(492,455),(565,460),(660,489),(707,530),(692,580),(512,579)]],
'thumbs_up_blink.png': [[(500,450),(580,454),(710,500),(724,534),(710,577),(514,572)]]
}
exclude={'packing_blink.png':[[550,460,650,495]],'stretch_break_blink.png':[[690,320,790,392]]}
extras={'bored_blink.png':[[1058,713,1087,750]],'cheer_blink.png':[[842,503,888,531]]}
if tier=='mingyue':
 extras['landing_blink.png']=[[970,605,1020,670],[819,750,997,790]]
outdir=work/'composed';outdir.mkdir(exist_ok=True)
reports=[]
for r in plans:
 name=r['frame'];base=Image.open(r['target']).convert('RGBA');draft=Image.open(r['generated']).convert('RGBA')
 assert base.size==draft.size==(1254,1254)
 mask=Image.new('L',base.size,0);d=ImageDraw.Draw(mask)
 boxes=rects[name]
 for j,b in enumerate(boxes):
  if j==0 and name in polys:d.polygon(polys[name][0],fill=255)
  else:d.rectangle(tuple(b),fill=255)
 for b in extras.get(name,[]):d.rectangle(tuple(b),fill=255)
 hard=mask.filter(ImageFilter.MaxFilter(17))
 if name in exclude:
  dd=ImageDraw.Draw(hard)
  for b in exclude[name]:dd.rectangle(tuple(b),fill=0)
 blend=ImageChops.multiply(hard,hard.filter(ImageFilter.GaussianBlur(3)))
 result=Image.composite(draft.convert('RGB'),base.convert('RGB'),blend).convert('RGBA')
 result.putalpha(base.getchannel('A'))
 diff=ImageChops.difference(result.convert('RGB'),base.convert('RGB'))
 outside=ImageChops.multiply(diff,ImageChops.invert(hard).convert('RGB'))
 assert outside.getbbox() is None,name
 assert result.getchannel('A').tobytes()==base.getchannel('A').tobytes(),name
 dest=outdir/(tier+'__'+name);result.save(dest)
 maskpath=outdir/(tier+'__'+name+'.mask.png');hard.save(maskpath)
 reports.append({'tier':tier,'frame':name,'master':r['master'],'masterSha256':hashlib.sha256(Path(r['target']).read_bytes()).hexdigest(),'generatedDraft':r['generated'],'composed':str(dest),'mask':str(maskpath),'eyeRectangles':boxes,'eyePolygons':polys.get(name),'eyeBoundaryPatches':extras.get(name),'protectedEyebrows':exclude.get(name),'outsideEyeExact':True,'alphaExact':True,'prompt':r['prompt']})
qa='BLINK_COMPOSITE_QA.json' if tier=='fanxing' else tier.upper()+'_BLINK_COMPOSITE_QA.json'
(work/qa).write_text(json.dumps(reports,indent=2),encoding='utf-8')
if args.finalize:
 for r in reports:
  dest=folder/r['tier']/r['frame']
  assert r['frame'] in s['missingAtStart'][r['tier']],dest
  if dest.exists():
   assert hashlib.sha256(dest.read_bytes()).digest()==hashlib.sha256(Path(r['composed']).read_bytes()).digest(),('existing_composite_differs',dest)
   continue
  shutil.copyfile(r['composed'],dest)
  src=next(f for f in s['frames'] if f['name']==r['frame'])
  record={**r,'source':src['source'],'sourceSha256':src['sourceSha256'],'status':'CANDIDATE','method':'imagegen closed eyes plus explicitly authorized eye-only Pillow compositing'}
  (work/'jobs'/(tier+'__'+r['frame']+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({'tier':tier,'composed':len(reports),'outsideEyeExact':len(reports),'alphaExact':len(reports),'finalized':args.finalize}))
