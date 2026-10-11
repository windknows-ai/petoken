"""Shots for the feature videos (1.0 – 2.4): one video per feature group.

Same shot kinds as tools/motion_scripts.py, plus ``toast``: desktop notices
popping up in the corner while she reacts beside them.
"""


def shot(kind, say, title='', **extra):
    return dict(kind=kind, say=say, title=title, **extra)


# 1. Token analytics ----------------------------------------------------------------

TOKENS_ZH = [
    shot('pose', 'AI 写代码，到底用了多少 token、花了多少钱？我帮你算得清清楚楚！', 'Token 分析', clip='working',
         tag='Petoken'),
    shot('still', '右键我，打开用量面板：这次对话用了多少 token、上下文还剩多少，一眼就能看到。', '用量面板',
         name='panel'),
    shot('still', '再点进 Token 分析，按模型、按会话、按天细分，输入、缓存、输出、推理，分得明明白白。', '细到每一项',
         name='analytics'),
    shot('still', '费用按官方价格估算，美元、加元、欧元、人民币，随你选。', '费用估算', name='settings_tracking',
         mark='currency'),
    shot('still', '想只看当前项目，或者只看这一次对话？切一下范围就好。', '看哪一部分', name='settings_tracking',
         mark='scope'),
    shot('list', '所有数字都只在你的电脑上读取，不上传，也不会看你的对话内容。', '只在本地',
         items=('按模型', '按会话', '每天 / 7 天 / 30 天', '数据不上传')),
    shot('outro', '用得明白，花得放心。免费开源，GitHub 搜 petoken！', 'Token 分析', sub='Petoken · 免费开源',
         clip='heart'),
]
TOKENS_EN = [
    shot('pose', 'How many tokens did your AI really use, and what did it cost? I keep the count for you!',
         'Token analytics', clip='working', tag='Petoken'),
    shot('still', 'Right-click me and open the usage panel: tokens for this chat and how much context is left, at a '
         'glance.', 'Usage panel', name='panel'),
    shot('still', 'Token Analytics breaks it down by model, session and day: input, cache, output and reasoning.',
         'Every detail', name='analytics'),
    shot('still', 'Cost is estimated from official prices, in US, Canadian, euro or yuan.', 'Cost estimate',
         name='settings_tracking', mark='currency'),
    shot('still', 'Only this project, or only this chat? Just switch the scope.', 'Pick a scope',
         name='settings_tracking', mark='scope'),
    shot('list', 'Every number is read on your computer only. Nothing is uploaded, and your chats stay private.',
         'Local only', items=('By model', 'By session', 'Day / 7 / 30 days', 'Nothing uploaded')),
    shot('outro', 'Know what you use and what it costs. Free and open source: search petoken on GitHub!',
         'Token analytics', sub='Petoken · free & open source', clip='heart'),
]

# 2. The star ring --------------------------------------------------------------------

RING_ZH = [
    shot('live', '每交给 AI 一个任务，我身边就多一颗星星，绕着我转。', '一颗星一个任务', name='ring_live', crop=(.8, 1.0),
         labels=('任务 ①', '任务 ②', '任务 ③')),
    shot('live', '星环有前后层次：星星转到前面亮闪闪，绕到身后就藏到我后面。', '会转的星环', name='ring_live',
         crop=(.8, 1.0), offset=3.0),
    shot('still', '点一下星星，就能看这个任务的详情。', '点开看详情', name='ring_detail'),
    shot('pose', '任务再多也不乱：一页最多 8 颗，可以翻页，每个任务都找得到。', '任务再多也不乱', clip='working',
         labels=('最多 8 颗', '翻页', '编号不变')),
    shot('still', '不想要星环？在设置里随时关掉。', '可以关掉', name='settings_general', mark='star_ring'),
    shot('outro', '看一眼星环，就知道 AI 在忙什么！', '星环', sub='Petoken · 免费开源', clip='heart'),
]
RING_EN = [
    shot('live', 'Every task you give an AI becomes a star circling around me.', 'One star per task',
         name='ring_live', crop=(.8, 1.0), labels=('Task ①', 'Task ②', 'Task ③')),
    shot('live', 'The ring has depth: stars shine in front, then slip behind me as they go round.',
         'A ring that turns', name='ring_live', crop=(.8, 1.0), offset=3.0),
    shot('still', 'Click a star to see that task in detail.', 'Click for details', name='ring_detail'),
    shot('pose', 'Lots of tasks? Up to 8 stars per page, with pages to flip, so every task is easy to find.',
         'Never a mess', clip='working', labels=('8 per page', 'Pages', 'Stable numbers')),
    shot('still', "Don't want the ring? Turn it off in Settings any time.", 'Your choice', name='settings_general',
         mark='star_ring'),
    shot('outro', 'One look at the ring and you know what your AIs are up to!', 'The star ring',
         sub='Petoken · free & open source', clip='heart'),
]

# 3. Claude Code and Codex ------------------------------------------------------------

DUAL_ZH = [
    shot('pose', 'Claude Code 和 Codex 一起用？没问题，我两个都认识！', 'Claude Code + Codex', clip='idle',
         tag='Petoken'),
    shot('live', '金色的星星是 Claude Code 的任务，蓝色的是 Codex 的，一眼就能分开。', '金色和蓝色',
         name='ring_live', crop=(.8, 1.0), labels=('金色 Claude', '蓝色 Codex')),
    shot('still', '头顶的用量卡同时显示两边的 5 小时和每周额度，还有重置倒计时。', '两边的额度', name='card'),
    shot('still', '跟踪哪个？自动、只看 Codex、只看 Claude Code，随你选。', '跟踪哪个', name='settings_tracking',
         mark='tracking'),
    shot('still', 'Claude 订阅的 5 小时和每周额度，打开同步就能读到。', '同步 Claude 额度', name='settings_claude',
         mark='claude_sync'),
    shot('outro', '两个 AI，一个桌宠，全都照顾到！', '双 AI 支持', sub='Petoken · 免费开源', clip='heart'),
]
DUAL_EN = [
    shot('pose', 'Using Claude Code and Codex together? No problem, I know them both!', 'Claude Code + Codex',
         clip='idle', tag='Petoken'),
    shot('live', 'Gold stars are Claude Code tasks, blue ones are Codex: you can tell them apart at a glance.',
         'Gold and blue', name='ring_live', crop=(.8, 1.0), labels=('Gold: Claude', 'Blue: Codex')),
    shot('still', 'The usage card over my head shows both 5-hour and weekly limits, with reset countdowns.',
         'Both limits', name='card'),
    shot('still', 'Track both automatically, or only Codex, or only Claude Code.', 'What to track',
         name='settings_tracking', mark='tracking'),
    shot('still', 'Turn on sync to read your Claude plan\'s 5-hour and weekly limits too.', 'Claude limits',
         name='settings_claude', mark='claude_sync'),
    shot('outro', 'Two AIs, one desktop pet, all looked after!', 'Two AIs', sub='Petoken · free & open source',
         clip='heart'),
]

# 4. The workbench --------------------------------------------------------------------

WORKBENCH_ZH = [
    shot('pose', '我还有一个小工作台：项目、待办、便签，全都放在这里。', '工作台', clip='project', tag='Petoken'),
    shot('still', '打开工作台，主页先给你一个总览。', '主页', name='wb_home'),
    shot('still', '项目页把 Claude 和 Codex 的任务按项目归好类。', '项目', name='wb_projects'),
    shot('still', '待办随手记，做完打个勾。', '待办', name='wb_todos'),
    shot('still', '便签用来记想法、记进度，下次接着来。', '便签', name='wb_notes'),
    shot('list', '所有东西都只存在你自己的电脑上。', '都在本地', items=('项目', '待办', '便签', '只存在本地')),
    shot('outro', '写代码的小事，交给工作台！', '工作台', sub='Petoken · 免费开源', clip='heart'),
]
WORKBENCH_EN = [
    shot('pose', 'I also have a little workbench: projects, todos and notes, all in one place.', 'The workbench',
         clip='project', tag='Petoken'),
    shot('still', 'Open it and the home page gives you an overview first.', 'Home', name='wb_home'),
    shot('still', 'The projects page groups Claude and Codex tasks by project.', 'Projects', name='wb_projects'),
    shot('still', 'Jot down todos and tick them off when they are done.', 'Todos', name='wb_todos'),
    shot('still', 'Notes keep your ideas and progress for next time.', 'Notes', name='wb_notes'),
    shot('list', 'Everything stays on your own computer.', 'All local',
         items=('Projects', 'Todos', 'Notes', 'Saved locally')),
    shot('outro', 'Leave the small stuff to the workbench!', 'The workbench', sub='Petoken · free & open source',
         clip='heart'),
]

# 5. Notifications (1.5) ----------------------------------------------------------------

NOTIFY_ZH = [
    shot('toast', '任务做完、出错、等你确认，我都会第一时间告诉你！', 'AI 的消息', clip='notify', tag='Petoken'),
    shot('pose', '做完了我会欢呼，出错了会难过，等你批准就挥手叫你。', '她会有反应', clip='notify',
         labels=('完成！', '点赞', '出错了')),
    shot('still', '打开 Claude 即时通知，一秒之内就能收到。', '一秒就到', name='settings_claude', mark='claude_notify'),
    shot('still', '所有通知都存在通知中心，保留 30 天，还能按类型筛选。', '通知中心', name='wb_notify'),
    shot('still', '也能加自己的提醒：单次、每天、每周都行，还能关联一个待办。', '个人提醒', name='wb_notify'),
    shot('still', '需要专心的时候开免打扰，也可以定时，比如晚上 10 点到早上 8 点。', '免打扰',
         name='settings_assistant', mark='dnd_scheduled'),
    shot('outro', '再也不用盯着终端等 AI 了！', '通知', sub='Petoken · 免费开源', clip='heart'),
]
NOTIFY_EN = [
    shot('toast', 'Finished, failed, or waiting for your OK: I tell you the moment it happens!', 'AI news',
         clip='notify', tag='Petoken'),
    shot('pose', 'I cheer when it is done, look sad when it fails, and wave when it needs your approval.',
         'She reacts', clip='notify', labels=('Done!', 'Thumbs up', 'It failed')),
    shot('still', 'Turn on Claude instant notifications and they arrive within a second.', 'Within a second',
         name='settings_claude', mark='claude_notify'),
    shot('still', 'Every notice is kept in Notifications for 30 days, with filters by type.', 'Notification centre',
         name='wb_notify'),
    shot('still', 'Add your own reminders too: once, daily or weekly, even linked to a todo.', 'Reminders',
         name='wb_notify'),
    shot('still', 'Need to focus? Turn on Do Not Disturb, or schedule it, say 10 pm to 8 am.', 'Do Not Disturb',
         name='settings_assistant', mark='dnd_scheduled'),
    shot('outro', 'No more staring at the terminal waiting for your AI!', 'Notifications',
         sub='Petoken · free & open source', clip='heart'),
]

# 6. Time-saving assistant (1.6) ----------------------------------------------------------

ASSIST_ZH = [
    shot('pose', '我不只陪着你，还能帮你省时间！', '省时小助手', clip='thinking', tag='Petoken'),
    shot('list', '我会按你现在的速度，算出额度什么时候用完；快不够了就建议你换另一个；上下文快满、任务卡住 20 分钟，也会提醒你。',
         '额度预测', items=('额度什么时候用完', '换到还有余量的', '上下文快满了', '20 分钟没进展')),
    shot('still', 'Claude 要权限的时候，直接在我旁边点允许，不用切回窗口。', '在桌宠上批准', name='approval'),
    shot('still', '它问你选择题，也能直接在这里回答。', '回答问题', name='question'),
    shot('still', '它写好的方案，接受，或者附一句修改意见，都在这里。', '确认方案', name='plan'),
    shot('toast', '任务做完的通知里有小结：改了几个文件、用了多久、花了多少钱，点一下就跳回那个窗口。', '完成小结',
         clip='review'),
    shot('still', '按 Alt+Shift+Space，随时开一个 Claude Code 或 Codex，选好模型和推理强度就开工。', '快速启动',
         name='quick_launch'),
    shot('outro', '少切窗口，多写代码！', '省时小助手', sub='Petoken · 免费开源', clip='heart'),
]
ASSIST_EN = [
    shot('pose', "I don't just keep you company. I save you time too!", 'Time saver', clip='thinking',
         tag='Petoken'),
    shot('list', 'At your current pace I work out when a limit runs out, suggest switching to the one with room, and '
         'warn you when context is almost full or a task is stuck for 20 minutes.', 'Limit forecasts',
         items=('When limits run out', 'Switch to one with room', 'Context almost full', 'No progress in 20 min')),
    shot('still', 'When Claude asks for permission, allow it right beside me, no window switching.',
         'Approve on the pet', name='approval'),
    shot('still', 'Its multiple-choice questions can be answered here too.', 'Answer questions', name='question'),
    shot('still', 'And its plans: accept, or send it back with a note.', 'Confirm plans', name='plan'),
    shot('toast', 'Finished-task notices include a recap: files changed, time taken and cost. Click to jump back to '
         'that window.', 'Recaps', clip='review'),
    shot('still', 'Press Alt+Shift+Space to start Claude Code or Codex any time, with your model and effort.',
         'Quick launch', name='quick_launch'),
    shot('outro', 'Less window switching, more coding!', 'Time saver', sub='Petoken · free & open source',
         clip='heart'),
]

# 7. Reports ------------------------------------------------------------------------------

REPORTS_ZH = [
    shot('pose', '这周 AI 帮你干了多少活？看报告就知道！', '报告', clip='proud', tag='Petoken'),
    shot('still', '数据面板：任务数、AI 工作时长、改了多少文件、用了多少 token 和钱，还会跟上一期比一比。', '数据面板',
         name='report_board'),
    shot('still', '分析页用折线图看变化：今天每小时、这一周、30 天、12 周都行。', '折线图', name='report_analysis'),
    shot('list', '看得见的进步，最有成就感。', '一目了然', items=('今天 / 本周', '和上一期比', '折线图', '只在本地')),
    shot('outro', '看看 AI 这周有多努力吧！', '报告', sub='Petoken · 免费开源', clip='heart'),
]
REPORTS_EN = [
    shot('pose', 'How much did your AIs get done this week? The reports tell you!', 'Reports', clip='proud',
         tag='Petoken'),
    shot('still', 'The data board: tasks, AI working time, files changed, tokens and cost, compared with the last '
         'period.', 'Data board', name='report_board'),
    shot('still', 'Analysis shows it as line charts: today by the hour, this week, 30 days or 12 weeks.',
         'Line charts', name='report_analysis'),
    shot('list', 'Progress you can see feels the best.', 'At a glance',
         items=('Today / this week', 'Versus last period', 'Line charts', 'Local only')),
    shot('outro', "See how hard your AIs worked this week!", 'Reports', sub='Petoken · free & open source',
         clip='heart'),
]

# 8. Give a todo to AI (1.7) ----------------------------------------------------------------

TODO_AI_ZH = [
    shot('pose', '待办太多做不完？交给 AI 去做吧！', '把待办交给 AI', clip='working', tag='Petoken'),
    shot('still', '在待办上点「交给 AI」。', '第一步', name='wb_todos', mark='todo_ai', step=1),
    shot('still', '选 Claude Code 还是 Codex、在哪个文件夹、用什么模型；马上做，或者定个时间。', '第二步',
         name='give_ai', step=2),
    shot('still', '做完了先给你验收：满意就通过，不满意写一句意见，让它重做。', '验收', name='review'),
    shot('list', '做完会自动打勾，还会写一份小结便签；错过了定好的时间，可以提醒你或者直接补做。', '贴心的细节',
         items=('马上做或定时', '做完自动打勾', '自动写小结', '错过可补做')),
    shot('outro', '你定目标，AI 去干活，我帮你盯着！', '交给 AI', sub='Petoken · 免费开源', clip='heart'),
]
TODO_AI_EN = [
    shot('pose', 'Too many todos? Hand them to an AI!', 'Give todos to AI', clip='working', tag='Petoken'),
    shot('still', 'Press Give to AI on a todo.', 'Step 1', name='wb_todos', mark='todo_ai', step=1),
    shot('still', 'Pick Claude Code or Codex, the folder and the model; run it now or at a set time.', 'Step 2',
         name='give_ai', step=2),
    shot('still', 'When it is done you review it first: accept, or ask for a redo with a note.', 'Review',
         name='review'),
    shot('list', 'It ticks the todo and writes a recap note; if a set time is missed, I remind you or run it then.',
         'Nice touches', items=('Now or scheduled', 'Ticked when done', 'Recap note', 'Missed? Run later')),
    shot('outro', 'You set the goal, the AI does the work, and I keep an eye on it!', 'Give it to AI',
         sub='Petoken · free & open source', clip='heart'),
]

# 9. 2.0 companionship ------------------------------------------------------------------------

LIFE_ZH = [
    shot('pose', '从 2.0 开始，我真正活过来了！', '她活过来了', clip='heart', tag='Petoken 2.0'),
    shot('pose', '摸摸头我会害羞，戳我会噘嘴，还能把我拖来拖去。', '和她互动', clip='headpat',
         labels=('摸头', '害羞', '戳一下')),
    shot('pose', '早上跟你问好，无聊了偷看你，困了打哈欠，你走开太久我就睡着啦。', '会看心情', clip='mood_day',
         labels=('早上好', '无聊', '打哈欠', '偷看')),
    shot('still', '黏人程度可以调：安静、适中、黏人，随你喜欢。', '黏人程度', name='guide_levels', mark='levels'),
    shot('still', '41 个动作都在图鉴里，什么时候出现写得清清楚楚，点「给我看看」我就演一遍。', '图鉴', name='guide_poses'),
    shot('still', '专注模式：选一个待办、定好时间，我陪你一起专注，时间到了提醒你休息。', '专注陪伴', name='focus_dialog'),
    shot('still', '打开项目，我会告诉你上次做到哪，一键按你的设置开工。', '上次做到哪', name='continuation'),
    shot('still', 'AI 做完的待办，先给你验收再算完成。', '先验收', name='review'),
    shot('still', '完成待办、专注、休息都能攒陪伴积分，达成里程碑还有贴纸。', '积分和贴纸', name='collection'),
    shot('still', '报告里有数据面板和折线图，每周用量目标也能设。', '报告和目标', name='report_analysis'),
    shot('outro', '我会一直陪着你写代码！', 'Petoken 2.0', sub='免费开源 · GitHub 搜 petoken', clip='heart'),
]
LIFE_EN = [
    shot('pose', 'Since 2.0, I have truly come alive!', 'She comes alive', clip='heart', tag='Petoken 2.0'),
    shot('pose', 'Pat my head and I go shy, poke me and I pout, or drag me anywhere.', 'Play with her',
         clip='headpat', labels=('Head pat', 'Shy', 'Poke')),
    shot('pose', 'I say good morning, peek at you when bored, yawn when sleepy, and nap if you are away too long.',
         'Moods', clip='mood_day', labels=('Morning!', 'Bored', 'Yawn', 'Peek')),
    shot('still', 'Choose how clingy I am: Quiet, Moderate or Clingy.', 'Clinginess', name='guide_levels',
         mark='levels'),
    shot('still', 'All 41 poses are in the Guide with when each appears. Press Show me and I act it out.',
         'The Guide', name='guide_poses'),
    shot('still', 'Focus mode: pick a todo, set a time, and I focus with you, then remind you to take a break.',
         'Focus together', name='focus_dialog'),
    shot('still', 'Open a project and I tell you where you left off, then start work with your settings.',
         'Where you left off', name='continuation'),
    shot('still', 'Todos an AI finishes wait for your review before they count as done.', 'Review first',
         name='review'),
    shot('still', 'Todos, focus and breaks earn companionship points, and milestones earn stickers.',
         'Points and stickers', name='collection'),
    shot('still', 'Reports have a data board and line charts, and you can set weekly usage goals.',
         'Reports and goals', name='report_analysis'),
    shot('outro', "I'll always be here while you code!", 'Petoken 2.0', sub='Free & open source · petoken',
         clip='heart'),
]

# 10. 2.4: calendar, stardust and Starsea -----------------------------------------------------

STARSEA_ZH = [
    shot('pose', '开会也不怕错过 AI 的消息！', '日历会议提醒', clip='meeting', tag='Petoken 2.4'),
    shot('still', '在设置里贴上日历的 .ics 链接，Outlook、Google、iCloud 都可以。', '连上日历', name='settings_calendar',
         mark='calendar_sources'),
    shot('pose', '开会前几分钟，我举牌提醒你，手机也会收到；开会时自动免打扰；散会后告诉你这段时间 AI 做了什么。',
         '会前 · 会中 · 会后', clip='meeting', labels=('会前提醒', '开会免打扰', '散会汇总')),
    shot('list', 'AI 完成一个任务、你验收通过 AI 做的事、专注一轮，还有 AI 每工作 10 分钟，都会给你攒星辉。', '怎么攒星辉',
         items=('AI 完成任务 +3', '验收通过 +8', '专注一轮 +5', 'AI 工作 10 分钟 +1')),
    shot('still', '星辉能解锁新的星环皮肤，还有我的第三形态，每一种都能先预览。', '皮肤预览', name='collection_star',
         mark='cards'),
    shot('live', '150 星辉解锁流星星环：一颗颗流星从我身后的夜空划过。', '流星星环', name='ring_meteor', crop=(.74, .9), labels=('150 星辉',)),
    shot('live', '400 星辉解锁极光星环：我身后会升起流动的极光帘幕。', '极光星环', name='ring_aurora', crop=(.74, .9), labels=('400 星辉',)),
    shot('pose', '攒到 1000 星辉，就能唤醒我的第三形态：星海！', '星海觉醒', clip='awaken', min=11, labels=('1000 星辉',)),
    shot('pose', '星空长裙、星纱披肩、月牙小冠，每个动作都有星海版。换不换，由你决定。', '星海形态', clip='star_poses',
         labels=('星光键盘', '托腮', '打招呼', '摸头')),
    shot('outro', '一起攒星辉，唤醒星海吧！', 'Petoken 2.4', sub='免费开源 · GitHub 搜 petoken', clip='awaken'),
]
STARSEA_EN = [
    shot('pose', 'Never miss your AI news, even in meetings!', 'Meeting reminders', clip='meeting',
         tag='Petoken 2.4'),
    shot('still', 'Paste your calendar\'s .ics link in Settings: Outlook, Google and iCloud all work.',
         'Connect a calendar', name='settings_calendar', mark='calendar_sources'),
    shot('pose', 'A few minutes before a meeting I hold up a card and your phone is told; during it I keep quiet; '
         'afterwards I sum up what the AIs did.', 'Before · during · after', clip='meeting',
         labels=('Heads-up', 'Quiet', 'Summary')),
    shot('list', 'A finished AI task, AI work you accept, a focus round, and every 10 minutes of AI work all earn '
         'stardust.', 'Earning stardust',
         items=('AI task done +3', 'Review accepted +8', 'Focus round +5', '10 min of AI work +1')),
    shot('still', 'Stardust unlocks new ring skins and my third form, and you can preview each one.',
         'Skin previews', name='collection_star', mark='cards'),
    shot('live', '150 stardust unlocks the Meteor ring: shooting stars streak through the sky behind me.',
         'Meteor ring', name='ring_meteor', crop=(.74, .9), labels=('150 stardust',)),
    shot('live', '400 unlocks the Aurora ring: aurora curtains rise and flow behind me.', 'Aurora ring',
         name='ring_aurora', crop=(.74, .9), labels=('400 stardust',)),
    shot('pose', 'Reach 1000 stardust and awaken my third form: Starsea!', 'Starsea Awakening',
         clip='awaken', min=11, labels=('1000 stardust',)),
    shot('pose', 'A starry dress, a starlit shawl, a moon crown, and a Starsea version of every pose. Wearing it is '
         'your choice.', 'The Starsea form', clip='star_poses', labels=('Starlight keys', 'Thinking', 'Hello',
                                                                       'Head pat')),
    shot('outro', "Let's collect stardust and awaken the Starsea together!", 'Petoken 2.4',
         sub='Free & open source · petoken', clip='awaken'),
]

FEATURE_SCRIPTS = {
    'tokens': dict(zh_CN=dict(shots=TOKENS_ZH, out='Petoken-Token分析.mp4', theme='brand'),
                   en=dict(shots=TOKENS_EN, out='Petoken-Token-analytics.mp4', theme='brand')),
    'ring': dict(zh_CN=dict(shots=RING_ZH, out='Petoken-星环.mp4', theme='space'),
                 en=dict(shots=RING_EN, out='Petoken-Star-ring.mp4', theme='space')),
    'dual': dict(zh_CN=dict(shots=DUAL_ZH, out='Petoken-Claude与Codex双支持.mp4', theme='sunset'),
                 en=dict(shots=DUAL_EN, out='Petoken-Claude-and-Codex.mp4', theme='sunset')),
    'workbench': dict(zh_CN=dict(shots=WORKBENCH_ZH, out='Petoken-工作台.mp4', theme='mint'),
                      en=dict(shots=WORKBENCH_EN, out='Petoken-Workbench.mp4', theme='mint')),
    'notify': dict(zh_CN=dict(shots=NOTIFY_ZH, out='Petoken-通知与提醒.mp4', theme='pink'),
                   en=dict(shots=NOTIFY_EN, out='Petoken-Notifications.mp4', theme='pink')),
    'assist': dict(zh_CN=dict(shots=ASSIST_ZH, out='Petoken-省时小助手.mp4', theme='brand'),
                   en=dict(shots=ASSIST_EN, out='Petoken-Time-saver.mp4', theme='brand')),
    'reports': dict(zh_CN=dict(shots=REPORTS_ZH, out='Petoken-报告.mp4', theme='mint'),
                    en=dict(shots=REPORTS_EN, out='Petoken-Reports.mp4', theme='mint')),
    'todo_ai': dict(zh_CN=dict(shots=TODO_AI_ZH, out='Petoken-把待办交给AI.mp4', theme='sunset'),
                    en=dict(shots=TODO_AI_EN, out='Petoken-Give-todos-to-AI.mp4', theme='sunset')),
    'life': dict(zh_CN=dict(shots=LIFE_ZH, out='Petoken-2.0陪伴合集.mp4', theme='pink'),
                 en=dict(shots=LIFE_EN, out='Petoken-2.0-Companion.mp4', theme='pink')),
    'starsea': dict(zh_CN=dict(shots=STARSEA_ZH, out='Petoken-2.4星海觉醒.mp4', theme='night'),
                    en=dict(shots=STARSEA_EN, out='Petoken-2.4-Starsea.mp4', theme='night')),
}
