# Petoken 2.0 角色美术生成记录

## 当前状态

2026-10-06：**WAITING_FOR_HUMAN_ART_QA**。分支 `codex/v2.0-art`，基于 `9d96ee9`。用户已确认 `33e9fd9` 的五组全身样张，现已完成全部剩余 A/B/C/D：新增 **25 个动作、60 张 PNG**；已验收的 26 张原字节保留，当前合计 **86 张 PNG**。只提交本地美术分支，不合并、不推送、不修改共享代码。

以下“前批记录”保留其原始交付与验证证据；当前结果以文末“后续动作续绘”及 REMAINING_VALIDATION.json 为准。

## 前批记录（已验收）

已完整阅读 `D:/Documents/ChatGPT/petoken-claude/docs/V2_0_ART_PROMPTS.md`，按本轮重新画全身的要求执行。`idle.png` 只作为角色设定参考，不作为这五个首帧的合成底图。每个动作都单独生成全身，身体姿势分别为趴睡、双肘托腮趴卧、侧坐哈欠、抱枕后蹲藏、站立叉手跺脚；没有两个动作共用一个身体。

## 交付范围

- sleep：3 帧，**替换上批坐姿睡眠图**，无眨眼图。
- bored：3 帧 + bored_blink.png。
- yawn：3 帧，无眨眼图。
- peek：2 帧，按清单不画眨眼图。
- pout：2 帧 + pout_blink.png。
- 原 coquettish 四帧和眨眼、headpat_happy 四帧和眨眼、idle_blink 共 **11 张**保持字节不变。
- 当前 assets/v2_0/ 合计 26 张 PNG。总览 `docs/V2_0_ART_PREVIEW.png` 展示原始 idle、保留样张代表和本批全部 15 张，在 #D0CCE4 浅紫背景上同时给出大图和 128 px 小图。

## 工具与步骤

1. 角色绘制使用 OpenAI **内置 image_gen**：五个新全身首帧输入唯一角色参考 `assets/v1_1/idle.png`。不从 idle 裁切身体，不把 idle 的身体合回新动作。提示词保留银紫长卷发、冰蓝羽状水晶发饰、深蓝紫星月服装、深色四角星长袜、大头短身、黑蓝描边及柔和赛璐璐上色。
2. 用户已授权 Pillow 局部蒙版合成、透明边缘清理与对比图拼接。首帧先清理 alpha<=8 的微弱噪点和小于 20 像素孤立连通块，再等比例归一化到 1254×1254 透明画布：左右至少 40 px 安全边，最低 alpha 像素统一 y=1218。没有拉伸。原始 bbox、缩放系数和偏移都记录在 FULLPOSE_VALIDATION.json。
3. **只有同一动作后续帧及眨眼图**使用该动作完成的第 1 帧作编辑目标。由 image_gen 绘制运动部位，Pillow 将这些局部合回首帧；蒙版边缘 2 px 羽化。所有同组后续帧使用相同画布和基线，不对各帧单独缩放/居中。
4. 运动区覆盖新旧位置的并集及被遮住/重新露出的背景或头发；旧手臂移开时必须补出背后的发丝。蒙版外的 RGBA 像素直接复制首帧。眨眼区只包含眼部及相关眼皮线条，不改变手、身体、脚及嘴型。
5. 图内没有文字。sleep 提示词中的 Zzz 按全局“无文字”要求改成纯圆形呼吸泡；呼吸第 2 帧复用第一帧的气泡像素上移 8 px，不让生成器随机改变泡泡形状。
6. 睡眠脚尖向外摆的初稿越过安全边，已重做为向内轻晃；晃腿与哈欠局部蒙版曾切断移动轮廓，已扩展至完整运动范围；pout 眨眼的眼尾及眉眼细节已做一轮局部修正。最终重新查看总览和放大接缝。

首帧完整提示词、每张后续编辑的最终提示词和生成源文件路径保存在 **FULLPOSE_VALIDATION.json 的 generation**；每张实际蒙版、父图、羽化、差分范围和 SHA256 也在该文件。未使用额外 API 密钥或 fallback CLI，不修改 imagegen 工具脚本。

## 本批逐张生成方式与透明范围

alpha bbox 采用 Pillow `(left, top, right, bottom)`，右下边界不包含在范围内。所有图最低点为 y=1218，底部余量 35 px。

| 文件 | 非零 alpha bbox | 生成方式/帧动作 |
|---|---|---|
| sleep_1.png | (40, 287, 1214, 1219) | 全身重新生成；抱枕上趴睡，头靠叠手，双脚弯起，吸气背部略高。 |
| sleep_2.png | (40, 287, 1214, 1219) | 首帧局部编辑背部呼气；呼吸泡像素整体上移 8 px。 |
| sleep_3.png | (40, 287, 1214, 1219) | 首帧局部编辑最右侧小腿/脚尖向内轻晃，另一只脚和头部锁定。 |
| bored_1.png | (40, 180, 1214, 1219) | 全身重新生成；反向趴卧、双肘撑起、双手托腮，双腿向后交叉弯起。 |
| bored_2.png | (40, 180, 1214, 1219) | 首帧局部编辑两条交叉小腿，向左摆。 |
| bored_3.png | (40, 180, 1214, 1219) | 首帧局部编辑两条交叉小腿，向右摆。 |
| bored_blink.png | (40, 180, 1214, 1219) | 首帧局部编辑双眼闭合；脸型、嘴、双手及腿部不动。 |
| yawn_1.png | (103, 24, 1150, 1219) | 全身重新生成；双腿折向一侧坐着，一手抬起、一手捂住半张哈欠嘴。 |
| yawn_2.png | (103, 24, 1150, 1219) | 首帧局部编辑抬起手臂进一步伸高，嘴张大。 |
| yawn_3.png | (103, 24, 1150, 1219) | 首帧局部编辑手臂放下一半，嘴合上；原先被手臂遮住的头发由生成图补齐。 |
| peek_1.png | (51, 24, 1203, 1219) | 全身重新生成；低蹲在大圆抱枕后，抱枕遮住身体和嘴，仅眼睛/头发/发饰及指尖露出。 |
| peek_2.png | (51, 15, 1203, 1219) | 首帧局部编辑抱枕上方露出的头部略抬起；抱枕主体下方固定。 |
| pout_1.png | (132, 24, 1122, 1219) | 全身重新生成；站立叉手鼓腮，左脚抬起准备跺脚，右脚站稳。 |
| pout_2.png | (132, 24, 1122, 1219) | 首帧局部编辑左腿落下、双脚站稳，脸颊更鼓。 |
| pout_blink.png | (132, 24, 1122, 1219) | 首帧局部编辑双眼闭合；鼓腮、叉手和抬脚姿势不动。 |

## 检查结果

- 15/15 PNG：1254×1254、RGBA，alpha 有 0 和 255，四角完全透明，无白底、棋盘格、地面或阴影块。
- 15/15：左右至少 40 px 安全边，基线 y=1218；与 idle 的 y=1221 相差 3 px，符合文件 y≈1218 的规范，没有任何单帧漂移。
- 10/10 后续帧及眨眼：相对对应首帧，蒙版之外 RGBA 差异像素数 **0**。运动区内都有差异，15 个最终 SHA256 均不同，不用重复文件凑帧数。
- 五个首帧两两 alpha 轮廓均不相同，10 对检查全部通过；同时人工按姿势复核身体轮廓确实不同。轮廓差分是辅助检测，不代替姿势视觉判断。
- 放大检查脚尖、交叉小腿、眼尾、跺脚双腿和哈欠手臂接缝；总览复核身份、配色、服装和 128 px 可读性。未测试程序内播放，因为本批只交付美术，不修改动画代码。
- 11 张上批保留 PNG 与 c2a4ed0 原始字节相同；原 idle SHA256 仍为 `b52b011cb3328dc1d8733bf4a33c1d81d26c200a84e56a358ee05f1025b757d1`。

## 记录和接入

- FULLPOSE_VALIDATION.json：本批 15 张完整提示词、父图、alpha 范围、归一化、蒙版及检查证据。
- VALIDATION.json：上批仍保留的 11 张检查记录；旧坐姿 sleep 三帧已移除，避免把旧哈希误当现行文件。
- GENERATION_PROMPTS.json：上批提示词历史，里面的坐姿 sleep 编辑指令已经被本批替代，不能用作当前睡眠规格。
- 本批作者原始输出/辅助脚本缓存：`C:/Users/fengz/.codex/generated_images/petoken-v2-fullpose-20261006/`。旧坐姿 sleep 及旧生成说明备份在其 `previous-sleep/` 子目录；也可从 c2a4ed0 恢复。最终 PNG 已全部落入仓库，运行不依赖缓存。
- 普通帧按各动作 1→2→3→1 或 1→2→1 播放；独立眨眼对应第 1 帧，应在第 1 帧时插入，避免手脚突然回到第 1 帧。任意相位眨眼需要运行时独立眼层或逐相位图，不属于本次接入范围。
- 前批后续：五组动作已由用户确认，其余 A/B/C/D 已在下面的续绘批次完成。
- 沿用 docs/ARTWORK.md 的既有美术归属说明；代码 MIT 不自动适用于角色身份/图片权利。本轮未修改该共享文档或任何共享代码。

## 后续动作续绘（2026-10-06）

- 已完成清单所有剩余 A/B/C/D：25 个独立全身首帧 + 21 个后续动作帧 + 14 个眨眼 = **60 张**。
- A 剩余 16 个动作 38 张；B 4 个动作 12 张；C 3 个动作 6 张；D 2 个动作 4 张。
- 内置 imagegen 绘制，唯一角色设定参考 assets/v1_1/idle.png。每个动作首帧重新画全身；后续帧只以本动作首帧为编辑目标。没有把 idle 当成新动作底图。
- 同组通过已授权的 Pillow 局部蒙版合成，2 px 边界羽化；运动区外 RGBA 逐像素保持一致。首帧统一居中/缩放/基线归一化一次，后续帧不再整体归一化。
- proud 提示词明确要求闭眼，按总规则“不为闭眼动作画眨眼”交付 proud_1.png；没有用重复图凑 proud_blink。greet_morning_blink 只关闭原先睁开的另一只眼。
- dragged 首稿与 poked 姿势太近，已重画为直立悬垂。curious_2 重画为反向歪头，手和膝保持原位。stretch_break_2 重画反向侧伸，头发/躯干/四肢为整体运动区，锁定脚底接触像素及画布基线，避免把静止小腿矩形强行拼到倾斜腿上造成接缝。
- landing、thumbs_up、heart、stretch_break、proud、ready_go 首帧的脚部另用 imagegen 局部修正，去除误画鞋带/鞋跟，恢复深色星纹长袜；所有依赖帧重新以修正首帧合成。原始脚部修正蒙版之外差异 0。
- 看书明确有翻页、低头读书和抬眼；问号/汗滴用原符号的像素平移，保持形状一致。早安挥手装饰线和出发眨眼眼尾接缝已在放大复核后修正。

### 完整验证结果

- 60/60 新图：1254×1254 真 RGBA PNG，alpha 有 0 和 255，四角透明；左右至少 40 px 安全边，最低点 y1218（bbox bottom1219）。
- 35/35 后续帧/眨眼：各自首帧蒙版之外的 RGBA 差异像素数 **0**；运动区内有差异，60 张 SHA256 均不同。
- 25 首帧 300 对 alpha 轮廓均不同；逐组查看全身姿势和小尺寸图，作为姿势视觉复核的辅助证据，不把哈希差异等同于设计审美验收。
- 26 张此前已验收 PNG 与 33e9fd9 字节完全一致；idle SHA256 保持不变，assets/v1_1/ 未修改。
- 各组逐帧放大检查手指、脚尖、腿部接缝、眼尾、翻页、热气、泪滴和汗滴；总览完成所有 86 张与 idle 对比。程序内动画播放仍由 Claude 接入后验证，本批只交付图像。
- 完整最终提示词、生成原图路径、每帧父图、蒙版/保护区、技术对齐参数、差分 bbox、alpha bbox 与 SHA256：REMAINING_VALIDATION.json。辅助脚本/原始生成输出保留在 `C:/Users/fengz/.codex/generated_images/petoken-v2-remaining-20261006/`，最终运行不依赖缓存。
- 总览：docs/V2_0_ART_PREVIEW.png，浅紫底 #D0CCE4，所有最终帧列出原文件名；图片本身无文字，名字仅在总览中。

### 逐张交付记录

alpha bbox 的 right/bottom 为不包含边界。完整提示词和精确运动蒙版见 REMAINING_VALIDATION.json。

| PNG | 非零 alpha bbox | 生成方式 |
|---|---|---|
| wake_stretch_1.png | (147, 40, 1106, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| wake_stretch_2.png | (147, 40, 1106, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 wake_stretch_1 |
| curious_1.png | (66, 24, 1188, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| curious_2.png | (67, 19, 1214, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 curious_1 |
| curious_blink.png | (66, 24, 1188, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 curious_1，其余区域锁定 |
| thinking_1.png | (93, 24, 1161, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| thinking_2.png | (93, 24, 1161, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 thinking_1 |
| thinking_blink.png | (93, 24, 1161, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 thinking_1，其余区域锁定 |
| shy_1.png | (170, 24, 1084, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| shy_2.png | (170, 24, 1084, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 shy_1 |
| poked_1.png | (84, 24, 1170, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| dragged_1.png | (153, 24, 1100, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| dragged_2.png | (153, 24, 1100, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 dragged_1 |
| dragged_3.png | (153, 24, 1100, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 dragged_1 |
| dragged_4.png | (153, 24, 1100, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 dragged_1 |
| landing_1.png | (40, 33, 1214, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化；imagegen 局部修正星纹长袜 |
| landing_blink.png | (40, 33, 1214, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 landing_1，其余区域锁定 |
| hug_1.png | (106, 24, 1148, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| hug_2.png | (105, 24, 1179, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 hug_1 |
| hug_blink.png | (106, 24, 1148, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 hug_1，其余区域锁定 |
| heart_1.png | (130, 24, 1123, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化；imagegen 局部修正星纹长袜 |
| greet_morning_1.png | (113, 24, 1140, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| greet_morning_2.png | (113, 24, 1140, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 greet_morning_1 |
| greet_morning_blink.png | (113, 24, 1140, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 greet_morning_1，其余区域锁定 |
| greet_night_1.png | (103, 24, 1150, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| greet_night_2.png | (103, 24, 1150, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 greet_night_1 |
| surprised_1.png | (70, 24, 1183, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| thumbs_up_1.png | (101, 24, 1152, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化；imagegen 局部修正星纹长袜 |
| thumbs_up_blink.png | (101, 24, 1152, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 thumbs_up_1，其余区域锁定 |
| cheer_1.png | (72, 24, 1182, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| cheer_2.png | (72, 24, 1182, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 cheer_1 |
| cheer_blink.png | (72, 24, 1182, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 cheer_1，其余区域锁定 |
| clap_1.png | (147, 24, 1107, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| clap_2.png | (147, 24, 1107, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 clap_1 |
| clap_3.png | (147, 24, 1107, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 clap_1 |
| clap_blink.png | (147, 24, 1107, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 clap_1，其余区域锁定 |
| grievance_1.png | (75, 24, 1179, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| grievance_2.png | (75, 24, 1179, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 grievance_1 |
| focus_read_1.png | (79, 24, 1174, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| focus_read_2.png | (79, 24, 1174, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 focus_read_1 |
| focus_read_3.png | (79, 24, 1174, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 focus_read_1 |
| focus_read_4.png | (79, 24, 1174, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 focus_read_1 |
| focus_read_blink.png | (79, 24, 1174, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 focus_read_1，其余区域锁定 |
| focus_tea_1.png | (92, 24, 1162, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| focus_tea_2.png | (92, 24, 1162, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 focus_tea_1 |
| focus_done_1.png | (138, 24, 1115, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| focus_done_blink.png | (138, 24, 1115, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 focus_done_1，其余区域锁定 |
| stretch_break_1.png | (123, 30, 1131, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化；imagegen 局部修正星纹长袜 |
| stretch_break_2.png | (128, 51, 1144, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 stretch_break_1 |
| stretch_break_blink.png | (123, 30, 1131, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 stretch_break_1，其余区域锁定 |
| hold_card_1.png | (120, 24, 1134, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| hold_card_blink.png | (120, 24, 1134, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 hold_card_1，其余区域锁定 |
| packing_1.png | (78, 24, 1176, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| packing_blink.png | (78, 24, 1176, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 packing_1，其余区域锁定 |
| ready_go_1.png | (106, 24, 1147, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化；imagegen 局部修正星纹长袜 |
| ready_go_blink.png | (106, 24, 1147, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 ready_go_1，其余区域锁定 |
| worried_1.png | (156, 24, 1098, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化 |
| worried_2.png | (156, 24, 1098, 1219) | imagegen 本动作首帧局部运动重绘；Pillow 合成到 worried_1 |
| worried_blink.png | (156, 24, 1098, 1219) | imagegen 只闭眼；Pillow 蒙版合成到 worried_1，其余区域锁定 |
| proud_1.png | (132, 24, 1121, 1219) | imagegen 全身新姿势；一次性尺寸/基线归一化；imagegen 局部修正星纹长袜 |

### 接入与下一步

- 下一步仅等待用户对本批美术验收；清单剩余图像已交齐，无尚未开始的动作。
- 各组帧顺序沿用 V2_0_ART_PROMPTS.md；独立 blink 与本动作第1帧匹配，需在第1帧相位插入。不同相位直接插入 blink 会让手脚回到第1帧；任意相位眨眼需要额外眼层/逐相位资产。
- 不改共享代码，不合并、不推送；本批美术尚未在桌宠程序内播放验收。图片权利继续沿用项目既有美术授权说明。
