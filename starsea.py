"""2.4 "Starsea Awakening": her third form, unlocked with 1000 stardust.

Once unlocked she can wear it from the right-click menu (Show > Starsea form)
or the workbench Collection page; it is never put on by itself. Game mode
(her second form) and late-night pajamas still win; afterwards she is back
in the form you chose. Switching plays a short awakening: the starry dress,
shawl, crown and nebula hair tips appear one after another
(docs/V2_4_STARSEA_PLAN.md, art in assets/v2_4).
"""
from __future__ import annotations

# Starsea versions of her poses; any other pose becomes star_idle.
STAR_POSES = {'idle': 'star_idle', 'sleep': 'star_sleep', 'yawn': 'star_sleep', 'dragged': 'star_dragged'}
STAR_POSES.update(dict.fromkeys(('typing', 'codex_working', 'working', 'focus_read', 'music', 'guitar',
                                 'microphone'), 'star_typing'))
STAR_POSES.update(dict.fromkeys(('celebrate', 'thumbs_up', 'cheer', 'clap', 'proud', 'heart', 'focus_done',
                                 'wake_stretch', 'stretch_break'), 'star_celebrate'))
STAR_POSES.update(dict.fromkeys(('sad', 'pout', 'grievance', 'worried'), 'star_sad'))
STAR_POSES.update(dict.fromkeys(('wave', 'greet_morning', 'greet_night', 'hold_card', 'ready_go', 'hug'),
                                'star_wave'))
STAR_POSES.update(dict.fromkeys(('thinking', 'curious', 'bored', 'peek'), 'star_thinking'))
STAR_POSES.update(dict.fromkeys(('headpat_happy', 'coquettish', 'shy'), 'star_headpat'))
STAR_POSES.update(dict.fromkeys(('poked', 'surprised', 'landing'), 'star_poked'))
# Poses that belong to another look and are shown as they are.
OTHER_FORMS = ('star_', 'awaken_', 'night_', 'form2_', 'game_', 'xform_', 'night:', 'game:', 'star:')
# The awakening, (pose, seconds); played backwards to change back.
AWAKEN = (('awaken_0', .7), ('awaken_1', .8), ('awaken_2', .8), ('awaken_3', .8), ('awaken_4', 1.0))


def awaken_steps(on):
    steps = AWAKEN if on else tuple(reversed(AWAKEN))
    return steps + ((('star_idle' if on else 'idle'), .6),)


class StarseaForm:
    def __init__(self, panel):
        self.panel = panel
        self.active = False

    def art_ready(self):
        import pet_assets
        return all(pet_assets.has_own_art(pose) for pose, _s in AWAKEN) and pet_assets.has_own_art('star_idle')

    def available(self):
        """Unlocked with stardust and drawn."""
        from stardust import unlocked
        dust = getattr(self.panel, 'stardust', None)
        return dust is not None and 'starsea' in unlocked(dust.total()) and self.art_ready()

    def apply(self, animate=False):
        """Wear the chosen form; returns whether she is in Starsea now."""
        wanted = self.panel.prefs.get('pet_form') == 'starsea' and self.available()
        if wanted != self.active:
            self.active = wanted
            pet = getattr(self.panel, 'pet', None)
            if animate and pet is not None and pet.isVisible():
                pet.play_change(awaken_steps(wanted))
            elif pet is not None:
                pet.update_activity()
        return self.active

    def toggle(self):
        self.panel.prefs['pet_form'] = 'default' if self.active else 'starsea'
        self.panel.persist()
        return self.apply(animate=True)

    def pose(self, pose):
        """The Starsea version of ``pose`` while she wears it and its art exists."""
        if not self.active or pose.startswith(OTHER_FORMS):
            return pose
        import pet_assets
        own = f'star_{pose}'
        if own in STAR_POSES.values() and pet_assets.has_own_art(own):
            return own                                       # The first Starsea pictures of this very action.
        full = pet_assets.full_set('star', pose)             # Its own Starsea picture of this action.
        if full:
            return full
        star = STAR_POSES.get(pose, 'star_idle')
        return star if pet_assets.has_own_art(star) else pose
