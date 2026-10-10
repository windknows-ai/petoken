"""The 2.3 videos: an overview, one video per new feature, and a vertical short.

Each script: header and file name, chapters, and scenes in the same shape as
tools/tutorial_script.py (``S``). Visuals: ('still', capture), ('pet', clip)
or ('live', recording) — see tools/tutorial_video.py. ``min`` keeps a scene
on screen long enough for its recording.

    python tools/tutorial_video.py OUT --ffmpeg PATH --script overview --language en
"""
from tools.tutorial_script import S as _S


def S(chapter, title, say, visual, steps=(), step=None, highlight=(), seconds=0):
    return dict(_S(chapter, title, say, visual, steps, step, highlight), min=seconds)


# Overview -------------------------------------------------------------------

OVERVIEW_ZH_CHAPTERS = (('intro', '认识她'), ('pet', '相处'), ('usage', '用量'), ('notify', '提醒'),
                        ('work', '派活和工作台'), ('focus', '专注'), ('game', '游戏模式'), ('phone', '手机'),
                        ('night', '深夜'), ('end', '最后'))
OVERVIEW_ZH = [
    S('intro', '嗨，我是 Petoken！',
      '我是住在你桌面上的 AI 编程小伙伴：帮你盯着 Claude Code 和 Codex 在忙什么、额度还剩多少，'
      '干完活喊你，需要你拍板也喊你。', ('pet', 'idle')),
    S('intro', '这一集：全部过一遍',
      '这一集带你快速看完我会的所有事：从看用量、提醒审批，到新加的游戏模式、手机通知和深夜睡衣。'
      '想细看哪一块，还有单独的介绍视频。', ('pet', 'greet_morning')),
    S('pet', '戳一戳、摸摸头',
      '左键戳我，头上来回划是摸头，按住我是撒娇，拖一下就能换位置。左键只陪我玩，不会弹出任何窗口。',
      ('pet', 'headpat')),
    S('pet', '右键：所有入口',
      '右键点我：用量面板、快速派活、专注、工作台、报告和设置都在这；「显示」里还能切换游戏模式和深夜模式。',
      ('still', 'menu')),
    S('usage', '星环和用量卡片',
      '有任务在跑，我身边就亮起星环，一颗星一个任务：蓝色是 Codex，金色是 Claude Code。'
      '头顶的卡片显示五小时和一周额度还剩多少，快用完会变红。', ('still', 'ring')),
    S('usage', '完整数字',
      '右键勾选「用量面板」，tokens、缓存命中、上下文和每个额度的完整数字都在这里。', ('still', 'panel')),
    S('notify', '干完活喊你',
      '任务完成我会欢呼，出错或者额度快没了我会难过，同时弹出 Windows 通知，先写任务名，再写项目。',
      ('pet', 'notify')),
    S('notify', '在我旁边批准',
      'Claude Code 想跑命令、改文件，我旁边会弹出卡片：允许、以后都允许或者拒绝，不用切回终端。',
      ('still', 'approval')),
    S('work', '一句话派活',
      '按 Alt + Shift + 空格，写一句要做什么，选好文件夹和 AI，点开始就开工。', ('still', 'quick_launch')),
    S('work', '工作台',
      '工作台里有待办、便签和项目。待办可以直接「交给 AI」，做完先变成「等你验收」，你看过再打勾。',
      ('still', 'wb_home')),
    S('work', '报告',
      '「报告」告诉你 AI 帮你干了多少：任务数、AI 工作时长、改过的文件、tokens 和等价费用。'
      '几个任务同时跑，时间只算一次。', ('still', 'report_board')),
    S('focus', '一起专注',
      '右键「开始专注」，我安静地陪你看书，只有要紧事才打扰你；时间到了告诉你这一轮做完了什么，再喊你起来休息。',
      ('pet', 'cheer')),
    S('game', '游戏模式：变身！',
      '打开全屏游戏，我会自动进入游戏模式：起身，星环飞到身后，铠甲一片片成形，亮剑登场！',
      ('live', 'transform'), seconds=15),
    S('game', '不挡你打游戏',
      '游戏里我待在一边，用小圆环显示额度、CPU 和显卡；鼠标在游戏上会直接穿过我，通知也只悄悄记下。',
      ('live', 'game_rings')),
    S('phone', '离开电脑也知道',
      '在设置的「手机」页打开推送，用 ntfy App 订阅频道。你离开电脑、专注或者打游戏时，'
      '任务完成、出错和等你审批都会推到手机上。', ('still', 'phone_mock')),
    S('night', '深夜换上睡衣',
      '到了深夜，我会犯困，换上月夜睡衣，抱起月亮枕头。AI 干活时我盖着被子看书陪着，你走开一会儿我就睡着。',
      ('pet', 'night_on'), seconds=9),
    S('night', '作息小助手',
      '「作息」页还有久坐提醒：连续用电脑太久，我伸个懒腰喊你起来走走。'
      '打开「记录使用时长」，报告里能看到每个程序用了多久，只存在这台电脑上。', ('still', 'settings_rest')),
    S('end', '就这些啦！',
      '所有数据都只留在你自己的电脑上。想细看某个功能，就看看单独的介绍视频吧。下载地址在简介里，今天也一起加油！',
      ('pet', 'heart')),
]

OVERVIEW_EN_CHAPTERS = (('intro', 'Hello'), ('pet', 'Play'), ('usage', 'Usage'), ('notify', 'Alerts'),
                        ('work', 'Work'), ('focus', 'Focus'), ('game', 'Game'), ('phone', 'Phone'),
                        ('night', 'Night'), ('end', 'Bye'))
OVERVIEW_EN = [
    S('intro', "Hi, I'm Petoken!",
      'I live on your desktop and keep an eye on Claude Code and Codex: what they are doing, how much of your '
      'limits is left, and I call you when they finish or need a decision.', ('pet', 'idle')),
    S('intro', 'Everything in one go',
      'This video runs through everything I can do, from usage and approvals to the new game mode, phone '
      'notifications and my late-night pajamas. Each new feature also has its own video.', ('pet', 'greet_morning')),
    S('pet', 'Poke me, pat my head',
      'Click to poke me, stroke my head to pat it, hold me down and I act cute, drag me anywhere. A left click '
      'only plays with me; it never opens a window.', ('pet', 'headpat')),
    S('pet', 'Right-click: everything',
      'Right-click me for the usage panel, quick launch, focus, the workbench, reports and settings; Show also '
      'switches game mode and late-night mode.', ('still', 'menu')),
    S('usage', 'Star ring and usage card',
      'When tasks run, a ring of stars lights up around me, one star per task: blue for Codex, gold for Claude '
      'Code. The card above my head shows what is left of your 5-hour and weekly limits, red when nearly gone.',
      ('still', 'ring')),
    S('usage', 'All the numbers',
      'Tick Usage panel in my menu for the full numbers: tokens, cache hits, context and every limit.',
      ('still', 'panel')),
    S('notify', 'I call you when it is done',
      'When a task finishes I cheer; errors or low limits make me sad, and a Windows notice pops up with the task '
      'name first, then the project.', ('pet', 'notify')),
    S('notify', 'Approve right beside me',
      'When Claude Code wants to run a command or edit a file, a card pops up beside me: allow, always allow or '
      'deny, without going back to the terminal.', ('still', 'approval')),
    S('work', 'Launch work in one line',
      'Press Alt + Shift + Space, type what you want, pick a folder and an AI, and start.',
      ('still', 'quick_launch')),
    S('work', 'The workbench',
      'The workbench holds your todos, notes and projects. Hand a todo to an AI; when it is done it waits for '
      'your review before it is ticked off.', ('still', 'wb_home')),
    S('work', 'Reports',
      'Reports show how much AI did for you: tasks, AI working time, files changed, tokens and the API-equivalent '
      'cost. Tasks running at the same time count their time once.', ('still', 'report_board')),
    S('focus', 'Focus together',
      'Pick Start focus and I read quietly beside you, interrupting only for what matters; at the end I sum up '
      'the round and send you off for a break.', ('pet', 'cheer')),
    S('game', 'Game mode: transform!',
      'Start a fullscreen game and I switch to game mode by myself: I rise, the ring flies behind me, my armour '
      'forms piece by piece, and out comes the sword!', ('live', 'transform'), seconds=15),
    S('game', 'Never in your way',
      'In a game I stay at the side with small rings for your limits, CPU and GPU; the mouse passes straight '
      'through me, and notices are only recorded.', ('live', 'game_rings')),
    S('phone', 'Away from your desk',
      'Turn on phone notifications in Settings and subscribe with the ntfy app. While you are away, focusing or '
      'gaming, finished tasks, errors and approvals reach your phone.', ('still', 'phone_mock')),
    S('night', 'Pajamas at night',
      'Late at night I get sleepy, change into my moon pajamas and hug my moon pillow. I read under my blanket '
      'while an AI works, and fall asleep when you step away.', ('pet', 'night_on'), seconds=9),
    S('night', 'A little rest helper',
      'The Rest page also has a sitting reminder: after too long at the computer I stretch and tell you to get '
      'up. Turn on Record app time to see how long each program was in front, kept on this computer.',
      ('still', 'settings_rest')),
    S('end', "That's all!",
      'Your data never leaves your computer. Watch the feature videos for the details. The download link is in '
      'the description. Let us have a good day!', ('pet', 'heart')),
]

# Game mode ------------------------------------------------------------------

GAME_ZH_CHAPTERS = (('start', '进入'), ('form', '变身'), ('display', '用量显示'), ('play', '不打扰'), ('end', '设置'))
GAME_ZH_STEPS = ('自动进入', '变身和第二形态', '小圆环和信息条', '不挡你、不抢焦点', '大小和退出')
GAME_ZH = [
    S('start', '游戏模式', '打游戏的时候，我也想陪着你，又不能挡着你。这就是游戏模式：我换上第二形态，安安静静待在一边。',
      ('pet', 'game_poses'), GAME_ZH_STEPS, None),
    S('start', '自动进入',
      '全屏游戏在前台几秒，我就自动进入；退出游戏自动恢复，切出去一小会儿不会退出。'
      '识别错了？在「游戏模式」设置里加白名单或黑名单，直接选程序文件就行。',
      ('still', 'settings_game'), GAME_ZH_STEPS, 0, ('game_auto',)),
    S('start', '手动切换', '不想等？右键我，在「显示」里点「游戏模式」，马上进入或者退出。',
      ('still', 'menu_view'), GAME_ZH_STEPS, 0, ('game',)),
    S('form', '变身！',
      '进入时我会起身，星环飞到身后，铠甲一片片成形，最后亮剑，在聚光灯下登场。嫌慢的话可以打开两倍速。',
      ('live', 'transform'), GAME_ZH_STEPS, 1, seconds=15),
    S('form', '第二形态', '游戏里我有一套新动作：认真观战、紧张、欢呼、喝水，还有胜利和失败的样子。',
      ('pet', 'game_poses'), GAME_ZH_STEPS, 1),
    S('display', '小圆环',
      '默认是几个小圆环，显示两个额度、CPU 和显卡；身后的星环还在，一颗星还是一个任务。',
      ('live', 'game_rings'), GAME_ZH_STEPS, 2),
    S('display', '横向信息条',
      '也可以换成横向信息条：额度、CPU、显卡、温度、显存、内存自己挑，还能拖到屏幕任意位置。',
      ('live', 'game_bar'), GAME_ZH_STEPS, 2),
    S('play', '鼠标直接穿过我',
      '鼠标在游戏画面上会直接穿过我，只有移到我或信息条上，才能右键或拖动。我也不会抢游戏的焦点；'
      '通知只悄悄记下，等你打完再看。', ('pet', 'game_watch'), GAME_ZH_STEPS, 3),
    S('end', '大小分开设', '游戏模式的大小和平时分开设，切换时我会慢慢变过去，人还在原来的位置。',
      ('still', 'settings_game'), GAME_ZH_STEPS, 4, ('game_scale',)),
    S('end', '打完了', '退出游戏，铠甲一片片褪去，星环慢慢变回原来的样子，我又回到平常的模样。玩得开心！',
      ('live', 'game_leave'), GAME_ZH_STEPS, 4, seconds=11),
]

GAME_EN_CHAPTERS = (('start', 'Start'), ('form', 'Transform'), ('display', 'Display'), ('play', 'Quiet'),
                    ('end', 'Settings'))
GAME_EN_STEPS = ('Starts by itself', 'Transformation', 'Rings and bar', 'Never in the way', 'Size and leaving')
GAME_EN = [
    S('start', 'Game mode', 'When you play I want to keep you company without getting in the way. That is game '
      'mode: I take my second form and stay quietly at the side.', ('pet', 'game_poses'), GAME_EN_STEPS, None),
    S('start', 'It starts by itself',
      'A fullscreen game in front for a few seconds turns game mode on; leaving the game turns it off, and a quick '
      'alt-tab does not. Wrong guess? Add the program to the allow or block list in the Game mode settings.',
      ('still', 'settings_game'), GAME_EN_STEPS, 0, ('game_auto',)),
    S('start', 'Or switch it yourself', 'Right-click me and pick Game mode under Show to switch it right away.',
      ('still', 'menu_view'), GAME_EN_STEPS, 0, ('game',)),
    S('form', 'Transform!',
      'I rise, the ring flies behind me, my armour forms piece by piece, then the sword and a spotlight. Too slow? '
      'Turn on double speed.', ('live', 'transform'), GAME_EN_STEPS, 1, seconds=15),
    S('form', 'My second form', 'In a game I have new poses: watching closely, tense, cheering, a drink, and how I '
      'look when you win or lose.', ('pet', 'game_poses'), GAME_EN_STEPS, 1),
    S('display', 'Small rings', 'By default small rings show your two limits, CPU and GPU; the star ring stays '
      'behind me, still one star per task.', ('live', 'game_rings'), GAME_EN_STEPS, 2),
    S('display', 'The info bar', 'Or use a bar: pick limits, CPU, GPU, temperature, video memory and RAM, and drag '
      'it anywhere on the screen.', ('live', 'game_bar'), GAME_EN_STEPS, 2),
    S('play', 'The mouse goes through me',
      'Over the game the mouse passes straight through me; move onto me or the bar to right-click or drag. I never '
      'take the focus from your game, and notices wait until you are done.', ('pet', 'game_watch'),
      GAME_EN_STEPS, 3),
    S('end', 'Its own size', 'Game mode has its own size; I grow or shrink smoothly when it switches and stay '
      'where I am.', ('still', 'settings_game'), GAME_EN_STEPS, 4, ('game_scale',)),
    S('end', 'Game over', 'When you leave the game the armour comes off piece by piece and the ring turns back. '
      'Have fun!', ('live', 'game_leave'), GAME_EN_STEPS, 4, seconds=11),
]

# Late night and rest --------------------------------------------------------

NIGHT_ZH_CHAPTERS = (('night', '深夜模式'), ('poses', '睡衣动作'), ('rest', '久坐提醒'), ('time', '使用时长'))
NIGHT_ZH_STEPS = ('换上睡衣', '什么时候算深夜', '睡衣动作', '睡着和醒来', '久坐提醒', '使用时长')
NIGHT_ZH = [
    S('night', '月夜睡衣', '熬夜写代码？我陪你。到了深夜，我会换上月夜睡衣，抱着月亮枕头。',
      ('pet', 'night_idle'), NIGHT_ZH_STEPS, None),
    S('night', '换装', '深夜开始时，我先犯困，换上睡裤和睡衣，散开头发戴上小月亮发夹，再抱起枕头；早上醒来再一步步换回去。',
      ('pet', 'night_on'), NIGHT_ZH_STEPS, 0, seconds=9),
    S('night', '什么时候算深夜',
      '在设置的「作息」页设好深夜时间，默认是晚上十一点到早上七点；开着免打扰时也能换上睡衣。右键「显示」里还能临时开关。',
      ('still', 'settings_rest'), NIGHT_ZH_STEPS, 1, ('night',)),
    S('poses', '睡衣动作',
      '深夜里我所有的动作都是睡衣版：AI 干活时盖着被子看书陪你，有好消息就挥手说晚安，困了打哈欠，还会捧一杯热牛奶。',
      ('pet', 'night_poses'), NIGHT_ZH_STEPS, 2),
    S('poses', '睡着和醒来',
      '整台电脑六分钟没有键盘鼠标操作，我就抱着枕头睡着；你一动鼠标，我就揉着眼睛醒过来。',
      ('pet', 'night_sleep'), NIGHT_ZH_STEPS, 3),
    S('poses', '图鉴里都有', '每个睡衣动作什么时候出现，工作台「图鉴」的深夜一组都写着，点「看看」我马上演给你看。',
      ('still', 'guide_night'), NIGHT_ZH_STEPS, 2),
    S('rest', '久坐提醒',
      '连续用电脑一小时，中间没离开过五分钟，我就伸个懒腰，提醒你站起来走走、喝口水。'
      '时间可以选三十到九十分钟，专注和游戏时不打扰。', ('pet', 'sit'), NIGHT_ZH_STEPS, 4),
    S('time', '使用时长',
      '在「报告」的「使用时长」里开始记录，就能看到今天、本周每个程序在前台用了多久。'
      '只记程序名和时间，只存在这台电脑上，离开电脑两分钟就不算。', ('still', 'report_app_time'), NIGHT_ZH_STEPS, 5),
    S('time', '晚安', '今天也辛苦啦，早点休息，晚安！', ('pet', 'night_goodnight'), NIGHT_ZH_STEPS, None),
]

NIGHT_EN_CHAPTERS = (('night', 'Late night'), ('poses', 'Pajama poses'), ('rest', 'Sitting'), ('time', 'App time'))
NIGHT_EN_STEPS = ('Into pajamas', 'When it is night', 'Pajama poses', 'Sleep and wake', 'Sitting reminder',
                  'App time')
NIGHT_EN = [
    S('night', 'Moon pajamas', 'Coding late? I will stay up with you. Late at night I change into my moon pajamas '
      'and hug my moon pillow.', ('pet', 'night_idle'), NIGHT_EN_STEPS, None),
    S('night', 'Changing', 'When the night begins I get sleepy, change into pajama trousers and top, let my hair '
      'down with a little moon clip and pick up my pillow; in the morning I change back step by step.',
      ('pet', 'night_on'), NIGHT_EN_STEPS, 0, seconds=9),
    S('night', 'When is it night?', 'Set the hours on the Rest page in Settings, 11 pm to 7 am by default; I can '
      'wear pajamas during Do Not Disturb too. Show in my menu switches it for now.',
      ('still', 'settings_rest'), NIGHT_EN_STEPS, 1, ('night',)),
    S('poses', 'Pajama poses', 'At night every pose is a pajama one: I read under my blanket while an AI works, '
      'wave good night for good news, yawn, and sip warm milk.', ('pet', 'night_poses'), NIGHT_EN_STEPS, 2),
    S('poses', 'Asleep and awake', 'Six minutes without keyboard or mouse on the computer and I fall asleep on my '
      'pillow; move the mouse and I wake up rubbing my eyes.', ('pet', 'night_sleep'), NIGHT_EN_STEPS, 3),
    S('poses', 'All in the Guide', 'The Late night group in the workbench Guide says when each pose appears; press '
      'Show me and I act it out.', ('still', 'guide_night'), NIGHT_EN_STEPS, 2),
    S('rest', 'Sitting reminder', 'After an hour at the computer without a five-minute break I stretch and remind '
      'you to stand up and have some water. Choose 30 to 90 minutes; never while focusing or gaming.',
      ('pet', 'sit'), NIGHT_EN_STEPS, 4),
    S('time', 'App time', 'Start recording under Reports, App time, to see how long each program was in front '
      'today or this week. Only names and times, kept on this computer; nothing counts after two minutes away.',
      ('still', 'report_app_time'), NIGHT_EN_STEPS, 5),
    S('time', 'Good night', 'Well done today. Get some rest. Good night!', ('pet', 'night_goodnight'),
      NIGHT_EN_STEPS, None),
]

# Phone notifications --------------------------------------------------------

PHONE_ZH_CHAPTERS = (('why', '为什么'), ('setup', '三步设置'), ('when', '什么时候推'))
PHONE_ZH_STEPS = ('打开推送', '订阅频道', '发一条试试', '什么时候推', '推哪些')
PHONE_ZH = [
    S('why', '离开电脑也知道',
      '让 AI 跑个大任务，自己去倒杯水、开个会，回来才发现它早就在等你批准？打开手机推送，我直接告诉你的手机。',
      ('pet', 'notify'), PHONE_ZH_STEPS, None),
    S('setup', '第一步：打开推送', '右键我选「设置」，打开「手机」页，勾上「推送到手机」。',
      ('still', 'settings_phone'), PHONE_ZH_STEPS, 0, ('push_enabled',)),
    S('setup', '第二步：订阅频道',
      '在手机上装免费的 ntfy App，点加号订阅，把这里的频道名复制过去。频道名是随机生成的，别人猜不到；想换一个就点「换一个」。',
      ('still', 'settings_phone'), PHONE_ZH_STEPS, 1, ('push_subscribe',)),
    S('setup', '第三步：试一下', '点「发一条试试」，手机响了就说明连上了。',
      ('still', 'settings_phone'), PHONE_ZH_STEPS, 2, ('push_test',)),
    S('when', '什么时候推',
      '默认只在你离开电脑五分钟以上、专注或者打游戏时推送，坐在电脑前就不打扰手机；免打扰时一条都不发。也可以选一直推送。',
      ('still', 'settings_phone'), PHONE_ZH_STEPS, 3, ('push_when',)),
    S('when', '推哪些',
      '推哪些自己挑：完成、出错、等你审批、额度快用完和你自己的提醒。通知里先写任务名，项目名也可以不发。',
      ('still', 'phone_mock'), PHONE_ZH_STEPS, 4),
    S('when', '就这么简单', '这样就算不在电脑前，也不会错过 AI 的消息啦！', ('pet', 'heart'), PHONE_ZH_STEPS, None),
]

PHONE_EN_CHAPTERS = (('why', 'Why'), ('setup', 'Set up'), ('when', 'When'))
PHONE_EN_STEPS = ('Turn it on', 'Subscribe', 'Send a test', 'When it sends', 'What it sends')
PHONE_EN = [
    S('why', 'Away from your desk', 'Start a big task, grab a coffee or join a meeting, and come back to find it '
      'waited ages for your approval? Turn on phone notifications and I tell your phone.', ('pet', 'notify'),
      PHONE_EN_STEPS, None),
    S('setup', 'Step 1: turn it on', 'Right-click me, open Settings, go to the Phone page and tick Send to phone.',
      ('still', 'settings_phone'), PHONE_EN_STEPS, 0, ('push_enabled',)),
    S('setup', 'Step 2: subscribe', 'Install the free ntfy app on your phone, tap plus to subscribe and paste the '
      'topic name from here. It is random, so nobody can guess it; press New to change it.',
      ('still', 'settings_phone'), PHONE_EN_STEPS, 1, ('push_subscribe',)),
    S('setup', 'Step 3: test it', 'Press Send a test; when your phone buzzes, you are connected.',
      ('still', 'settings_phone'), PHONE_EN_STEPS, 2, ('push_test',)),
    S('when', 'When it sends', 'By default only while you are away for five minutes or more, focusing or gaming, '
      'so your phone stays quiet while you sit at the computer; nothing during Do Not Disturb. Or send always.',
      ('still', 'settings_phone'), PHONE_EN_STEPS, 3, ('push_when',)),
    S('when', 'What it sends', 'Pick what to send: finished, failed, waiting for approval, limits running low and '
      'your own reminders. Notices name the task first; project names can be left out.',
      ('still', 'phone_mock'), PHONE_EN_STEPS, 4),
    S('when', 'That is it', 'Now you never miss what your AI is up to, even away from your desk!', ('pet', 'heart'),
      PHONE_EN_STEPS, None),
]

# Vertical short ---------------------------------------------------------------

SHORT_ZH = [
    S('all', '你的 AI 编程小伙伴', '我住在你的桌面上，帮你盯着 Claude Code 和 Codex！', ('pet', 'idle')),
    S('all', '一颗星 = 一个任务', '任务在跑，星环就亮；额度还剩多少，头顶看得见。', ('still', 'ring')),
    S('all', '活干完就喊你', '干完欢呼，出错难过，要你批准就在旁边点一下。', ('pet', 'notify')),
    S('all', '打游戏？变身！', '全屏游戏一开，我自动变身第二形态，安静陪你打。', ('live', 'transform'), seconds=13),
    S('all', '离开电脑也不错过', '你不在的时候，消息直接推到手机。', ('still', 'phone_mock')),
    S('all', '深夜换上睡衣', '熬夜我也陪着你，换上睡衣抱着枕头。', ('pet', 'night_on'), seconds=8),
    S('all', 'Petoken · 免费开源', '下载地址见简介，快来领养我吧！', ('pet', 'heart')),
]

SHORT_EN = [
    S('all', 'Your AI coding buddy', 'I live on your desktop and keep an eye on Claude Code and Codex!',
      ('pet', 'idle')),
    S('all', 'One star = one task', 'Stars light up while tasks run; your limits sit right above my head.',
      ('still', 'ring')),
    S('all', 'I call you when it is done', 'I cheer when it is done, frown at errors, and you approve right beside '
      'me.', ('pet', 'notify')),
    S('all', 'Gaming? Transform!', 'Start a fullscreen game and I switch to my second form and keep quiet.',
      ('live', 'transform'), seconds=13),
    S('all', 'Away? Check your phone', 'When you are away, the news goes straight to your phone.',
      ('still', 'phone_mock')),
    S('all', 'Pajamas at night', 'Up late? I stay with you in my pajamas, hugging my pillow.', ('pet', 'night_on'),
      seconds=8),
    S('all', 'Petoken · free and open source', 'The download link is in the description. Adopt me!',
      ('pet', 'heart')),
]

SCRIPTS = {
    'overview': dict(
        zh_CN=dict(header='Petoken 2.3 总览', out='Petoken-2.3-总览.mp4', chapters=OVERVIEW_ZH_CHAPTERS,
                   scenes=OVERVIEW_ZH),
        en=dict(header='Petoken 2.3 Overview', out='Petoken-2.3-Overview.mp4', chapters=OVERVIEW_EN_CHAPTERS,
                scenes=OVERVIEW_EN)),
    'game': dict(
        zh_CN=dict(header='Petoken · 游戏模式', out='Petoken-游戏模式.mp4', chapters=GAME_ZH_CHAPTERS,
                   scenes=GAME_ZH),
        en=dict(header='Petoken · Game mode', out='Petoken-Game-mode.mp4', chapters=GAME_EN_CHAPTERS,
                scenes=GAME_EN)),
    'night': dict(
        zh_CN=dict(header='Petoken · 深夜与作息', out='Petoken-深夜与作息.mp4', chapters=NIGHT_ZH_CHAPTERS,
                   scenes=NIGHT_ZH),
        en=dict(header='Petoken · Late night and rest', out='Petoken-Late-night-and-rest.mp4',
                chapters=NIGHT_EN_CHAPTERS, scenes=NIGHT_EN)),
    'phone': dict(
        zh_CN=dict(header='Petoken · 手机通知', out='Petoken-手机通知.mp4', chapters=PHONE_ZH_CHAPTERS,
                   scenes=PHONE_ZH),
        en=dict(header='Petoken · Phone notifications', out='Petoken-Phone-notifications.mp4',
                chapters=PHONE_EN_CHAPTERS, scenes=PHONE_EN)),
    'short': dict(
        zh_CN=dict(header='Petoken', out='Petoken-抖音竖屏.mp4', chapters=(('all', ''),), scenes=SHORT_ZH,
                   vertical=True),
        en=dict(header='Petoken', out='Petoken-Short.mp4', chapters=(('all', ''),), scenes=SHORT_EN,
                vertical=True)),
}
