# Petoken 2.0 动作提示词（给 Codex 画图用）

目标：她要像真的活过来一样。**每个动作都是一张重新画的全身姿势**：站着、坐着、趴着、蹲着、悬空，身体轮廓要和其他动作明显不同。不能在 `idle.png` 上只改手或表情来凑数，也不能两个动作共用同一个身体。

## 一、总规则（每张都要满足）

1. **同一个角色**：以 `assets/v1_1/idle.png` 作为角色设定参考：银紫色长卷发、冰蓝色发饰、深蓝紫色带月亮纹样的服装、深色长袜、Q 版比例（大头、短身体）、同样的线条粗细和上色方式。只改变姿势、表情和道具，不换衣服，不加新角色。
2. **重新画全身**：每个动作单独生成一张全新的全身图。只有**同一个动作的几帧之间**、以及眨眼图，才在这个动作自己的第 1 帧上局部重绘。
3. **画布**：1254×1254 像素 PNG，真正的透明背景（alpha 通道）。没有棋盘格、底色、阴影底或地面。
4. **基线**：人物最低点（脚底、膝盖或趴着时的身体下沿）落在 y≈1218 像素，和 `idle.png` 一样，左右大致居中。站着的动作会比坐着的高，没关系，但头顶不要超出画布。趴着、悬空这类横向动作，宽度不要超出画布左右各 40 像素以内的安全边。
5. **小尺寸也看得懂**：桌宠实际显示约 128～200 像素。动作要夸张，轮廓清楚，表情一眼能看出来，细节不要太碎。
6. **图里不要有文字**。可以有符号：爱心、Zzz、汗滴、问号、感叹号、星星、音符、热气。
7. **帧**：`<名称>_1.png`、`<名称>_2.png`……（只有 1 帧的动作也叫 `<名称>_1.png`）。第 1 帧是完整的新姿势，后面的帧在第 1 帧上只重绘动的部位（不动的部分逐像素一致），这样循环时不会抖。
8. **眨眼图**：`<名称>_blink.png`，在第 1 帧上只把眼睛画成闭上（弯弯的线），其他像素不动。本来就闭眼的动作不要画。
9. **文件位置**：`assets/v2_0/`。完成一批后，更新 `docs/V2_0_ART_PREVIEW.png` 总览图，并在 `assets/v2_0/GENERATION.md` 记录每张的生成方式。

### 每张都用的风格前缀（英文，放在每条提示词最前面）

> Chibi anime girl, same character as the reference image (silver-lavender long wavy hair, ice-blue crystal hair ornament, dark navy-violet outfit with crescent-moon motif, dark thigh-high stockings), big head small body, clean thick lineart, soft cel shading, pastel lavender palette, full body, centered, transparent background, no text, no ground, no shadow, sticker-like clarity readable at 128px,

## 二、动作清单和提示词

格式：**文件名 · 中文名**（帧数 · 是否要眨眼图）— 英文提示词（接在风格前缀后面）— 帧说明。

### A. 日常和互动

- **`sleep` · 趴着睡**（3 帧 · 不要眨眼图）**← 已交付的版本请重画**
  > lying face-down on her stomach on a small round lavender cushion, cheek resting on her folded arms, legs stretched out behind and slightly bent up at the knees, eyes peacefully closed, tiny "Zzz" floating above, relaxed sleeping face, viewed from the front-side
  - 帧：1 吸气（背部略高）→ 2 呼气（背部略低、Zzz 往上飘）→ 3 一只脚的小腿轻轻晃一下。

- **`bored` · 无聊趴着托腮**（3 帧 · 要眨眼图）
  > lying on her stomach propped up on both elbows, chin resting in both hands, legs bent up behind her and crossed at the ankles, half-lidded bored eyes looking off to the side, small flat pouty mouth
  - 帧：1 → 2 小腿往一边晃 → 3 小腿往另一边晃。

- **`yawn` · 打哈欠**（3 帧 · 不要眨眼图）
  > sitting on the floor with legs to one side, one arm stretched high above her head, the other hand covering a wide-open yawning mouth, eyes squeezed shut, a small tear at the corner of one eye
  - 帧：1 刚开始张嘴 → 2 嘴张最大、手臂最高 → 3 嘴合上、手臂放下一半。

- **`wake_stretch` · 醒来伸懒腰**（2 帧 · 不要眨眼图）
  > kneeling up straight with both arms stretched high above her head, fingers interlaced, back arched, eyes squinting sleepily, small sparkles around
  - 帧：1 伸到最高 → 2 手臂微微往一边歪。

- **`curious` · 好奇凑近**（2 帧 · 要眨眼图）
  > on her hands and knees leaning forward toward the viewer, head tilted to one side, big sparkling curious eyes, mouth slightly open
  - 帧：1 → 2 头往另一边歪。

- **`thinking` · 盘腿思考**（2 帧 · 要眨眼图）
  > sitting cross-legged, one index finger tapping her chin, eyes looking up and to the side, a small question mark bubble above her head
  - 帧：1 → 2 手指点一下下巴、问号轻轻跳一下。

- **`shy` · 害羞捂脸**（2 帧 · 不要眨眼图）
  > standing with knees together and toes pointed inward, both hands covering her blushing face, peeking through her fingers with one eye, deep blush on the cheeks
  - 帧：1 → 2 手指缝张开一点、偷看。

- **`pout` · 鼓脸生气**（2 帧 · 要眨眼图）
  > standing, arms crossed tightly, cheeks puffed out, eyebrows furrowed, one foot raised mid-stomp, a small cartoon anger mark next to her head, cute rather than scary
  - 帧：1 脚抬起 → 2 脚跺下、腮帮更鼓。
  - 注意：要和 `sad` 完全不同：叉手、跺脚、鼓腮，是「哼」而不是难过。

- **`poked` · 被戳歪了**（1 帧 · 不要眨眼图）
  > standing but tipping sideways off balance as if just poked, one eye squeezed shut, arms flung out for balance, a small exclamation mark

- **`dragged` · 被拎起来**（4 帧 · 不要眨眼图）
  > dangling in mid-air as if lifted by the back of her collar, legs dangling and kicking, arms flailing, surprised flustered face, a sweat drop, no hand or hook visible
  - 帧：左手和右脚、右手和左脚交替乱晃（4 个关键姿势）。

- **`landing` · 落地站稳**（1 帧 · 要眨眼图）
  > landing in a low crouch on both feet, knees deeply bent, arms spread wide for balance, a tiny puff of dust at her feet, relieved expression

- **`hug` · 张开双臂要抱抱**（2 帧 · 要眨眼图）
  > standing and leaning toward the viewer with both arms open wide for a hug, big happy smile, small hearts
  - 帧：1 → 2 手臂再张开一点、身体往前倾。

- **`heart` · 比心**（1 帧 · 不要眨眼图）
  > standing, both hands forming a heart shape in front of her chest, winking with one eye, cheerful smile, a small heart floating

- **`greet_morning` · 早安**（2 帧 · 要眨眼图）
  > standing, rubbing one sleepy eye with one hand and waving with the other, a small cartoon sun beside her
  - 帧：挥手的手在左、在右。

- **`greet_night` · 晚安**（2 帧 · 不要眨眼图）
  > standing, hugging a fluffy pillow with one arm, waving goodnight drowsily with the other hand, eyes half closed, a small crescent moon beside her
  - 帧：挥手的手在左、在右。

- **`surprised` · 吓一跳**（1 帧 · 不要眨眼图）
  > jumping slightly off the ground in surprise, both hands raised, eyes wide open, hair bouncing up, an exclamation mark above her head

- **`thumbs_up` · 点赞**（1 帧 · 要眨眼图）
  > standing confidently, one hand giving a thumbs up toward the viewer, the other hand on her hip, bright grin

- **`cheer` · 加油**（2 帧 · 要眨眼图）
  > standing, one fist pumped high in the air, the other fist at her side, determined energetic expression
  - 帧：拳头举高 / 放到肩膀高度。

- **`clap` · 鼓掌**（3 帧 · 要眨眼图）
  > standing, clapping her hands in front of her chest, joyful closed-mouth smile, small sparkles
  - 帧：手张开 → 合拢 → 张开。

- **`peek` · 躲着偷看**（2 帧 · 不要眨眼图）
  > hiding behind a big round lavender cushion, only her eyes, the top of her head and her hair ornament visible above it, fingertips gripping the cushion edge
  - 帧：1 → 2 往上探出一点点。

- **`grievance` · 委屈**（2 帧 · 不要眨眼图）
  > kneeling in seiza, teary glistening eyes, trembling wavy mouth, fiddling with her fingers in front of her
  - 帧：1 → 2 一滴眼泪往下滑。

### B. 专注陪伴

- **`focus_read` · 陪你看书**（4 帧 · 要眨眼图）
  > sitting on a floor cushion at a tiny low wooden desk, reading an open book on the desk, calm gentle focused expression, a small steaming cup on the desk
  - 帧：1 看书 → 2 翻页 → 3 看书 → 4 抬眼偷看你一下。

- **`focus_tea` · 休息喝茶**（2 帧 · 不要眨眼图）
  > sitting with legs tucked to one side, holding a warm cup of tea in both hands near her face, eyes closed contentedly, steam rising
  - 帧：热气飘的形状变化。

- **`focus_done` · 专注完成**（1 帧 · 要眨眼图）
  > standing proudly, holding up a small notebook with a big check mark on its cover (no text), happy smile, small sparkles

- **`stretch_break` · 起来活动**（2 帧 · 要眨眼图）
  > standing, doing a side stretch with one arm over her head and the other on her hip, leaning to one side, refreshed expression
  - 帧：往左伸 / 往右伸。

### C. 项目

- **`hold_card` · 拿着「上次做到哪」卡片**（1 帧 · 要眨眼图）
  > standing, holding a large blank paper card with both hands in front of her chest, card facing the viewer and clearly empty, warm smile

- **`packing` · 收拾东西**（1 帧 · 要眨眼图）
  > standing, hugging a folder and a couple of papers against her chest, glancing to the side as if about to leave

- **`ready_go` · 出发**（1 帧 · 要眨眼图）
  > standing in a lively stance, one foot forward, pointing forward with one hand, the other hand in a fist, energetic eager face

### D. 用量目标

- **`worried` · 担心**（2 帧 · 要眨眼图）
  > standing, nervously biting the tip of her thumb, eyebrows furrowed, a big sweat drop, knees slightly bent inward
  - 帧：1 → 2 汗滴往下滑一点。

- **`proud` · 得意**（1 帧 · 要眨眼图）
  > standing with both hands on her hips, chin raised, eyes closed in a smug proud smile, sparkles around her

### E. 已交付的样张

- `coquettish`（撒娇）、`headpat_happy`（被摸头）、`idle_blink`：保留。
- `sleep`：请按上面「趴着睡」重画（3 帧）。

## 三、交付顺序

1. 先交 `sleep`、`bored`、`yawn`、`peek`、`pout` 这 5 个动作的全部帧（它们目前最不明显），附一张总览图。
2. 确认后交其余 A 类，然后 B、C、D。
3. 每批自检：尺寸、透明、基线、帧之间不动部分逐像素一致、没有文字，**以及任何两个动作的身体轮廓都不一样**。
