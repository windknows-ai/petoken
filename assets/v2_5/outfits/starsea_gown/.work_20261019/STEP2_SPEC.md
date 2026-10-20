# 服装重画 5/5：星海长裙（给 Codex）

分支 `codex/outfits-starsea-gown`，文件夹 `assets/v2_5/outfits/starsea_gown/<品质>/`，总览图 `STARSEA_GOWN_PREVIEW.png`（5 个品质并排，同一个动作，方便对比）。

这套服装有 5 个品质：繁星（`fanxing`）、明月（`mingyue`）、皓日（`haori`）、银河（`yinhe`）、星海（`xinghai`）。每个品质一个子文件夹，文件名和现在一样。

## 第一步：重画现有的图，拉开品质差距

现在每个品质只有 10 个核心动作（共 22 张），而且几个品质看起来几乎一样。请先把这 22 张在每个品质里**重画**，按下表拉开差距：

| 品质 | 要明显看出的差别 |
| --- | --- |
| 繁星 | 最朴素：单层布料、冷蓝或灰蓝、几乎没有装饰，没有发光。轮廓简单。 |
| 明月 | 珍珠银滚边，一两处小饰品（胸针、发卡），布料多一层，轮廓稍微变化。 |
| 皓日 | 香槟金刺绣和金属扣件，加一件明显的部件（短披风、宽袖或飘带），配色更暖更亮。 |
| 银河 | 铂金加深蓝，布料上有流动的星空图案，加长下摆或第二层轻纱，轻微发光。 |
| 星海 | 最华丽：幻彩极光色的布料，大幅飘带或光翼一样的披帛，头上加小冠或星环，身边有星光粒子。一眼就能认出是最稀有的。 |

**关键：** 不同品质之间要做到**缩到小图标那么小也一眼能分出来**：靠轮廓（多了披风、下摆变长、出现飘带或光翼）和亮度、配色区分，不能只改一点颜色或花纹。现在几档几乎一样，这是这次要解决的主要问题。

现有的 22 张文件名就是文件夹里现在的那些（`idle_1` … `wave_2`、`idle_blink`、`sad_blink` 等），覆盖原文件即可（只有这一步允许覆盖这几个文件夹里的旧图）。**第一步做完先单独提交一次**，告诉我提交号，我先接上看效果。

## 第二步：补全全部动作

再把默认形态的 41 个动作补全（下表；已经在第一步画过的跳过）。每个品质都要补。

| 动作 | 要画的文件（PNG） | 默认形态的原图（照着它的姿势、位置画；这些文件都在仓库里） |
| --- | --- | --- |
| 待机 | `idle_1`、`idle_blink` | `assets/v1_1/idle.png`、`assets/v2_0/idle_blink.png` |
| 跟着敲键盘 | `typing_1`、`typing_2` | `assets/v1_1/typing_1.png`、`assets/v1_1/typing_2.png` |
| 盯着屏幕 | `codex_working_1` | `assets/v1_1/working.png` |
| 说话 | `microphone_1` | `assets/v1_1/microphone.png` |
| 听歌 | `music_1` | `assets/v1_1/music.png` |
| 弹吉他 | `guitar_1` | `assets/v1_1/guitar.png` |
| 欢呼 | `celebrate_1` | `assets/v1_1/celebrate.png` |
| 难过 | `sad_1` | `assets/v1_1/sad.png` |
| 挥手提醒 | `wave_1` | `assets/v1_1/wave.png` |
| 撒娇 | `coquettish_1`、`coquettish_2`、`coquettish_3`、`coquettish_4`、`coquettish_blink` | `assets/v2_0/coquettish_1.png`、`assets/v2_0/coquettish_2.png`、`assets/v2_0/coquettish_3.png`、`assets/v2_0/coquettish_4.png`、`assets/v2_0/coquettish_blink.png` |
| 被摸头 | `headpat_happy_1`、`headpat_happy_2`、`headpat_happy_3`、`headpat_happy_4`、`headpat_happy_blink` | `assets/v2_0/headpat_happy_1.png`、`assets/v2_0/headpat_happy_2.png`、`assets/v2_0/headpat_happy_3.png`、`assets/v2_0/headpat_happy_4.png`、`assets/v2_0/headpat_happy_blink.png` |
| 趴着睡 | `sleep_1`、`sleep_2`、`sleep_3` | `assets/v2_0/sleep_1.png`、`assets/v2_0/sleep_2.png`、`assets/v2_0/sleep_3.png` |
| 无聊趴着 | `bored_1`、`bored_2`、`bored_3`、`bored_blink` | `assets/v2_0/bored_1.png`、`assets/v2_0/bored_2.png`、`assets/v2_0/bored_3.png`、`assets/v2_0/bored_blink.png` |
| 打哈欠 | `yawn_1`、`yawn_2`、`yawn_3` | `assets/v2_0/yawn_1.png`、`assets/v2_0/yawn_2.png`、`assets/v2_0/yawn_3.png` |
| 醒来伸懒腰 | `wake_stretch_1`、`wake_stretch_2` | `assets/v2_0/wake_stretch_1.png`、`assets/v2_0/wake_stretch_2.png` |
| 好奇凑近 | `curious_1`、`curious_2`、`curious_blink` | `assets/v2_0/curious_1.png`、`assets/v2_0/curious_2.png`、`assets/v2_0/curious_blink.png` |
| 盘腿思考 | `thinking_1`、`thinking_2`、`thinking_blink` | `assets/v2_0/thinking_1.png`、`assets/v2_0/thinking_2.png`、`assets/v2_0/thinking_blink.png` |
| 害羞捂脸 | `shy_1`、`shy_2` | `assets/v2_0/shy_1.png`、`assets/v2_0/shy_2.png` |
| 鼓脸 | `pout_1`、`pout_2`、`pout_blink` | `assets/v2_0/pout_1.png`、`assets/v2_0/pout_2.png`、`assets/v2_0/pout_blink.png` |
| 被戳 | `poked_1` | `assets/v2_0/poked_1.png` |
| 被拎起来 | `dragged_1`、`dragged_2`、`dragged_3`、`dragged_4` | `assets/v2_0/dragged_1.png`、`assets/v2_0/dragged_2.png`、`assets/v2_0/dragged_3.png`、`assets/v2_0/dragged_4.png` |
| 落地 | `landing_1`、`landing_blink` | `assets/v2_0/landing_1.png`、`assets/v2_0/landing_blink.png` |
| 欢迎回来 | `hug_1`、`hug_2`、`hug_blink` | `assets/v2_0/hug_1.png`、`assets/v2_0/hug_2.png`、`assets/v2_0/hug_blink.png` |
| 比心 | `heart_1` | `assets/v2_0/heart_1.png` |
| 早安 | `greet_morning_1`、`greet_morning_2`、`greet_morning_blink` | `assets/v2_0/greet_morning_1.png`、`assets/v2_0/greet_morning_2.png`、`assets/v2_0/greet_morning_blink.png` |
| 晚安 | `greet_night_1`、`greet_night_2` | `assets/v2_0/greet_night_1.png`、`assets/v2_0/greet_night_2.png` |
| 吓一跳 | `surprised_1` | `assets/v2_0/surprised_1.png` |
| 点赞 | `thumbs_up_1`、`thumbs_up_blink` | `assets/v2_0/thumbs_up_1.png`、`assets/v2_0/thumbs_up_blink.png` |
| 加油 | `cheer_1`、`cheer_2`、`cheer_blink` | `assets/v2_0/cheer_1.png`、`assets/v2_0/cheer_2.png`、`assets/v2_0/cheer_blink.png` |
| 鼓掌 | `clap_1`、`clap_2`、`clap_3`、`clap_blink` | `assets/v2_0/clap_1.png`、`assets/v2_0/clap_2.png`、`assets/v2_0/clap_3.png`、`assets/v2_0/clap_blink.png` |
| 躲着偷看你 | `peek_1`、`peek_2` | `assets/v2_0/peek_1.png`、`assets/v2_0/peek_2.png` |
| 委屈 | `grievance_1`、`grievance_2` | `assets/v2_0/grievance_1.png`、`assets/v2_0/grievance_2.png` |
| 陪你看书 | `focus_read_1`、`focus_read_2`、`focus_read_3`、`focus_read_4`、`focus_read_blink` | `assets/v2_0/focus_read_1.png`、`assets/v2_0/focus_read_2.png`、`assets/v2_0/focus_read_3.png`、`assets/v2_0/focus_read_4.png`、`assets/v2_0/focus_read_blink.png` |
| 喝茶休息 | `focus_tea_1`、`focus_tea_2` | `assets/v2_0/focus_tea_1.png`、`assets/v2_0/focus_tea_2.png` |
| 专注完成 | `focus_done_1`、`focus_done_blink` | `assets/v2_0/focus_done_1.png`、`assets/v2_0/focus_done_blink.png` |
| 起来活动 | `stretch_break_1`、`stretch_break_2`、`stretch_break_blink` | `assets/v2_0/stretch_break_1.png`、`assets/v2_0/stretch_break_2.png`、`assets/v2_0/stretch_break_blink.png` |
| 举着卡片 | `hold_card_1`、`hold_card_blink` | `assets/v2_0/hold_card_1.png`、`assets/v2_0/hold_card_blink.png` |
| 收拾东西 | `packing_1`、`packing_blink` | `assets/v2_0/packing_1.png`、`assets/v2_0/packing_blink.png` |
| 出发 | `ready_go_1`、`ready_go_blink` | `assets/v2_0/ready_go_1.png`、`assets/v2_0/ready_go_blink.png` |
| 担心 | `worried_1`、`worried_2`、`worried_blink` | `assets/v2_0/worried_1.png`、`assets/v2_0/worried_2.png`、`assets/v2_0/worried_blink.png` |
| 得意 | `proud_1` | `assets/v2_0/proud_1.png` |

## 通用要求

- **画布和位置：** 每张 1254×1254，RGBA 真透明背景。她在画面里的位置、大小、脚的落点、头的位置，和右栏的默认形态原图**完全一致**（照着原图描姿势），这样头饰、武器、翅膀等装饰才能贴在同一个地方。
- **动作：** 每个动作的意思和默认形态一样（例如「被摸头」就是开心地被摸头），只是换成这套形态的衣服、配色和小道具；可以按这套形态的性格稍微改表现方式，但不要换成另一个动作。
- **帧：** 同一个动作的几帧是连续的小动画（呼吸、眨眼、手部小动作），帧之间只做小变化，不要跳。`_blink` 是这一动作的闭眼版（只把眼睛闭上，其他完全一样）。
- **文字：** 图里不要有任何文字。
- **交付：** 只新增指定文件夹里的文件，不改代码、不改已有图片；附一张总览图（文件名见上）；在自己的分支本地提交，不要推送，做完告诉我提交号。程序已经写好：文件一放进去就会自动用上，缺的动作暂时沿用以前的样子。
