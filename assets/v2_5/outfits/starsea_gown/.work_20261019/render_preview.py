import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

work=Path(__file__).resolve().parent;folder=work.parent
s=json.loads((work/'STEP2_STATE.json').read_text(encoding='utf-8'))
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17);title=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',28);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',11)
counts={t:sum((folder/t/n).exists() for n in s['missingAtStart'][t]) for t in s['tiers']}
canvas=Image.new('RGB',(2048,4900),(28,33,47));draw=ImageDraw.Draw(canvas)
draw.text((20,12),'星海长裙 · 第二步动作总览',font=title,fill='white')
draw.text((20,55),str(sum(counts.values()))+' / 415 新增帧；已验收图片保持不变。灰格为尚待补全。',font=font,fill=(200,214,235))
labels=dict(zip(s['tiers'],['繁星','明月','皓日','银河','星海']))
for ti,t in enumerate(s['tiers']):
    y0=100+ti*960;draw.text((15,y0),labels[t]+'   新增 '+str(counts[t])+' / 83',font=title,fill='white')
    for i,r in enumerate(s['frames']):
        x=i%16*128;y=y0+55+i//16*151
        draw.rectangle((x+2,y+2,x+126,y+127),fill=(44,49,64));path=folder/t/r['name']
        if path.exists():
            im=Image.open(path).convert('RGBA');im.thumbnail((124,124));canvas.paste(im,(x+(128-im.width)//2,y+(128-im.height)//2),im)
        else:draw.text((x+39,y+50),'待补',font=font,fill=(117,126,145))
        draw.text((x+2,y+130),r['name'].removesuffix('.png'),font=small,fill=(209,215,228))
dest=folder/'STARSEA_GOWN_STEP2_20261019_PREVIEW.png'
assert not dest.exists(),'Never overwrite an existing preview'
canvas.save(dest)
print(json.dumps({'preview':str(dest),'step2NewCounts':counts}))
