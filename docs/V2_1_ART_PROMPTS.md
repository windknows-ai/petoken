# Petoken 2.1 游戏模式：第二形态和变身动画提示词（给 Codex 画图用）

2.1 新增「游戏模式」：你开始打游戏时，她从待机姿势**连续地**变身成第二形态（参考斗罗大陆海神着甲：身体一直看得见，铠甲一片一片在她身上成形，不是闪白、淡入淡出或转场），身后升起星环，最后摆出约 2 秒的 MVP 姿势，再进入游戏形态。第二形态还是她本人，但**不那么萌，要霸气、飒爽、有威严**（气质参考神王一类的形象，只参考气质，不照搬任何现成作品的造型）。

动画由 Petoken 实时合成（60–120 帧）：光线沿轮廓扫过、粒子、星环、飘动、镜头推近都由代码画。**Codex 只需要画「阶段图」**，关键是阶段图之间除了新增的那一块，其余像素完全一致，代码会对比相邻两张图，自动算出新出现的部分，再用光把它「着」上去。

## 一、总规则（每张都要满足）

1. **同一个角色、同一个比例**：沿用 `assets/v2_0/` 的角色和 Q 版比例（为了变身过程连续，身体比例不变）。「不萌」靠这些表现：表情（眼神锐利、嘴角微扬或抿紧）、姿态（挺胸抬头、站得直、动作果断）、铠甲、披风、武器和发光的眼睛。
2. **画布**：1254×1254 PNG，真正的透明背景。基线 y≈1218，左右居中，和 2.0 一样。
3. **不要画特效背景**：不要画星环、光晕、背景光、粒子、地面、阴影，这些全部由代码画。铠甲本身可以有细细的发光纹路。
4. **图里不要有文字**。
5. **变身阶段图必须「倒着做」**（最重要）：
   1. 先画最终的全副铠甲 `xform_armor_7.png`。
   2. 然后在它上面**只去掉一个部件**（并补出部件下面原本的衣服），得到 `xform_armor_6.png`；以此类推，一直退到没有任何铠甲的 `xform_base.png`。
   3. 每一步除了被去掉的部件区域，其他像素必须逐像素一致：同一个姿势、同一个镜头、同一缕头发。
   这样代码才能准确找出每一步新增的是哪一块。
6. **同一个动作的多帧**和 2.0 一样：第 1 帧是完整新姿势，后面的帧只重绘动的部位。眨眼图 `<名称>_blink.png` 只改眼睛。
7. **文件位置**：`assets/v2_1/`。完成后更新 `docs/V2_1_ART_PREVIEW.png` 总览图，并在 `assets/v2_1/GENERATION.md` 记录生成方式。

### 铠甲设计（所有带铠甲的图都按这个画，保证一致）

> celestial star-armor: deep midnight-blue plates with polished gold filigree edges and ice-blue crystal inlays matching her hair ornament, a crescent-moon emblem on the breastplate, layered pauldrons with small gold wing flourishes, crystal-shard gauntlets, tasset plates over her original skirt, greaves with gold wing-like flourishes, a long midnight-blue cape whose lining is a starfield, a slender gold circlet with a crescent and ice crystals; weapon: a tall slender star-spear (gold shaft, crystal crescent blade, small gold tassels)

### 每张都用的风格前缀（英文，放在每条提示词最前面）

> Chibi anime girl, same character and same proportions as the reference images in assets/v2_0 (silver-lavender long wavy hair, ice-blue crystal hair ornament, dark navy-violet outfit with crescent-moon motif, dark thigh-high stockings), clean thick lineart, soft cel shading, cool and commanding rather than cute, confident sharp eyes, upright regal posture, full body, centered, transparent background, no text, no ground, no shadow, no background glow, no halo ring, sticker-like clarity readable at 160px,

## 二、清单和提示词

格式：**文件名 · 中文名**（帧数 · 是否要眨眼图）— 英文提示词（接在风格前缀后面）— 说明。

### A. 起身（从待机进入变身姿势，4 张）

- **`xform_rise_1..3` · 缓缓升起**（3 帧 · 不要眨眼图）
  > 1: standing like her normal idle pose but eyes closing calmly, hair starting to lift slightly; 2: rising onto her toes, arms beginning to open outward at her sides, eyes closed, hair lifting more; 3: floating just above the ground, arms open at about 30 degrees with palms facing forward, toes pointed down, hair and dress floating upward as if weightless, eyes still closed
  - 三帧是连续动作的中间画，姿势要一步一步过渡，不要跳。

- **`xform_base` · 变身姿势（无铠甲）**（1 张）
  > floating upright in the air, same pose as xform_rise_3, eyes now open and glowing ice-blue, a calm fierce expression, hair floating outward, original outfit only (no armor yet)
  - 这是所有铠甲阶段共用的底图。

### B. 着甲（7 张，倒着做，见总规则第 5 条）

每张的提示词 = `xform_base` 的描述 + 「已经穿上的部件」。新增顺序（由下往上，像铠甲从脚下长上来）：

| 文件 | 这一步新增 |
| --- | --- |
| `xform_armor_1.png` | 腿甲 greaves（含金色翼饰） |
| `xform_armor_2.png` | 腰甲 tasset plates |
| `xform_armor_3.png` | 护手 crystal-shard gauntlets |
| `xform_armor_4.png` | 胸甲 breastplate（月牙徽章） |
| `xform_armor_5.png` | 肩甲 pauldrons + 立领 |
| `xform_armor_6.png` | 星空披风 cape（在身后展开） |
| `xform_armor_7.png` | 头冠 circlet（最终全副铠甲，最先画这张） |

### C. 武器成形（2 张）

- **`xform_weapon_1` · 星枪显形**：在 `xform_armor_7` 上，右手前方出现一杆**半透明、由光线勾勒**的星枪轮廓，手指张开准备握住。
- **`xform_weapon_2` · 握枪**：同一姿势，右手握住实体星枪，枪身竖直。
  - 两张除了右手和枪，其余像素和 `xform_armor_7` 一致。

### D. MVP 展示（3 张，可以换姿势）

- **`mvp_1` · 横扫**
  > landing from the float, sweeping the star-spear outward to her side in a wide arc, cape flaring dramatically behind her, hair whipping, determined glare
- **`mvp_2` · 定格**
  > heroic final stance: spear planted upright beside her, other hand on her hip, chin raised, cape settling, a slight confident smirk, eyes glowing faintly
- **`mvp_3` · 回眸**（同 `mvp_2` 的姿势，只重绘头部）
  > same stance, head turned slightly toward the viewer, one eye narrowed in a confident wink-less glance

### E. 第二形态待机（游戏中的默认动作）

- **`form2_idle` · 持枪伫立**（4 帧 · 要眨眼图）
  > standing tall in full star-armor, spear held upright in one hand, cape flowing behind, calm composed commanding expression, weight on one leg
  - 帧：1 → 2 披风轻扬 → 3 头发轻飘 → 4 回到接近第 1 帧。

### F. 游戏中的动作（她在陪你打游戏）

- **`game_watch` · 观战**（3 帧 · 要眨眼图）
  > sitting sideways on an invisible seat, legs crossed, spear resting against her shoulder, chin on her fist, watching intently with sharp eyes
  - 帧：1 → 2 眼神往一边移 → 3 手指轻敲脸颊。
- **`game_tense` · 紧张**（2 帧 · 要眨眼图）
  > leaning forward gripping the spear with both hands, eyebrows drawn together, lips pressed tight, a small sweat drop
- **`game_cheer` · 给你打气**（2 帧 · 不要眨眼图）
  > one fist raised confidently, other hand holding the spear, a fierce grin, a small sparkle near her fist
- **`game_victory` · 胜利**（2 帧 · 不要眨眼图）
  > raising the star-spear high above her head in triumph, cape flaring, proud open-mouthed smile, small stars around the spear tip
- **`game_defeat` · 失利（不服气）**（2 帧 · 要眨眼图）
  > arms crossed with the spear tucked in the crook of one arm, looking away with a dignified annoyed frown, small "hmph" puff of air, still composed not crying
- **`game_drink` · 中场喝水**（2 帧 · 不要眨眼图）
  > sipping from an ornate gold goblet held in one hand, eyes closed calmly, spear leaning against her shoulder
- **`game_bored` · 转枪**（2 帧 · 要眨眼图）
  > twirling the spear casually in one hand above her head, half-lidded unimpressed eyes, waiting

## 三、数量

| 组 | 张数 |
| --- | --- |
| A 起身 + 底图 | 4 |
| B 着甲 | 7 |
| C 武器 | 2 |
| D MVP | 3 |
| E 第二形态待机 | 4 + 1 眨眼 |
| F 游戏动作 | 15 + 4 眨眼 |
| **合计** | **约 40 张** |

建议分两批：先交 A、B、C（变身是最难的部分，一致性要先验收），再交 D、E、F。
