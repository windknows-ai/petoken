# Petoken 2.3 月夜睡衣 — 完整生成记录

状态：**WAITING_FOR_HUMAN_ART_QA**。第一批已由用户验收；本次补齐14张动作、增加2张衔接、重做4张换装，合计25张PNG。已验收的5张night_idle文件保持原SHA256。

## 工具与参考

- 角色绘制及局部重绘使用imagegen。用户已授权Pillow做局部蒙版合成、alpha清理、基线注册与对比图拼接；没有用程序重画角色。
- 主参考是实际原始坐着抱膝的 `assets/v1_1/idle.png`，原文件未改。沿用已验收 `night_idle_1` 的银白淡紫卷发、大头比例、靛色描边、淡紫长袖/长裤、毛绒袜、月亮发夹及月亮抱枕。
- 只有新姿势母图做一次居中/基线注册；派生动画帧不独立缩放或重新居中。
- 裁剪局部交给imagegen绘制后，按原坐标蒙版合回父图。2026-10-09牛奶原版曾采用不透明内部热气裁剪；2026-10-10牛奶改为两种独立姿势图层与共用底图，详见末尾当前记录。最终PNG均为真正透明RGBA。

## 换装与衔接（本次用户要求优先于旧文档）

- `night_change_0` 复制原始idle，只重绘两个眼部区域为半闭犯困。所有非眼部RGBA像素完全一致，整张alpha也完全一致。
- 顺序制作0→1（睡裤和袜子）→2（长袖睡衣盖手）→3（羽状发饰换小月亮）。每步只合成对应衣物/发饰区域，保留其他像素；第2步包含袖口覆盖膝盖及去除原裙装挂饰的接触区域。
- `night_change_3` 没有枕头，保持抱膝坐。`night_settle_1` 开始放腿、松开膝盖，枕头在身边；`night_settle_2` 已盘腿，正把枕头拉入怀中，随后衔接已验收 `night_idle_1` 的抱枕姿势。
- settle1为过渡新姿势母图；settle2在已验收idle1的躯干/袖子/枕头区域局部重绘，保留其头发、主体脸部和底部位置。

## 动作与多帧

| 动作 | 文件数 | 帧差异 |
|---|---:|---|
| night_idle | 4+眨眼 | 已验收5张不改 |
| night_yawn | 2 | 袖子掩嘴、轻微张口；保留眼角泪光 |
| night_sleep | 3 | 侧躺抱枕，呼吸袖褶、Zzz上飘14px、小幅收腿翻身蹭枕头 |
| night_milk | 2 | 胸前捧杯嘟嘴吹气→双袖举杯到嘴边小口喝；杯子抬高约130px，脸微抬、热气改为上飘 |
| night_read | 2+眨眼 | 盖小被子趴着看图画书，后脚轻踢，眨眼只改眼部 |
| night_goodnight | 2 | 一袖向外举高→整臂向内大幅摆回约43°，另一袖抱枕；星星换位变小 |
| night_wake | 2 | 起身揉眼，头发微乱，枕头滑到腿上；第2帧袖子/枕头轻动 |

- 图画书只含月亮、星星、云朵图案，无文字。睡觉图的Zzz、小月亮和晚安/醒来的小星星是文档明确允许的符号。
- 眨眼只使用眼部蒙版；睡觉翻身帧的头发与身体属于活动区域，不能把它们误记为静止区域。
- 生成时发现的换装衣物接缝、旧枕头边缘残留、牛奶袖口重影及透明缺口均在最终交付前修复；不合格原始生成留在恢复目录供追溯，不作为交付帧。

## 2026-10-09整套交付时的静态检查

以下为b933221交付检查；2026-10-10重做的晚安及牛奶两帧以本文末尾对应的新检查和SHA256为准。

- 25/25：1254×1254、PNG、RGBA、真实alpha通道；不是棋盘格或白底图。
- 17/17局部合成：有效蒙版外RGBA变化为0，包含4张换装、既有4张待机派生及其余局部动画帧。两个眨眼图仅眼部变动。
- 21/21非换装帧：四边alpha=0、最低有效像素y=1218；没有小于24像素的离散alpha连通块。Zzz/月亮/星星等合法独立符号另计，不要求全图只有一个连通主体。
- 换装4帧为明确例外：原idle的alpha bbox是(78,0,1210,1222)，存在原有弱alpha离散像素及顶部边界像素。为了遵守“眼部/换装区外逐像素一致”，保留原有像素，最低alpha仍为y=1221，属于基线y≈1218；未整体清理、缩放或平移。换装区内新产生的离散alpha已清除，没有新增离散块。
- yawn/milk/goodnight/wake两帧各自的y≥1120整条底部RGBA逐像素相同。
- 143/143旧PNG的SHA256未变：138张v1_1/v2_0/v2_1，以及5张已验收night_idle。
- 已查看浅紫总览、128px深底缩略图，以及换装、袖口、抱枕、眼部放大图；检查脸型、发色、服装、基线与合成接缝。
- 这是静态美术验证，未修改应用代码，也没有验证运行时动画播放、柔光揭示、夜间触发或节奏；接入仍由维护者负责。

## Alpha bounding box

Pillow `(left, top, right, bottom)`，右/下边界不包含。

| 文件 | Alpha bbox | 制作来源 |
|---|---|---|
| `night_change_0.png` | `(78, 0, 1210, 1222)` | 原始idle（只改眼睛） |
| `night_change_1.png` | `(78, 0, 1210, 1222)` | night_change_0 |
| `night_change_2.png` | `(78, 0, 1210, 1222)` | night_change_1 |
| `night_change_3.png` | `(78, 53, 1210, 1222)` | night_change_2 |
| `night_settle_1.png` | `(46, 59, 1207, 1219)` | 全姿势母图 |
| `night_settle_2.png` | `(52, 89, 1201, 1219)` | night_idle_1 |
| `night_idle_1.png` | `(52, 89, 1201, 1219)` | 全姿势母图 |
| `night_idle_2.png` | `(48, 87, 1202, 1219)` | night_idle_1 |
| `night_idle_3.png` | `(48, 87, 1202, 1219)` | night_idle_2 |
| `night_idle_4.png` | `(52, 89, 1201, 1219)` | night_idle_1 |
| `night_idle_blink.png` | `(52, 89, 1201, 1219)` | night_idle_1 |
| `night_yawn_1.png` | `(51, 59, 1203, 1219)` | 全姿势母图 |
| `night_yawn_2.png` | `(51, 59, 1203, 1219)` | night_yawn_1 |
| `night_sleep_1.png` | `(40, 329, 1214, 1219)` | 全姿势母图 |
| `night_sleep_2.png` | `(40, 329, 1214, 1219)` | night_sleep_1 |
| `night_sleep_3.png` | `(33, 330, 1220, 1219)` | night_sleep_1 |
| `night_milk_1.png` | `(51, 82, 1206, 1219)` | 共用静态母图 + 手臂/杯子/表情/热气图层（2026-10-10） |
| `night_milk_2.png` | `(51, 82, 1206, 1219)` | 共用静态母图 + 手臂/杯子/表情/热气图层（2026-10-10） |
| `night_read_1.png` | `(40, 212, 1214, 1219)` | 全姿势母图 |
| `night_read_2.png` | `(40, 212, 1233, 1219)` | night_read_1 |
| `night_read_blink.png` | `(40, 212, 1214, 1219)` | night_read_1 |
| `night_goodnight_1.png` | `(45, 23, 1206, 1219)` | 共用静态母图 + 独立挥手/星星图层（2026-10-10） |
| `night_goodnight_2.png` | `(50, 23, 1206, 1219)` | 共用静态母图 + 独立挥手/星星图层（2026-10-10） |
| `night_wake_1.png` | `(57, 30, 1197, 1219)` | 全姿势母图 |
| `night_wake_2.png` | `(57, 30, 1197, 1219)` | night_wake_1 |

## 交付与恢复

- 图文件：`assets/v2_3/`，完整25张。对比图：`docs/V2_3_ART_PREVIEW.png`，浅紫底#D0CCE4，整张画布等比展示，附128px深底检查。
- 2026-10-09历史批次的完整提示词、参考、父帧、蒙版多边形、alpha bbox、SHA256及校验结果见 `GENERATION.json`。2026-10-10重画的晚安与牛奶以末尾当前记录及各自恢复目录为准。
- 本批恢复目录：`D:\Documents\ChatGPT\petoken-takeover-backups\v2.3-art-batch2`，含原始生成、局部参考、蒙版、脚本、validation.json及PROGRESS.md。第一批原4张换装已被本次替换，旧记录仍在original-firstbatch中。
- 下一步由用户验收第二批；本地提交到codex/v2.3-art，不合并、不推送。

## 2026-10-10 · 晚安挥手幅度重画

本节取代b933221中的两张晚安图。本次严格只改night_goodnight_1.png、night_goodnight_2.png、本文件及docs/V2_3_ART_PREVIEW.png；不新增眨眼、不改代码，也不改其他动作。

### 制作方式

- 使用imagegen依据原night_goodnight_1绘制两种整臂挥手姿势，以及移除挥手手臂后的共用静态母图；先前尝试的局部头发补图产生接缝，弃用。
- 用户已授权Pillow做图层提取、透明边缘清理、合成和预览。两张分别提取新的手臂及小星星，叠到同一份RGBA静态母图；用固定枕头前景保护区恢复完整枕头/抱枕袖子，y>=835整条身体/腿部区域也复用母图原像素。
- 共用母图只做一次基线注册（y方向-1px），两帧不独立居中、缩放。头和头发主体保持固定，不增加可选的歪头微动；手臂经过头发时仅遮挡/露出，头发底图不移动。
- 第1帧袖子盖手，整臂向人物外侧高举。第2帧整臂向内摆到近竖直位置，袖口随姿势重绘。第1帧星星在外侧较大，第2帧移到手边并缩小，形成闪烁。

### 当前版本验证

- 2/2：1254×1254、RGBA PNG、真实透明背景，四条画布边缘alpha均为0，最低有效像素y=1218。
- 两帧有效挥手手臂/星星蒙版联合区域以外，RGBA变化像素为0。枕头保护区、整个y>=835身体/腿部区域变化像素都为0；保持静态头部及头发底图。
- 两帧alpha>0连通块检查无小于24像素的离散脏点；星星属于允许的独立图形。已查看浅紫背景大图及128px深色预览，并检查袖口、肩部衔接和头发露出区域。
- 手部框为人工在1254px图上标注，中心分别(177.0, 430.0)、(530.5, 385.0)；肩部近似标注(507, 822)。按肩到手部框中心向量计算，摆幅约43.2°，手部中心位移356.4px，大于手部框宽203px。角度是二维图像标注估算，不是3D骨骼测量。
- 按整张1254²画布RGBA任一通道变化计数，两帧变化像素167207，占10.63%。

| 当前文件 | SHA256 | Alpha bbox |
|---|---|---|
| `night_goodnight_1.png` | `13623d619c7ea09c94ce5a3da50cbc8024b5bd351adc2dffa4367541dcc43c8e` | `(45, 23, 1206, 1219)` |
| `night_goodnight_2.png` | `37632f1a946eb2c13f9480d1accbe163d75075036907866d24a0df502183d1d7` | `(50, 23, 1206, 1219)` |

### 追溯与接入

- 旧GENERATION.json保留2026-10-09历史记录；按照本次四文件范围没有修改它。其晚安条目的旧SHA、父帧/蒙版及批次验证不代表当前两张图，本节的新数据为准。
- 恢复目录：`D:\Documents\ChatGPT\petoken-takeover-backups\v2.3-goodnight-wave`，包含原图备份、全部生成来源/提示词、共用底图、图层蒙版、compose.py、validate.py、validation.json及PROGRESS.md。
- 当前选用生成源：共用底图`C:\Users\fengz\.codex\generated_images\01a0d97f-5017-71c2-8ba4-181bc329b670\exec-dc2431ae-4fc0-41da-94ee-cb5f8c55439d.png`；帧1手臂/星星`C:\Users\fengz\.codex\generated_images\01a0d97f-5017-71c2-8ba4-181bc329b670\exec-3b67832b-b676-40c5-a71d-1ba0130a0bc7.png`；帧2手臂/星星`C:\Users\fengz\.codex\generated_images\01a0d97f-5017-71c2-8ba4-181bc329b670\exec-82d99ab1-550a-417b-ba40-4772e5486618.png`。
- 不合格局部底图和首次合成保留在恢复目录供追溯，不作为交付。
- 静态美术验证完成，未改动画播放节奏或运行时实现。本地提交codex/v2.3-art，不合并、不推送，等待用户确认新挥手效果。

## 2026-10-10 · 热牛奶动作重画

本节取代b933221中的两张牛奶图。只修改night_milk_1.png、night_milk_2.png、本文件和docs/V2_3_ART_PREVIEW.png。不新增眨眼、不改其他动作或代码。

### 制作方式与动作

- 角色与姿势仍由内置imagegen绘制，非程序绘制：以原night_milk_1为风格参考，先绘制胸前吹气帧，再以其为参考绘制举杯喝奶帧；另生成移除杯子、手臂和热气的共用静态底图。
- 使用已获授权的Pillow提取袖子、杯子、表情与热气图层，并叠到同一份底图。腿部使用同一份保护图层，主体卷发、月亮发夹、身体及衣服底图固定；前景袖子/杯子只改变遮挡关系。中间刘海使用固定保护蒙版恢复，脸部接缝用同一生成脸上的皮肤小补片合成修复。
- 两帧只对共用底图做一次y=-1px基线注册；图层使用相同坐标，无独立居中或缩放。
- 第1帧双袖捧杯放在胸前，低头嘟嘴吹气，与杯沿保留间距，热气偏向画面右侧。第2帧双臂举杯到嘴边小口喝，眼睛满足地眯起、脸部微抬，热气上飘。
- 原牛奶动作没有枕头，本次也没有添加枕头。杯子沿用白色杯身及淡紫月亮图案；睡衣仍是淡紫配色、深色描边、柔和赛璐璐上色。

### 当前验证

- 2/2：1254×1254、RGBA透明PNG，四条画布边缘alpha均为0，最低有效像素均为y=1218。没有白底、文字、地面或新增眨眼图。
- 两帧有效手臂/袖子/杯子、脸部、热气蒙版联合区域以外，RGBA变化像素为0。整个y>=1062的身体下部/腿/脚区域变化为0；未被前景遮挡的腿部保护区也为0。
- 固定中间刘海保护区变化为0；头顶y<450及两侧主卷发区域（x<450或x>=977、450<=y<1062）变化为0。头部动作表现为眼睑与脸部略抬，头发主体不移动。
- alpha>0连通块检查无小于24像素的离散脏点；已经查看浅紫底大图、脸部/袖口/杯子放大图与128px深底缩略图。
- 人工标注的杯身框（不含热气/手部）为[[653, 832, 781, 986], [668, 702, 809, 857]]；杯身中心分别[[717.0, 909.0], [738.5, 779.5]]，向上移动约129.5px。此为二维图片估算，不是骨骼测量。
- 整张1254²画布按RGBA任一通道变化计数：178023像素，约11.32%。

| 当前文件 | SHA256 | Alpha bbox |
|---|---|---|
| `night_milk_1.png` | `ed55c9fd3942bdd6b5e5b7dc15986634706addcb8c3896085a33100a9a7c4f69` | `(51, 82, 1206, 1219)` |
| `night_milk_2.png` | `38ca4754c152e348c9cbd75b621e8d50835b1f26b17835985e58caea16d24529` | `(51, 82, 1206, 1219)` |

### 提示词与追溯

以下为当前选用imagegen原始提示词（英文）；图层合成后交付为上述两个PNG。

#### 胸前吹气

> Edit this exact transparent chibi pajama sprite for the first frame of drinking warm milk. Output ONE full1254x1254 transparent RGBA sprite at precisely same framing. Preserve character silver-white lavender curls, moon hair clip, lavender moon pajamas and bow, crossed legs and fluffy white slippers, black lineart and soft cel-shading. Change only arms/sleeves,mug,face and steam. BOTH sleeve-covered hands cradle SAME white crescent-decorated mug LOW at chest: mug top approximately y930, bottom1050, centerx720 in1254px canvas. She tips face slightly down toward the mug, sleepy squinted eyes and little PURSED o-shaped lips BLOW gently downward toward the milk. Two small soft wisps of steam bend conspicuously sideways toward viewer right. Arms extend down slightly to hold low mug, wrists almost covered by loose sleeves. Chest and sleeves match reference. Keep outer hair mass, head outline, seated body and legs fixed in the original position. This is blow on milk, not drink yet: leave a clear gap between lips and cup. No new props, no pillow, no text, no floor, no background. Do not crop any hair or feet. Feet lowest point1218. No blink variant. Faithfully same drawing style.

#### 举杯小口喝

> Create second animation frame by editing this EXACT transparent sprite. SAME1254x1254 character canvas; same silver-lavender long curls, moon hairclip, lavender pajamas and crossed legs/slippers. NOW raise BOTH sleeve-covered arms and the SAME white crescent mug to her MOUTH for a small sip. Move mug clearly UP about150pixels: brim touches lower lip aroundy710, cupbottomaroundy860; cup must visually cover lower face partially. Both large lavender sleeves raised into a V, elbows remain near torso atapprox(530,990) and(875,990), coveredhands support cup atcheeklevel. Head/face slightly lifts, eyes crinkle in contented closed sleepy smile with happy blush. Steam floats vertically above cup onviewer right side without obscuring eyes. Crucial large motion from earlier chest position, actually drinks rather than holding cup belowchin. Preserve same outer hair mass and hair edges, unchanged crosslegs, shoes, pajama torso and bow style. Keep uniformblack lineart, lavendercelshading. No text, no extra objects, no pillow,no ground; transparent background. No crop. Feetminy1218.

#### 共用静态底图

> Precise object-removal edit of this sprite to make the shared static underpainting for animation. ONE1254x1254 transparent RGBA. Remove the cup, BOTH entire arms and sleeves, and ALL steam. Restore the pajama torso behind removed cup/arms, exactly matching pale lavender pajama cloth, small tied dark lavender collarbow,2 small pale buttons and moon-themed print. Arms are hidden behind her back and should NOT be visible anywhere, no hands. Preserve character crossedlegs and slippers, hairmassand curls, head face expression, moonhairclip, and outer silhouette exactly like image1. Restore natural hair strands where sleeves were hiding them. This must look like exact same seatedgirl withhands hiddenbehindback, no objects. No steam, cup, extra props, pillow, written words. Sameblackoutlinecelshading. No moved feet, no recenter, no resizing. Retain fullytransparentbackground, lowestfootpixel1218. This underpaintingwill becovered by newarm/muglayers; no other redesign.

- 选用源：吹气 `C:\Users\fengz\.codex\generated_images\01a0d97f-5017-71c2-8ba4-181bc329b670\exec-f9662c18-c8e3-4307-af44-571495c4b7eb.png`；喝奶 `C:\Users\fengz\.codex\generated_images\01a0d97f-5017-71c2-8ba4-181bc329b670\exec-a4685983-39b5-4bed-80c4-ad0687652fbb.png`；底图 `C:\Users\fengz\.codex\generated_images\01a0d97f-5017-71c2-8ba4-181bc329b670\exec-d7730038-95d0-4bec-a3aa-4a15fc7f8401.png`。
- 恢复目录：`D:\Documents\ChatGPT\petoken-takeover-backups\v2.3-milk-sip`，包括原图备份、sources.json、compose.py、图层和保护蒙版、validate.py、validation.json、两帧GIF预览、全部资产基线SHA及PROGRESS.md。
- GENERATION.json是2026-10-09历史记录，按本次四文件范围未修改。其牛奶条目的旧SHA、热气限定蒙版及旧验证不适用于当前两张图；以本节为准。
- 已完成静态美术及帧差检查。没有修改或验证运行时动画逻辑、播放速度；应用接入由维护者负责。状态为WAITING_FOR_HUMAN_ART_QA，本地提交codex/v2.3-art，不合并、不推送。
