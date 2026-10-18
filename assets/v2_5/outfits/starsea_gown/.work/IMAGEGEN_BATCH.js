
const root=load('root'), folder=load('folder'), s=load('state');
const quote=v=>"'"+v.replaceAll("'","''")+"'";
async function writeJson(path,obj){const json=JSON.stringify(obj,null,2);const r=await tools.exec_command({cmd:"$starseaJson = @'\n"+json+"\n'@\n[IO.File]::WriteAllText("+quote(path)+",$starseaJson,(New-Object Text.UTF8Encoding($false)))",workdir:root,max_output_tokens:300});if(r.exit_code!==0)throw Error(r.output);}
const output=await tools.exec_command({cmd:"Get-ChildItem -LiteralPath "+quote(folder+'\\'+tier)+" -Filter *.png | Select-Object -ExpandProperty Name",workdir:root,max_output_tokens:2000});
const existing=new Set(output.output.trim().split(/\r?\n/));
let names=s.missingAtStart[tier].filter(n=>!existing.has(n)&& (mode==='blink'?n.includes('_blink'):!n.includes('_blink')));
if(mode==='masters') names=names.filter(n=>n.endsWith('_1.png')||['sleep_3.png','dragged_2.png'].includes(n));
if(mode==='adjacent') names=names.filter(n=>!n.endsWith('_1.png')&&!['sleep_3.png','dragged_2.png'].includes(n));
if(typeof selected!=='undefined')names=names.filter(n=>selected.includes(n));
let stopped=false,idx=0;const outcomes=[];
async function worker(){while(idx<names.length&&!stopped){const name=names[idx++], frame=s.frames.find(f=>f.name===name), master=name.replace('_blink','_1');
let prompt, refs,recordPath;
if(mode==='blink'){
refs=[folder+'\\'+tier+'\\'+master];
prompt='Use case: identity-preserve. EYE ONLY EDIT of the single finished '+tier.toUpperCase()+' Starsea Gown sprite. Close every visible open eye into a smooth natural closed dark curved eyelid; remove all iris and sclera. Leave existing closed eye closed. Preserve eyebrow, mouth, blush, face silhouette, hair, pose, hands, props, costume, boots, scale and canvas coordinates EXACTLY. No edit outside tiny eyelid regions; no new light or objects. Keep exact 1254x1254 RGBA transparent canvas and full alpha. Expression is same except closed eyes. Output one sprite, no text. Pair '+name+' with '+master+'. This is a closed-eyelid draft for authorized exact eye-only compositing.';
recordPath=folder+'\\.work\\blinks\\'+tier+'__'+name+'.json';
}else{
const sole=['sleep_3.png','bored_1.png','curious_1.png','curious_2.png','stretch_break_2.png'].includes(name);
const costumeMaster=mode==='adjacent'?(name.startsWith('dragged_')?'dragged_2.png':name.replace(/_\d+\.png$/,'_1.png')):'idle_1.png';
refs=sole?[frame.reference]:[frame.reference,folder+'\\'+tier+'\\'+costumeMaster];
prompt='Use case: identity-preserve. ONE production 1254x1254 RGBA transparent chibi sprite. INPUT 1 is the EXACT default action reference and absolute authority for pose and props: trace its head, hair outline, expression, mouth, every hand/finger and prop, knee and boot/foot tips at SAME coordinates and size. Never recenter, enlarge, shift, zoom, change the gesture or invent a prop. Same silver lavender hair, violet eyes and natural blue side feather. '+(sole?'Apply this accepted costume design without moving the character: ':'INPUT 2 is accepted '+tier.toUpperCase()+' COSTUME ONLY; ignore its pose and keep INPUT 1 geometry. Transfer exactly this costume: ')+s.specs[tier]+' Fully covered opaque modest bodice, long opaque sleeves where needed, no new cutouts or exposed torso. Clothes drape around ORIGINAL knees and props; never replace gesture. All hair/cloth/boot tips inside canvas with original margins. Genuine empty alpha, no opaque backdrop, no text, no extra anatomy. Default reference IMAGE overrides action labels or prose. '+(s.actionOverrides?.[name]||'');
if(name==='headpat_happy_3.png')prompt+=' Original frame 3 has a tiny CLOSED-mouth smile; do not copy frame 1 open mouth.';
if(name==='curious_1.png')prompt+=' Fully opaque high collar and long sleeves; retain source lean without exposed chest.';
if(tier==='haori'&&['sleep_3.png','bored_1.png','curious_1.png'].includes(name))prompt+=' IMPORTANT correction: natural side feather MUST stay bright icy BLUE and navy, exactly like input reference, never gold/yellow. Sun brooch is separate small golden jewelry, not a replacement or recolor of the feather. Keep feather tips and source head/boot coordinates.';
recordPath=folder+'\\.work\\jobs\\'+tier+'__'+name+'.json';
}
let rec={tier,frame:name,source:frame.source,sourceSha256:frame.sourceSha256,prompt,status:'REQUESTED',references:refs};
if(mode==='blink'){rec.master=master;rec.target=refs[0];}
await writeJson(recordPath,rec);
try{
const r=await tools.image_gen__imagegen({prompt,referenced_image_paths:refs,transparent_background:true});
const path=r.output_hint?.match(/as (C:\\[^\r\n]+?\.png) by default/)?.[1];
if(!path)throw Error(JSON.stringify(r));
rec.generated=path;rec.status='CANDIDATE';
if(mode!=='blink'){const d=folder+'\\'+tier+'\\'+name;const copy=await tools.exec_command({cmd:"if (Test-Path -LiteralPath "+quote(d)+") { throw 'Target already exists' }; Copy-Item -LiteralPath "+quote(path)+" -Destination "+quote(d),workdir:root,max_output_tokens:300});if(copy.exit_code!==0)throw Error(copy.output);}
await writeJson(recordPath,rec);outcomes.push({name,status:'saved'});notify(tier+' '+name+(mode==='blink'?' blink draft ready':' saved'));
}catch(e){rec.status='FAILED';rec.error=String(e);await writeJson(recordPath,rec);outcomes.push({name,status:'FAILED',error:rec.error});if(/usage_limit|quota|rate_limit/i.test(rec.error))stopped=true;notify({tier,name,error:rec.error.slice(0,500)});}
}}
await Promise.all(Array.from({length:pool},worker));
text({tier,mode,stopped,outcomes});
