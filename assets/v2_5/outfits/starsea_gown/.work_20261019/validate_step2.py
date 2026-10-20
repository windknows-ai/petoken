import hashlib,json,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops,ImageFilter
from PySide6.QtGui import QImage

work=Path(__file__).resolve().parent
state=json.loads((work/'STEP2_STATE.json').read_text(encoding='utf-8'))
root=Path(state['root']);folder=root/'assets/v2_5/outfits/starsea_gown'
prefix='assets/v2_5/outfits/starsea_gown/'
for rel,h in state['existingFileHashes'].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h,('changed_existing',rel)
for rel,h in state.get('checkpointProductionHashes',{}).items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h,('changed_checkpoint_production',rel)
modified=subprocess.check_output(['git','diff',state['baseline'],'--name-only'],cwd=root,text=True).splitlines()
assert all(p.startswith(prefix) for p in modified),('outside_scope',modified)
for line in subprocess.check_output(['git','diff',state['baseline'],'--name-status'],cwd=root,text=True).splitlines():
    assert line.startswith('A\t'),('not_add_only',line)
untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=root,text=True).splitlines()
assert all(p.startswith(prefix) for p in untracked),('outside_scope_untracked',untracked)
images=[];failed=[];pending=[];rejected=[];counts={t:0 for t in state['tiers']};blinkExact={t:0 for t in state['tiers']}
for path in sorted((work/'jobs').glob('*.json')):
    rec=json.loads(path.read_text(encoding='utf-8'))
    if rec['status']=='FAILED':
        failed.append({'tier':rec['tier'],'frame':rec['frame'],'error':rec.get('error')});continue
    if rec['status']=='REQUESTED':
        pending.append({'tier':rec['tier'],'frame':rec['frame']});continue
    if rec['status']=='REJECTED_NEEDS_REGEN':
        rejected.append({'tier':rec['tier'],'frame':rec['frame'],'reason':rec['visualIssue']});continue
    if rec['status']!='CANDIDATE':continue
    tier=rec['tier'];name=rec['frame'];dest=folder/tier/name
    assert name in state['missingAtStart'][tier],('not_requested',dest)
    with Image.open(dest) as im:
        im.load()
        assert im.size==(1254,1254) and im.mode=='RGBA',(dest,im.size,im.mode)
        alpha=im.getchannel('A');assert alpha.getextrema()==(0,255),dest
        corners=[alpha.getpixel(pt) for pt in [(0,0),(1253,0),(0,1253),(1253,1253)]]
        assert max(corners)<=1,(dest,corners)
        pixelhash=hashlib.sha256(im.tobytes()).hexdigest()
        bbox=alpha.point(lambda v:255 if v>32 else 0).getbbox()
        if rec.get('outsideEyeExact'):
            master=folder/tier/rec['master']
            assert hashlib.sha256(master.read_bytes()).hexdigest()==rec['masterSha256'],('changed_blink_master',dest)
            base=Image.open(master).convert('RGBA')
            mask=Image.new('L',im.size,0);draw=ImageDraw.Draw(mask)
            for j,box in enumerate(rec['eyeRectangles']):
                if j==0 and rec.get('eyePolygons'):draw.polygon([tuple(p) for p in rec['eyePolygons'][0]],fill=255)
                else:draw.rectangle(tuple(box),fill=255)
            for box in rec.get('eyeBoundaryPatches') or []:draw.rectangle(tuple(box),fill=255)
            mask=mask.filter(ImageFilter.MaxFilter(17))
            draw=ImageDraw.Draw(mask)
            for box in rec.get('protectedEyebrows') or []:draw.rectangle(tuple(box),fill=0)
            outside=ImageChops.multiply(ImageChops.difference(im.convert('RGB'),base.convert('RGB')),ImageChops.invert(mask).convert('RGB'))
            assert outside.getbbox() is None,('outside_eye_changed',dest)
            assert alpha.tobytes()==base.getchannel('A').tobytes(),('blink_alpha_changed',dest)
            blinkExact[tier]+=1
    native=QImage(str(dest))
    assert not native.isNull() and native.hasAlphaChannel() and native.width()==1254 and native.height()==1254,dest
    frame=next(f for f in state['frames'] if f['name']==name)
    ref=Path(frame['reference'])
    assert hashlib.sha256(ref.read_bytes()).hexdigest()==frame['sourceSha256'],('changed_source_snapshot',ref)
    with Image.open(ref) as source:
        oldbbox=source.convert('RGBA').getchannel('A').point(lambda v:255 if v>32 else 0).getbbox()
    counts[tier]+=1
    images.append({'tier':tier,'frame':name,'fileSha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'pixelSha256':pixelhash,'sourceBBox':oldbbox,'newBBox':bbox,'topDelta':bbox[1]-oldbbox[1],'cornerAlpha':corners})
assert len({im['pixelSha256'] for im in images})==len(images),'duplicate decoded sprites'
expected={(im['tier'],im['frame']) for im in images}
actual={(tier,path.name) for tier in state['tiers'] for path in (folder/tier).glob('*.png') if path.name in state['missingAtStart'][tier]}
inFlight=[]
if '--live' in sys.argv:
    assert expected<=actual,('missing_validated_png',expected-actual)
    for tier,name in actual-expected:
        record=work/'jobs'/(tier+'__'+name+'.json')
        assert record.exists() and json.loads(record.read_text(encoding='utf-8'))['status'] in ['REQUESTED','CANDIDATE'],('unrecorded_new_png',tier,name)
        inFlight.append({'tier':tier,'frame':name})
else:assert actual==expected,('unrecorded_or_missing_production_png',actual^expected)
report={'status':'PASS_SAVED_FORMAT_QT_AND_ADD_ONLY_SCOPE','saved':len(images),'counts':counts,'blinkOutsideEyeAndAlphaExact':blinkExact,'requiredNew':415,'frozenExistingUnchanged':len(state['existingFileHashes']),'pending':pending,'failed':failed,'rejected':rejected,'images':images,'limits':['Exact pose/foot/head pixel landmarks not quantitatively certified; visual review separate']}
report['inFlightNotValidated']=inFlight
report['resumeCounts']={tier:sum(1 for im in images if im['tier']==tier and im['frame'] in state['resumeMissingAtStart'][tier]) for tier in state['tiers']}
report['resumeSaved']=sum(report['resumeCounts'].values())
report['resumeRequired']=243
report['frozenTierSprites']=state['frozenTierSprites']
(work/'CURRENT_QA.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
state['done']={t:[im['frame'] for im in images if im['tier']==t] for t in state['tiers']}
state['currentValidation']={k:report[k] for k in ['status','saved','counts','requiredNew','frozenExistingUnchanged']}
(work/'STEP2_STATE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ['images','failed','pending']}))
print(json.dumps({'pending':len(pending),'failed':[f['frame'] for f in failed],'topDeltaOver20':[im for im in images if abs(im['topDelta'])>20]}))
