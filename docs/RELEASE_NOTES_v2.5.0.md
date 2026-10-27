# Petoken v2.5.0

**English** · [中文](#中文)

## English

The Stardust Wardrobe: spend the stardust you earn on outfits, weapons and decorations she really wears, wish on falling stars, and a redrawn, lighter app.

### Added

- **Stardust Wardrobe** (right-click her › Stardust Wardrobe, or the tray menu): its own window with three pages.
  - **Closet**: a mirror where she tries on anything at once, owned or not, in a few poses and at the size you like. Pick a piece to wear or take it off, nudge its size and angle by hand, save whole looks and put them back on in one click.
  - **Shop**: 88 items in three sets — 8 outfits, 20 weapons, 60 decorations (head, back, ground, a floating buddy, task-star styles) — in five rarities: Stars 200, Moon 800, Sun 1800, Galaxy 4500 stardust; Starsea pieces only come from wishes. Four picks each day, each with a discount you draw from face-down cards (60–95 %), for that day. A few items are only on sale at certain times of year.
  - **Milestones**: the Meteor and Aurora rings and the Starsea form, unlocked by the stardust you have ever earned. Spending never takes them back.
- **Outfits she really wears**: every outfit has its own pictures for her actions; the Frost coat and the Starsea gown come in several tiers, each richer than the one below. Weapons sit in her hand and hide when her hands are out of sight; decorations follow her head, back and feet, and head and back pieces are put away while she lies down.
- **Wishes**: 300 stardust for one, 3000 for ten. Falling stars cross the night sky and you fly her to them with the mouse or the arrow keys to catch them; each rarity opens in its own colours, with tall result cards and sounds. Odds are shown in the window (Starsea 0.6 %, Galaxy 1.5 %, Sun 4 %, Moon 15 %, Stars 78.9 %); a Starsea piece within 60 wishes, at least one Moon piece in every ten, and 100 stardust back for a duplicate.
- **More ways to earn stardust**: a daily sign-in (+10, +50 for seven days in a row), three AI tasks in a day (+20), keeping your weekly goal (+30), completing a set in the collection book (+100); wearing a matching outfit, weapon and decoration lights a soft glow behind her. A heavy day of work still earns about 600 at most.
- **Every action in every form**: the night pajamas, the game armour and the Starsea form now have their own pictures for all 41 actions.

### Changed

- **The whole app is redrawn** in Qt Quick: the usage panel, the workbench, Settings, dialogs and the cards beside her share one calm, readable look with clear text, icons and empty-list hints.
- **Lighter and smoother**: about half the CPU while idle, pictures loaded only when first needed, the star ring drawn once and reused, 30 frames a second when nothing moves fast. The workbench opens in about a second and the wardrobe faster than before.
- Reports are read in their own background process, so the app stays responsive while it reads long Codex and Claude logs.

### Fixed

- No freeze when an AI task finishes: its file recap and the todo outcome are read in the background.
- Quitting while a report is being read no longer hangs.
- Her outfit no longer flickers between pictures while she is dragged.
- Decorations no longer float in the wrong place when she lies down or reads.
- Closing the wardrobe in the middle of a wish ends the wish show instead of leaving it running unseen.
- Only one Settings window and one focus dialog open at a time.
- Lists and scroll areas no longer flicker their scroll bar on and off at certain sizes.

### Install

Download `Petoken-Setup-v2.5.0.exe`, check it against `SHA256SUMS.txt`, and run it. Petoken 2.x updates itself when automatic updates are on.

## 中文

星辉衣柜来了：用工作攒下的星辉换服装、武器和装饰，真的穿在她身上；跟着流星许愿；整个程序换了新界面，也更轻快了。

### 新增

- **星辉衣柜**（在她身上右键 →「星辉衣柜」，托盘菜单里也有）：一个单独的窗口，分三页。
  - **衣柜**：一面镜子，点任何一件她马上试穿，没拥有的也能试；可以换几个姿势、调她的大小。穿上或卸下，手动调每件的大小和角度，把整套搭配存下来，一键换回。
  - **商店**：三类共 88 件：8 套服装、20 把武器、60 件装饰（头顶、身后、脚下、漂浮伙伴、任务星造型）；五种稀有度：繁星 200、明月 800、皓日 1800、银河 4500 星辉，星海级只能许愿获得。每天 4 件精选，每件可以翻牌抽一次折扣（6 折到 9.5 折），当天有效。少数商品只在一年中的特定时段出售。
  - **里程碑**：流星星环、极光星环和星海形态，由累计星辉解锁；花掉星辉不会让它们退回。
- **真的穿在她身上**：每套服装的每个动作都有自己的图；霜雪外套和星海礼服分好几个等级，越高越华丽。武器拿在她手上，看不到手的动作自动收起；装饰跟着她的头、背和脚，躺下时头饰和背饰会收起来。
- **许愿**：单抽 300 星辉，十连 3000。流星划过夜空，用鼠标或方向键带她飞过去摘下；每种稀有度有自己的开场颜色、高高的结果卡和音效。窗口里公示概率（星海 0.6%、银河 1.5%、皓日 4%、明月 15%、繁星 78.9%）；60 次内必得星海级，十连至少一件明月级，抽到重复返还 100 星辉。
- **更多得星辉的方式**：每日签到 +10（连续 7 天再 +50），一天完成 3 个 AI 任务 +20，守住每周目标 +30，图鉴集齐一类 +100；穿齐同一主题的服装、武器和装饰，她身后会亮起一圈柔光。重度工作一天最多还是约 600。
- **每种形态的每个动作**：深夜睡衣、游戏铠甲和星海形态的 41 个动作都有了自己的图。

### 改进

- **整个程序重新绘制**（Qt Quick）：用量面板、工作台、设置、对话框和她旁边的卡片统一成清爽好读的样式，文字清晰，空列表有提示。
- **更轻、更流畅**：待机时 CPU 占用约减半，图片用到时才加载，星环画一次反复用，画面平静时每秒 30 帧。工作台约 1 秒打开，衣柜也比以前快。
- 报告在单独的后台进程里读取，读很长的 Codex 和 Claude 记录时程序也不卡。

### 修复

- AI 任务完成时界面不再卡住：改了哪些文件和待办结果都在后台读取。
- 正在读报告时退出，不会再挂住。
- 拖动她时服装不再在两套图之间乱跳。
- 她躺下或看书时，装饰不再飘在错误的位置。
- 许愿动画播到一半关掉衣柜，动画会一起结束，不会在后台继续跑。
- 设置窗口和专注对话框同一时间只会开一个。
- 列表和滚动区在某些尺寸下滚动条不再反复闪现。

### 安装

下载 `Petoken-Setup-v2.5.0.exe`，用 `SHA256SUMS.txt` 核对后运行。打开自动更新的 Petoken 2.x 会自己更新。
