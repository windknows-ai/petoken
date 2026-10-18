import argparse,json,math
from pathlib import Path
from PIL import Image,ImageDraw

parser=argparse.ArgumentParser();parser.add_argument('tier');args=parser.parse_args()
work=Path(__file__).resolve().parent;folder=work.parent;tier=args.tier
report='BLINK_COMPOSITE_QA.json' if tier=='fanxing' else tier.upper()+'_BLINK_COMPOSITE_QA.json'
rows=json.loads((work/report).read_text());out=work/'review';out.mkdir(exist_ok=True)
for page in range(math.ceil(len(rows)/5)):
    group=rows[page*5:(page+1)*5]
    canvas=Image.new('RGB',(1500,len(group)*310),(35,40,55));draw=ImageDraw.Draw(canvas)
    for i,r in enumerate(group):
        boxes=r['eyeRectangles'];crop=(max(0,min(b[0] for b in boxes)-90),max(0,min(b[1] for b in boxes)-80),min(1254,max(b[2] for b in boxes)+90),min(1254,max(b[3] for b in boxes)+80))
        for j,(label,path) in enumerate([('master',folder/tier/r['master']),('generated draft',Path(r['generatedDraft'])),('eye-only result',Path(r['composed']))]):
            image=Image.open(path).convert('RGBA').crop(crop);image.thumbnail((485,270))
            canvas.paste(image,(j*500,i*310+35),image)
            draw.text((j*500+5,i*310+5),r['frame']+' '+label,fill='white')
    canvas.save(out/(tier.upper()+'_BLINK_REVIEW_'+str(page+1)+'.png'))
print(json.dumps({'tier':tier,'reviewedCandidates':len(rows),'sheets':math.ceil(len(rows)/5)}))
