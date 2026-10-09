# Petoken 2.3「月夜睡衣」夜间形态提示词（给 Codex 画图用）

2.3 新增「深夜模式」：晚上 11 点以后（或者打开免打扰的时段），她自动换上月夜睡衣，动作也变得慢、软、困。早上醒来（或你关掉深夜模式）再换回平常的衣服。

换衣服沿用游戏模式变身的做法：**不靠淡入淡出**，而是代码对比相邻两张阶段图，找出新增的那一块，用一层柔光把它「盖」上去（像被子慢慢裹上来），所以阶段图同样要「倒着做」。整体氛围和游戏模式相反：**柔和、放松、温暖**，不要发光的铠甲感。

## 一、总规则（每张都要满足）

1. **同一个角色、同一个比例**：沿用 `assets/v2_0/` 的 Q 版角色。表情柔和、困倦、安心。
2. **画布**：1254×1254 PNG，真正透明背景，基线 y≈1218，左右居中。
3. **不要画背景、地面、阴影、光晕**；可以画小道具（枕头、被子、杯子、月亮小挂件）。
4. **图里不要有文字**，可以有 Zzz、小月亮、小星星符号。
5. **换装阶段图倒着做**（和 2.1 着甲一样）：先画穿好睡衣的 `night_change_3`，再每次只去掉一个部分（并补出原来的衣服）得到 `night_change_2`、`night_change_1`，最后退回原来衣服的 `night_change_0`。每一步除了被换掉的区域，其余像素必须完全一致。
6. 同一动作的多帧只重绘动的部位；眨眼图 `<名称>_blink.png` 只改眼睛。
7. **文件位置**：`assets/v2_3/`。完成后更新 `docs/V2_3_ART_PREVIEW.png`，在 `assets/v2_3/GENERATION.md` 记录生成方式。

### 睡衣设计（所有夜间图都按这个画）

> soft pastel lavender pajamas: a loose long-sleeved top whose sleeves cover her hands, a tiny crescent-moon print, a satin ribbon at the collar, loose matching pants, fluffy socks; her hair loose and a little messy, no crystal hair ornament (a small moon hair clip instead); she hugs a round crescent-moon pillow

### 风格前缀（英文，放在每条提示词最前面）

> Chibi anime girl, same character and proportions as the reference images in assets/v2_0 (silver-lavender long wavy hair, soft violet eyes), clean thick lineart, soft cel shading, cozy bedtime mood, warm and relaxed, drowsy gentle expression, full body, centered, transparent background, no text, no ground, no shadow, no glow, sticker-like clarity readable at 128px,

## 二、清单

格式：**文件名 · 中文名**（帧数 · 是否要眨眼图）— 英文提示词 — 说明。

### A. 换装（4 张，倒着做）

| 文件 | 内容 |
|---|---|
| `night_change_0.png` | 和 `assets/v2_0/idle_1.png` 同一个坐着抱膝的姿势、原来的衣服，眼睛半闭开始犯困 |
| `night_change_1.png` | 下半身换成睡裤和毛绒袜 |
| `night_change_2.png` | 上衣换成长袖睡衣（袖子盖住手） |
| `night_change_3.png` | 头发散开、发饰换成小月亮发夹、怀里多出月亮抱枕（最终状态，最先画这张） |

### B. 夜间动作

- **`night_idle` · 抱着月亮枕头**（4 帧 · 要眨眼图）
  > sitting cross-legged hugging the crescent-moon pillow, chin resting on it, sleepy half-closed eyes, slow breathing
  - 帧：1 → 2 头轻轻一点 → 3 抱枕抱紧一点 → 4 回到接近第 1 帧。
- **`night_yawn` · 打哈欠**（2 帧 · 不要眨眼图）
  > one sleeve-covered hand over a big yawn, the other arm around the pillow, a tiny tear at the eye corner
- **`night_sleep` · 抱着枕头睡着**（3 帧 · 不要眨眼图）
  > curled up on her side hugging the moon pillow, eyes closed, small "Zzz" and a tiny moon above
  - 帧：1 吸气 → 2 呼气（Zzz 上飘）→ 3 翻个身蹭一下枕头。
- **`night_milk` · 喝热牛奶**（2 帧 · 不要眨眼图）
  > holding a warm mug of milk with both sleeve-covered hands, a little steam rising, eyes closed contentedly
- **`night_read` · 盖着被子看书**（2 帧 · 要眨眼图）
  > lying on her stomach under a small blanket, propped on elbows, reading a little picture book, legs kicking slowly
- **`night_goodnight` · 晚安**（2 帧 · 不要眨眼图）
  > waving a sleeve-covered hand goodnight, the other hugging the pillow, a soft sleepy smile, a small star beside her
- **`night_wake` · 早上醒来**（2 帧 · 不要眨眼图）
  > sitting up and rubbing one eye with a sleeve, hair messy, the pillow slipping from her lap, a little sparkle of morning

## 三、数量

| 组 | 张数 |
| --- | --- |
| A 换装 | 4 |
| B 夜间动作 | 17 + 2 眨眼 |
| **合计** | **约 23 张** |

建议先交 A 组和 `night_idle`，我先验收换装是否连贯，再画其余的。
