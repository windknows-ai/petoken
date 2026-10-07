"""The English tutorial video, scene by scene (same scenes as tutorial_script.py).

UI terms in “quotes” match the app's English labels and are highlighted.
"""
from tools.tutorial_script import S

CHAPTERS = (
    ('intro', 'Meet Petoken'),
    ('pet', 'Playing with her'),
    ('usage', 'AI usage'),
    ('notify', 'Alerts & approvals'),
    ('launch', 'Quick launch'),
    ('workbench', 'Workbench'),
    ('focus', 'Focus'),
    ('settings', 'Settings'),
    ('end', 'Wrap-up'),
)

PET_STEPS = ('Drag: move her', 'Click: a poke', 'Click fast: she pouts', 'Stroke her head: a pat',
             'Hold still: she gets cuddly')
USAGE_STEPS = ('Star ring: one star per task', 'Usage card: three rings', 'Usage panel: every number',
               "Refresh Claude's limits")
NOTIFY_STEPS = ('Reactions and notifications', 'Approve Claude beside her', "Claude's questions and plans",
                'Do Not Disturb')
WB_STEPS = ('Home', 'Todos and Give to AI', 'Ready for review', 'Notes', 'Projects and Start Work',
            'Where I Left Off', 'Usage goals', 'Notifications', 'Reports', 'Collection', 'Guide')
FOCUS_STEPS = ('Start focusing', 'Pick a todo and breaks', 'Countdown and End button', 'Summary card', 'Breaks')
SET_STEPS = ('General', 'Tasks', 'Claude and Codex', 'Assistant', 'About the data')

SCENES = [
    S('intro', "Hi, I'm Petoken!",
      "Hi there! I'm your AI coding buddy, living right on your desktop. I keep an eye on Claude Code and "
      "Codex: what they're doing and how much of your limits is left. I'll ping you when a job is done or "
      "needs you, keep you company while you focus, and help with todos and projects.",
      ('pet', 'idle')),
    S('intro', "Here's the tour",
      "Let me show you around: playing with me, usage, alerts and approvals, quick launch, the workbench, "
      "focus, and settings. Everything stays on your own computer.",
      ('pet', 'greet_morning')),

    S('pet', 'Pick me up', "Want me somewhere else? Just drag me! I dangle while you carry me and land "
      "softly when you let go. I remember where you put me.", ('pet', 'drag'), PET_STEPS, 0),
    S('pet', 'A little poke', "Click me and I wobble. Left clicks are just for play, they never open a "
      "window. Poke away!", ('pet', 'poked'), PET_STEPS, 1),
    S('pet', "Don't overdo it", "Five clicks in four seconds? Hmph, I'll puff up my cheeks! Keep going and "
      "I stay grumpy until you stop.", ('pet', 'pout'), PET_STEPS, 2),
    S('pet', 'Head pats', "Move the mouse back and forth over my head for about a second, no buttons, and "
      "that's a head pat: I close my eyes, happy. Keep it up for five seconds and I hide my face!",
      ('pet', 'headpat'), PET_STEPS, 3),
    S('pet', 'Hold me', "Press and hold me for about 0.7 seconds and I get all cuddly. Don't worry, that "
      "won't turn into a drag.", ('pet', 'coquettish'), PET_STEPS, 4),
    S('pet', 'Right-click: everything', "Right-click me for the menu: the usage panel, quick launch, focus, "
      "the workbench, reports and settings. Hover an item and I'll tell you what it does.",
      ('still', 'menu')),
    S('pet', 'I have moods too', "When there's nothing to do, I keep myself busy: good morning in the "
      "morning, a blank stare when you ignore me, and yawns when you stay up late.", ('pet', 'mood_day')),
    S('pet', 'Sleepy, then awake', "Step away and I curl up and sleep. Come back and I stretch awake, and "
      "if you were gone for half an hour, I welcome you back with open arms!", ('pet', 'mood_sleep')),
    S('pet', 'How clingy?', "You choose how clingy I am: “Quiet”, “Moderate” or “Clingy”. The "
      "workbench “Guide” spells out what each level does; press “Use this level” to switch.",
      ('still', 'guide_levels'), highlight=('levels',)),

    S('usage', 'The star ring', "When Claude Code or Codex gets to work, a ring of stars lights up around me: "
      "one star per running task, blue for Codex, gold for Claude Code. Click a star for details.",
      ('still', 'ring'), USAGE_STEPS, 0),
    S('usage', 'The usage card', "The card above my head shows what's left: context, 5 hours and one week, "
      "one ring each, with the time until it resets. Amber means low, red means nearly gone. "
      "“Usage card (also when idle)” is on by default, so it stays even when nothing runs.",
      ('still', 'card'), USAGE_STEPS, 1, ('card',)),
    S('usage', "N/A? Nothing's broken", "A dashed ring with N/A just means your plan has no such limit, "
      "like Codex Pro with no 5-hour limit. For Claude's limits, turn on “Sync Claude usage” in Settings.",
      ('still', 'card_na'), USAGE_STEPS, 1),
    S('usage', 'Every number', "Check “Usage panel (always shown)” in my menu for the full picture: tokens, "
      "cache hits, context and every limit, for one task, a session, a project or everything.",
      ('still', 'panel'), USAGE_STEPS, 2),
    S('usage', "Claude's limits, always fresh", "Claude only updates its limits when a conversation moves. "
      "Turn on “Refresh Claude's limits in the background” and I'll quietly ask Haiku every 1, 5 or 15 "
      "minutes. No windows pop up.", ('still', 'settings_claude'), USAGE_STEPS, 3, ('claude_probe',)),

    S('notify', 'Job done!', "When an AI finishes, I cheer or give you a thumbs-up, and Windows shows a "
      "notification. Done in under a minute? I'm amazed! Errors or low limits make me sad, so you'll know.",
      ('pet', 'notify'), NOTIFY_STEPS, 0),
    S('notify', 'Approve right here', "Claude Code wants to run a command or edit a file? A card pops up next "
      "to me: “Allow”, “Always allow”, “Deny”, or hand it back to Claude. No terminal needed.",
      ('still', 'approval'), NOTIFY_STEPS, 1),
    S('notify', 'Claude has a question', "When Claude asks, the card lists its options. Pick one or several, "
      "or write your own, then press “Answer”. I sit and think along with you.",
      ('still', 'question'), NOTIFY_STEPS, 2),
    S('notify', 'Sign off on the plan', "When Claude brings a plan, accept it, or write what to change and "
      "let it plan again.", ('still', 'plan'), NOTIFY_STEPS, 2),
    S('notify', 'Shh, Do Not Disturb', "Need quiet? Turn on “Do Not Disturb” in Settings, or schedule it "
      "daily. I stay still and silent, and everything is still saved under “Notifications”.",
      ('still', 'settings_assistant'), NOTIFY_STEPS, 3, ('dnd',)),

    S('launch', 'One line, one job', "Press Alt + Shift + Space anywhere, or pick “Quick launch” in my menu: "
      "write what to do, pick a folder, Claude Code or Codex, the model and effort, and go! Just want to "
      "talk? Tick “Just chat”.", ('still', 'quick_launch')),

    S('workbench', 'Welcome to the workbench', "Right-click me and open the workbench: todos, notes and "
      "projects in one place, and you can focus on one project on the left. “Home” starts with AI work "
      "ready for your review.", ('still', 'wb_home'), WB_STEPS, 0),
    S('workbench', 'Todos', "Press “Add todo”, write it down, tick it off when it's done. Select one to "
      "get “Give to AI…” and “Focus on it”; edit and delete live under “More”.",
      ('still', 'wb_todos'), WB_STEPS, 1, ('todo_ai',)),
    S('workbench', 'Give it to an AI', "“Give to AI…” sends the job to Claude Code or Codex: describe it, "
      "pick the folder, app, model and effort, and start now or at a set time.",
      ('still', 'give_ai'), WB_STEPS, 1),
    S('workbench', 'Review before done', "A todo the AI finished isn't ticked right away: it's ready for your "
      "review, and I hold up a card. See what it did, then “Accept”, or say what to change and “Redo”.",
      ('still', 'review'), WB_STEPS, 2),
    S('workbench', 'Notes', "Jot anything down in notes, file them under a project, save with Ctrl + S. "
      "When an AI finishes a todo, it leaves a note here: files changed and time taken.",
      ('still', 'wb_notes'), WB_STEPS, 3),
    S('workbench', 'Projects + Start Work', "A project is a folder on your computer. Press “New project”, "
      "name it, pick the folder. Then “Start Work” wakes the AI with your settings and tells it your last "
      "note.", ('still', 'wb_projects'), WB_STEPS, 4, ('start_work',)),
    S('workbench', 'Start Settings', "Under “More”, “Start Settings” picks the AI, model, effort and opening "
      "words for a project. Leave it empty and the AI first looks around and tells you where you left off.",
      ('still', 'preset'), WB_STEPS, 4),
    S('workbench', 'Where I Left Off', "“Where I Left Off” shows your last note on top, then the AI's last "
      "task, what's unfinished and your HANDOFF file. Leave a line for next time. Come back hours later and "
      "I'll hold up this card myself.", ('still', 'continuation'), WB_STEPS, 5),
    S('workbench', 'Earlier notes', "“Earlier notes” keeps everything you wrote for this project. Delete "
      "what you don't need.", ('still', 'history'), WB_STEPS, 5),
    S('workbench', 'Usage goals', "Set a weekly limit for a project under “More”, in tokens (millions or "
      "billions) or dollars. At 80% I get nervous, over it I warn you once, and a week under it makes me "
      "proud!", ('still', 'goal'), WB_STEPS, 6),
    S('workbench', 'All your notifications', "“Notifications” keeps every finish, error, approval and limit "
      "alert for 30 days, filterable by type. Add your own reminders too.",
      ('still', 'wb_notify'), WB_STEPS, 7),
    S('workbench', 'Reports: data board', "“Reports” shows how much the AI did. On the “Data board” pick "
      "today, yesterday, this week or an earlier week: tasks, AI time, files, tokens, cost and the change, "
      "plus a searchable history.", ('still', 'report_board'), WB_STEPS, 8),
    S('workbench', 'Reports: analysis', "“Analysis” draws line charts of tokens, cost, AI time and tasks: "
      "today by the hour, this week, 7 or 30 days, or 12 weeks. Hover for the exact numbers.",
      ('still', 'report_analysis'), WB_STEPS, 8),
    S('workbench', 'Points and stickers', "Finishing todos, accepting AI work, focusing and taking breaks earn "
      "companionship points, and milestones earn stickers. Tokens never count. It's all in “Collection”.",
      ('still', 'collection'), WB_STEPS, 9),
    S('workbench', 'My guide', "The “Guide” has all 41 of my poses and when each one shows up. Press “Show "
      "me” and I'll act it out!", ('still', 'guide_poses'), WB_STEPS, 10),

    S('focus', "Let's focus", "Time to concentrate? Right-click me, “Start focusing”, and pick 25, 45 or 60 "
      "minutes, or select a todo and press “Focus on it”. I'll cheer you on!", ('pet', 'cheer'),
      FOCUS_STEPS, 0),
    S('focus', 'Plan it first', "“Choose a todo and breaks…” sets the length, the todo, break lengths and how "
      "often a long break comes. One sentence below sums it all up.", ('still', 'focus_dialog'),
      FOCUS_STEPS, 1),
    S('focus', 'Focusing, shh', "While you focus I read quietly beside you; only urgent things like approvals "
      "and errors get through. The countdown hangs under me, with “End focus” right next to it.",
      ('still', 'focus_tag'), FOCUS_STEPS, 2, ('focus_tag',)),
    S('focus', "Time's up!", "Then I tell you what got done: todos, AI tasks, files changed and tokens used. "
      "Picked a todo? “This todo is done” ticks it off.", ('still', 'focus_card'), FOCUS_STEPS, 3),
    S('focus', 'Stretch your legs', "Break time! I stretch and sip some tea, and remind you to move around. "
      "I'll tell you when it's over, or press “End break” any time.", ('pet', 'break'), FOCUS_STEPS, 4),

    S('settings', 'Settings: General', "Right-click me, “Settings”. Every option says what it does. General "
      "has language, my size, clinginess, always on top, the star ring and updates.",
      ('still', 'settings_general'), SET_STEPS, 0),
    S('settings', 'Settings: Tasks', "Tasks decides whose usage I show and how it's counted, Claude Code or "
      "Codex, plus number format and currency.", ('still', 'settings_tracking'), SET_STEPS, 1),
    S('settings', 'Settings: Claude and Codex', "This page connects me to Claude Code and Codex: usage sync, "
      "instant alerts, approvals beside me and the background refresh. Each one backs up your settings "
      "first and restores them when turned off.", ('still', 'settings_claude'), SET_STEPS, 2),
    S('settings', 'Settings: Assistant', "Predictions and tips, Where I Left Off reminders, Do Not Disturb, "
      "missed scheduled todos and the quick launch shortcut.", ('still', 'settings_assistant'), SET_STEPS, 3),
    S('settings', 'Settings: About the data', "The last page explains where the numbers come from and how "
      "costs are estimated, and exports diagnostics if something goes wrong.", ('still', 'settings_about'),
      SET_STEPS, 4),

    S('end', 'Updates, and your data stays home', "I check for a new version once a day and tell you what "
      "changed, or install it automatically if you like. Your data never leaves this computer.",
      ('pet', 'proud')),
    S('end', "That's it!", "New here? Open “Getting started” at the top right of the workbench and try it "
      "step by step. Let's get things done together!", ('pet', 'heart')),
]
