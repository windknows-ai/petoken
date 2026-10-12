# 形态补全 2/5：游戏形态（给 Codex）

分支 `codex/forms-game`，文件夹 `assets/v2_5/forms/game/`，总览图 `FORMS_GAME_PREVIEW.png`。

## 为什么要画

她现在的默认形态有 41 个动作，但游戏形态只画了其中几个，其余动作在这个形态下会变回默认衣服，或者只能用待机代替。用户希望每个形态都拥有默认形态的**全部**动作，只是换成这个形态的样子。

## 这个形态的样子

她打游戏时的第二形态（参考 `assets/v2_1/form2_idle_1.png` 等已有的游戏形态图）：同一套装甲、银色冰蓝靛色配色和剑。整体更利落、更有精神。

## 要画的动作（41 个，共 96 张）

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
