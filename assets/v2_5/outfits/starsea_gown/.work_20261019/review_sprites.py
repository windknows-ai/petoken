import argparse,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

parser=argparse.ArgumentParser();parser.add_argument('tier');parser.add_argument('--group',choices=['masters','adjacent','all'],default='all');args=parser.parse_args()
work=Path(__file__).resolve().parent;folder=work.parent
state=json.loads((work/'STEP2_STATE.json').read_text(encoding='utf-8'))
rows=[n for n in state['resumeMissingAtStart'][args.tier] if '_blink' not in n and (folder/args.tier/n).exists()]
if args.group=='masters':rows=[n for n in rows if n.endswith('_1.png') or n in ['sleep_3.png','dragged_2.png']]
if args.group=='adjacent':rows=[n for n in rows if not n.endswith('_1.png') and n not in ['sleep_3.png','dragged_2.png']]
font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',15)
for page in range(math.ceil(len(rows)/12)):
    group=rows[page*12:(page+1)*12];canvas=Image.new('RGB',(1040,math.ceil(len(group)/2)*285),(35,40,55));draw=ImageDraw.Draw(canvas)
    for i,name in enumerate(group):
        x=i%2*520;y=i//2*285
        ref=next(f['reference'] for f in state['frames'] if f['name']==name)
        for j,path in enumerate([Path(ref),folder/args.tier/name]):
            image=Image.open(path).convert('RGBA');image.thumbnail((252,252));canvas.paste(image,(x+j*260,y+26),image)
        draw.text((x+2,y+3),name+'  default | '+args.tier,font=font,fill='white')
    canvas.save(work/'review'/(args.tier.upper()+'_'+args.group.upper()+'_'+str(page+1)+'.png'))
print(json.dumps({'tier':args.tier,'sprites':len(rows),'sheets':math.ceil(len(rows)/12)}))
