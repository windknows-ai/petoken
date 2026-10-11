"""Shots for the 2.3 motion videos (tools/motion_video.py): only what is new since 2.0.

A shot: kind, what she says (the voice-over, also the karaoke subtitle), a
headline, and kind-specific fields:

    pose    clip (tools/tutorial_video.CLIPS), labels popping in around her
    live    a live recording (tutorial_video.LIVES), offset into it, labels
    still   a capture, the mark to zoom to, a step number
    phone   the lock screen with notices dropping in
    list    items flying in
    outro   the closing title
"""


def shot(kind, say, title='', **extra):
    return dict(kind=kind, say=say, title=title, **extra)


# Overview: what is new since 2.0 -------------------------------------------------

NEW_ZH = [
    shot('pose', '好久不见！从 2.0 到现在，我又学会了好多新本事，一起来看看吧！', '2.0 之后的新本事',
         clip='heart', tag='Petoken 2.3'),
    shot('list', '这次有四个大更新：游戏模式、手机通知、深夜睡衣，还有作息小助手！', '四个大更新',
         items=('游戏模式', '手机通知', '深夜睡衣', '作息小助手')),
    shot('live', '先看最酷的！打开全屏游戏，我会自动变身：星环飞到身后，铠甲一片片成形，亮剑登场！', '游戏模式',
         name='transform', min=15, labels=('自动进入', '变身！')),
    shot('live', '游戏里我安静待在一边，小圆环帮你盯着额度和显卡，鼠标直接穿过我，绝不抢焦点。', '不挡你打游戏',
         name='game_rings', labels=('额度', 'CPU · 显卡', '鼠标穿透')),
    shot('phone', '离开电脑也不怕错过！打开手机通知，任务完成、出错、等你批准，都会推到你的手机上。', '手机通知'),
    shot('pose', '熬夜写代码？到了深夜，我会换上月夜睡衣，抱着月亮枕头陪你。', '深夜睡衣', clip='night_on', min=8),
    shot('pose', 'AI 干活的时候，我就盖着被子看书；有好消息，我就挥手说晚安。', '睡衣版动作', clip='night_poses',
         labels=('看书陪你', '晚安', '打哈欠', '热牛奶')),
    shot('pose', '坐太久了，我会伸个懒腰，喊你起来走走、喝口水。', '久坐提醒', clip='sit'),
    shot('still', '还能记录每个程序用了多久，数据只留在你自己的电脑上。', '使用时长', name='report_app_time', mark='list'),
    shot('list', '还有一堆小改进：通知先告诉你是哪个任务，AI 工作时长算得更准，菜单也重新整理过了。', '还有这些',
         items=('通知先写任务名', '工作时长更准', '菜单更好找', '设置分页更清楚')),
    shot('outro', '想看每个功能的细节，就看看单独的介绍视频吧。下载地址在简介里，快去更新吧！', 'Petoken 2.3',
         sub='免费开源 · GitHub 搜 petoken', clip='heart'),
]

NEW_EN = [
    shot('pose', "Long time no see! Since 2.0 I've learned a bunch of new tricks. Let me show you!",
         'New since 2.0', clip='heart', tag='Petoken 2.3'),
    shot('list', 'Four big updates: game mode, phone notifications, late-night pajamas, and a little rest helper!',
         'Four big updates', items=('Game mode', 'Phone notices', 'Night pajamas', 'Rest helper')),
    shot('live', 'The coolest first! Start a fullscreen game and I transform: the ring flies behind me, armour '
         'forms piece by piece, and out comes the sword!', 'Game mode', name='transform', min=15,
         labels=('Starts by itself', 'Transform!')),
    shot('live', 'In the game I stay quietly at the side. Small rings watch your limits and GPU, and the mouse goes '
         'right through me.', 'Never in your way', name='game_rings', labels=('Limits', 'CPU · GPU', 'Click-through')),
    shot('phone', 'Away from your desk? Turn on phone notifications: finished tasks, errors and approvals go straight '
         'to your phone.', 'Phone notifications'),
    shot('pose', 'Coding late? At night I change into my moon pajamas and hug my moon pillow.', 'Night pajamas',
         clip='night_on', min=8),
    shot('pose', 'While an AI works I read under my blanket, and for good news I wave good night.', 'Pajama poses',
         clip='night_poses', labels=('Reading', 'Good night', 'Yawn', 'Warm milk')),
    shot('pose', 'Sitting too long? I stretch and tell you to get up and grab some water.', 'Sitting reminder',
         clip='sit'),
    shot('still', 'I can also record how long you spend in each program, kept only on your computer.', 'App time',
         name='report_app_time', mark='list'),
    shot('list', 'Plus lots of small fixes: notices name the task first, AI working time is more accurate, and the '
         'menus are tidier.', 'And more', items=('Task names first', 'Accurate AI time', 'Tidier menus',
                                                  'Clearer settings')),
    shot('outro', 'Watch the feature videos for the details. The download link is in the description. Go update!',
         'Petoken 2.3', sub='Free & open source · github.com/windknows-ai/petoken', clip='heart'),
]

# Game mode ----------------------------------------------------------------------

GAME_ZH = [
    shot('pose', '打游戏的时候，我也想陪着你，但绝不挡着你。这就是游戏模式！', '游戏模式', clip='game_poses',
         tag='Petoken'),
    shot('still', '全屏游戏在前台几秒，我就自动进入；退出游戏自动恢复。认错了？加个白名单或黑名单就好。', '自动进入',
         name='settings_game', mark='game_auto'),
    shot('live', '进入的时候，我会起身，星环飞到身后，铠甲一片片成形，最后亮剑，在聚光灯下登场！', '变身！',
         name='transform', min=15),
    shot('pose', '游戏里我是第二形态：认真观战、紧张、欢呼、喝口水，赢了输了都有反应。', '第二形态', clip='game_poses',
         labels=('观战', '紧张', '欢呼', '胜利')),
    shot('live', '额度、CPU、显卡，用小圆环一眼就能看到；身后的星环还在，一颗星还是一个任务。', '小圆环',
         name='game_rings', labels=('5 小时额度', '一周额度', 'CPU · 显卡')),
    shot('live', '喜欢横条？换成信息条，想看什么自己挑，还能拖到屏幕任意位置。', '信息条', name='game_bar'),
    shot('pose', '鼠标在游戏上会直接穿过我，我也不会抢焦点；通知都悄悄记下，等你打完再看。', '绝不打扰',
         clip='game_watch', labels=('鼠标穿透', '不抢焦点', '通知静音')),
    shot('live', '打完退出，铠甲褪去，星环变回原样。玩得开心！', '打完收工', name='game_leave', min=10),
]

GAME_EN = [
    shot('pose', "When you play, I want to keep you company without ever getting in your way. That's game mode!",
         'Game mode', clip='game_poses', tag='Petoken'),
    shot('still', 'A fullscreen game in front for a few seconds and I switch on by myself; leave the game and I '
         'switch back. Wrong guess? Use the allow or block list.', 'Starts by itself', name='settings_game',
         mark='game_auto'),
    shot('live', 'I rise, the ring flies behind me, my armour forms piece by piece, then the sword and the '
         'spotlight!', 'Transform!', name='transform', min=15),
    shot('pose', 'In a game I take my second form: watching, tense, cheering, a quick drink, and I react when you '
         'win or lose.', 'Second form', clip='game_poses', labels=('Watching', 'Tense', 'Cheer', 'Victory')),
    shot('live', 'Limits, CPU and GPU in small rings at a glance; the star ring stays behind me, one star per task.',
         'Small rings', name='game_rings', labels=('5-hour limit', 'Weekly limit', 'CPU · GPU')),
    shot('live', 'Prefer a bar? Pick what it shows and drag it anywhere on the screen.', 'Info bar',
         name='game_bar'),
    shot('pose', 'The mouse goes straight through me, I never steal focus, and notices wait until you are done.',
         'Never in the way', clip='game_watch', labels=('Click-through', 'No focus stealing', 'Quiet notices')),
    shot('live', 'Game over? The armour comes off and the ring turns back. Have fun!', 'GG', name='game_leave',
         min=10),
]

# Late night and rest ---------------------------------------------------------------

NIGHT_ZH = [
    shot('pose', '熬夜写代码？别怕，我陪你！', '深夜与作息', clip='night_idle', tag='Petoken'),
    shot('pose', '到了深夜，我会犯困、换上睡衣、戴上小月亮发夹，再抱起月亮枕头。', '换上睡衣', clip='night_on', min=8),
    shot('still', '深夜几点开始，在设置的作息页自己定；开着免打扰的时候，也能换上睡衣。', '什么时候算深夜',
         name='settings_rest', mark='night'),
    shot('pose', '深夜里我的动作都是睡衣版：AI 干活时盖着被子看书，有好消息就挥手说晚安。', '睡衣版动作',
         clip='night_poses', labels=('看书陪你', '晚安', '打哈欠', '热牛奶')),
    shot('pose', '你六分钟不动，我就抱着枕头睡着；动一下鼠标，我就揉着眼睛醒过来。', '睡着又醒来', clip='night_sleep'),
    shot('pose', '坐太久了？我会伸个懒腰，提醒你站起来走走、喝口水。', '久坐提醒', clip='sit'),
    shot('still', '打开使用时长，就能看到每个程序用了多久，只存在你自己的电脑上。', '使用时长', name='report_app_time', mark='list'),
    shot('outro', '今天也辛苦啦，晚安！', '晚安', sub='Petoken · 深夜与作息', clip='night_goodnight'),
]

NIGHT_EN = [
    shot('pose', "Coding late? Don't worry, I'll stay up with you!", 'Late night & rest', clip='night_idle',
         tag='Petoken'),
    shot('pose', 'At night I get sleepy, change into my pajamas, put on a little moon clip and hug my moon pillow.',
         'Pajamas on', clip='night_on', min=8),
    shot('still', 'Choose when the night starts on the Rest page; I can wear pajamas during Do Not Disturb too.',
         'When is night?', name='settings_rest', mark='night'),
    shot('pose', 'At night every pose is a pajama one: I read under my blanket while an AI works, and wave good '
         'night for good news.', 'Pajama poses', clip='night_poses',
         labels=('Reading', 'Good night', 'Yawn', 'Warm milk')),
    shot('pose', 'Six minutes without the mouse and I fall asleep on my pillow; move it and I wake up rubbing my eyes.',
         'Asleep and awake', clip='night_sleep'),
    shot('pose', 'Sitting too long? I stretch and remind you to stand up and drink some water.', 'Sitting reminder',
         clip='sit'),
    shot('still', 'Turn on app time to see how long each program was in front, kept only on your computer.',
         'App time', name='report_app_time', mark='list'),
    shot('outro', 'Well done today. Good night!', 'Good night', sub='Petoken · Late night & rest',
         clip='night_goodnight'),
]

# Phone notifications ----------------------------------------------------------------

PHONE_ZH = [
    shot('pose', '让 AI 跑个大任务，自己去倒杯水？回来才发现，它早就在等你批准了！', '手机通知', clip='notify',
         tag='Petoken'),
    shot('phone', '打开手机通知，任务完成、出错、等你批准，我都会推到你的手机上。', '直接推到手机'),
    shot('still', '第一步，在设置的手机页，勾上推送到手机。', '第一步', name='settings_phone', mark='push_enabled', step=1),
    shot('still', '第二步，在手机上装 ntfy，订阅这里的频道名。', '第二步', name='settings_phone', mark='push_subscribe',
         step=2),
    shot('still', '第三步，点发一条试试，手机响了就成功啦！', '第三步', name='settings_phone', mark='push_test', step=3),
    shot('still', '默认只在你离开电脑、专注或者打游戏时才推，坐在电脑前就不打扰你。', '不打扰你', name='settings_phone',
         mark='push_when'),
    shot('outro', '这样就再也不会错过 AI 的消息啦！', '不再错过', sub='Petoken · 手机通知', clip='heart'),
]

PHONE_EN = [
    shot('pose', 'Start a big task, go grab a coffee, and come back to find it waited ages for your approval?',
         'Phone notifications', clip='notify', tag='Petoken'),
    shot('phone', 'Turn on phone notifications: finished tasks, errors and approvals go straight to your phone.',
         'Straight to your phone'),
    shot('still', 'Step one: on the Phone page in Settings, tick Send to phone.', 'Step 1', name='settings_phone',
         mark='push_enabled', step=1),
    shot('still', 'Step two: install ntfy on your phone and subscribe to this topic name.', 'Step 2',
         name='settings_phone', mark='push_subscribe', step=2),
    shot('still', 'Step three: press Send a test. When your phone buzzes, you are done!', 'Step 3',
         name='settings_phone', mark='push_test', step=3),
    shot('still', 'By default I only send while you are away, focusing or gaming, so your phone stays quiet at your '
         'desk.', 'Only when it helps', name='settings_phone', mark='push_when'),
    shot('outro', 'Now you never miss what your AI is up to!', 'Never miss a thing', sub='Petoken · Phone',
         clip='heart'),
]

# Vertical short -------------------------------------------------------------------------

SHORT_ZH = [
    shot('pose', '我是 Petoken，你的 AI 编程桌宠！', '我的桌宠会变身！', clip='idle'),
    shot('live', '一打游戏，我就自动变身！', '打游戏？变身！', name='transform', offset=3.0, min=9),
    shot('phone', '离开电脑？消息直接推到手机！', '消息推到手机'),
    shot('pose', '熬夜？我换上睡衣陪你！', '深夜换睡衣', clip='night_on', min=7),
    shot('outro', '免费开源，快来领养我吧！', 'Petoken', sub='GitHub 搜 petoken', clip='heart'),
]

SHORT_EN = [
    shot('pose', "I'm Petoken, your AI coding desktop pet!", 'My desktop pet transforms!', clip='idle'),
    shot('live', 'Start a game and I transform!', 'Gaming? Transform!', name='transform', offset=3.0, min=9),
    shot('phone', 'Away from your desk? News goes straight to your phone!', 'Straight to your phone'),
    shot('pose', 'Up late? I put on my pajamas and stay with you!', 'Pajamas at night', clip='night_on', min=7),
    shot('outro', 'Free and open source. Come adopt me!', 'Petoken', sub='github.com/windknows-ai/petoken',
         clip='heart'),
]

SCRIPTS = {
    'new': dict(zh_CN=dict(shots=NEW_ZH, out='Petoken-2.3-新功能总览.mp4', theme='brand'),
                en=dict(shots=NEW_EN, out='Petoken-2.3-Whats-new.mp4', theme='brand')),
    'game': dict(zh_CN=dict(shots=GAME_ZH, out='Petoken-游戏模式.mp4', theme='space'),
                 en=dict(shots=GAME_EN, out='Petoken-Game-mode.mp4', theme='space')),
    'night': dict(zh_CN=dict(shots=NIGHT_ZH, out='Petoken-深夜与作息.mp4', theme='night'),
                  en=dict(shots=NIGHT_EN, out='Petoken-Late-night-and-rest.mp4', theme='night')),
    'phone': dict(zh_CN=dict(shots=PHONE_ZH, out='Petoken-手机通知.mp4', theme='pink'),
                  en=dict(shots=PHONE_EN, out='Petoken-Phone-notifications.mp4', theme='pink')),
    'short': dict(zh_CN=dict(shots=SHORT_ZH, out='Petoken-抖音竖屏.mp4', theme='brand', vertical=True),
                  en=dict(shots=SHORT_EN, out='Petoken-Short.mp4', theme='brand', vertical=True)),
}

# The feature videos (1.0 – 2.4).
from tools.motion_scripts_features import FEATURE_SCRIPTS  # noqa: E402
SCRIPTS.update(FEATURE_SCRIPTS)
