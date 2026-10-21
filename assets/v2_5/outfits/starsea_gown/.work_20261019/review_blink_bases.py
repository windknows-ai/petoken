import json,sys,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

work=Path(__file__).resolve().parent;folder=work.parent;tier=sys.argv[1]
s=json.loads((work/'STEP2_STATE.json').read_text(encoding='utf-8'))
names=[n.replace('_blink','_1') for n in s['resumeMissingAtStart'][tier] if '_blink' in n]
canvas=Image.new('RGB',(1500,math.ceil(len(names)/5)*325),(35,40,55));draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',16)
for i,n in enumerate(names):
    image=Image.open(folder/tier/n).convert('RGBA');image.thumbnail((290,290));x=i%5*300;y=i//5*325
    canvas.paste(image,(x,y+25),image);draw.text((x,y),n,font=font,fill='white')
canvas.save(work/'review'/(tier.upper()+'_BLINK_BASES.png'))
print(json.dumps({'tier':tier,'bases':len(names)}))
