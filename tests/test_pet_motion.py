import random
import unittest
from datetime import datetime

import pet_motion as motion
from pet_mood import Mood, TUNING


class SpringTests(unittest.TestCase):
    def test_kick_overshoots_then_settles(self):
        spring = motion.Spring(260, 13)
        spring.kick(2.2)
        peak = 0
        for _ in range(120):
            spring.step(1 / 60)
            peak = max(peak, spring.value)
        self.assertGreater(peak, .05)
        self.assertLess(peak, .2)
        self.assertTrue(spring.settled)

    def test_step_size_does_not_change_the_result(self):
        a, b = motion.Spring(170, 12), motion.Spring(170, 12)
        a.kick(200)
        b.kick(200)
        for _ in range(60):
            a.step(1 / 60)
        for _ in range(30):
            b.step(1 / 30)
        self.assertAlmostEqual(a.value, b.value, places=3)


class AnimatorTests(unittest.TestCase):
    def make(self, frames=0, blink=False):
        return motion.Animator(lambda state: frames, lambda state: blink, rng=random.Random(1))

    def run_for(self, animator, start, seconds, fps=60):
        frame = None
        for n in range(int(seconds * fps)):
            frame = animator.step(start + n / fps)
        return frame

    def test_idle_breathes_around_the_feet(self):
        animator = self.make()
        heights = [animator.step(n / 30).scale_y for n in range(int(4 * 30))]
        self.assertGreater(max(heights) - min(heights), .008)
        frame = animator.step(5)
        self.assertEqual(frame.pivot, (.5, 1.0))
        self.assertLess(abs(frame.scale_x - 1), .02)

    def test_pose_change_cross_fades_and_hops(self):
        animator = self.make()
        animator.step(0)
        animator.set_state('celebrate', .5)
        frame = animator.step(.5 + motion.CROSSFADE_S / 2)
        self.assertEqual(frame.previous, 'idle')
        self.assertAlmostEqual(frame.fade, .5, places=1)
        self.assertTrue(frame.lively)
        lifts = [animator.step(.5 + n / 60).lift for n in range(6, 40)]
        self.assertGreater(max(lifts), 4)              # The entry hop.
        self.assertIsNone(self.run_for(animator, 1, .5).previous)

    def test_drag_sways_within_the_limit_and_lands(self):
        animator = self.make()
        animator.step(0)
        animator.start_drag((.5, .2))
        for n in range(60):
            animator.drag(5000)                     # Far faster than any real drag.
            frame = animator.step(n / 60)
        self.assertGreater(frame.angle, 1)
        self.assertLessEqual(frame.angle, motion.SWAY_LIMIT + .5)
        self.assertEqual(frame.pivot, (.5, .2))     # Swings from where you hold her.
        animator.end_drag()
        squash = [animator.step(1 + n / 60).scale_y for n in range(30)]
        self.assertLess(min(squash), .97)           # Squashes on landing.
        frame = self.run_for(animator, 2, 3)
        self.assertLess(abs(frame.angle), .3)
        self.assertEqual(frame.pivot, (.5, 1.0))

    def test_poke_leans_away_from_the_click(self):
        animator = self.make()
        animator.step(0)
        animator.poke(1.0)                          # Clicked on her right side.
        angles = [animator.step(n / 60).angle for n in range(1, 20)]
        self.assertLess(min(angles), -1)

    def test_frames_loop_or_stop_and_blend(self):
        animator = self.make(frames=4)
        animator.set_state('coquettish', 0)
        profile = motion.profile_for('coquettish')
        seen = {animator.step(n / 60).index for n in range(int(60 * 4 / profile.fps) + 2)}
        self.assertEqual(seen, {0, 1, 2, 3})
        blend = animator.step((1 - motion.FRAME_BLEND / 2) / profile.fps)
        self.assertEqual(blend.next_index, 1)
        self.assertGreater(blend.next_alpha, .3)
        once = self.make(frames=3)
        once.set_state('yawn', 0)
        self.assertEqual(once.step(30).index, 2)    # A one-shot holds its last frame.
        self.assertIsNone(once.step(31).next_index)

    def test_blinks_only_with_eyes_closed_art(self):
        with_art, without = self.make(blink=True), self.make(blink=False)
        blinks = [with_art.step(n / 60).blink for n in range(60 * 20)]
        self.assertTrue(any(blinks))
        self.assertLess(sum(blinks) / len(blinks), .2)
        self.assertFalse(any(without.step(n / 60).blink for n in range(60 * 20)))

    def test_particles_stay_near_the_head(self):
        for kind in ('hearts', 'sparkles', 'notes', 'zzz', 'sweat', 'question'):
            for t in (0, .7, 1.9, 5.3):
                for part in motion.particles(kind, t):
                    self.assertTrue(0 <= part.x <= 1, (kind, part))
                    self.assertTrue(-.25 <= part.y <= .3, (kind, part))
                    self.assertTrue(0 <= part.alpha <= 1)

    def test_every_companion_pose_has_a_profile(self):
        import pet_assets as assets
        for state in assets.companion_states() + assets.registered_states():
            self.assertIn(state, motion.PROFILES, state)


class MoodTests(unittest.TestCase):
    def day(self, hour, minute=0):
        return datetime(2026, 10, 6, hour, minute)

    def test_morning_greeting_once_a_day(self):
        mood = Mood('moderate', rng=random.Random(0))
        self.assertEqual(mood.update(0, self.day(9), idle=1), 'greet_morning')
        self.assertIsNone(mood.update(10, self.day(9), idle=1))
        self.assertIsNone(mood.update(20, self.day(10), idle=1))
        self.assertEqual(mood.greeted_day, '2026-10-06')

    def test_sleeps_when_away_wakes_and_welcomes_back(self):
        mood = Mood('moderate', rng=random.Random(0), greeted_day='2026-10-06')
        self.assertEqual(mood.update(0, self.day(14), idle=TUNING['moderate'].sleep_after), 'sleep')
        self.assertEqual(mood.update(60 * 40, self.day(15), idle=60 * 40), 'sleep')
        self.assertEqual(mood.update(60 * 40 + 1, self.day(15), idle=1), 'wake_stretch')
        self.assertEqual(mood.update(60 * 40 + 4, self.day(15), idle=1), 'hug')

    def test_falls_asleep_sooner_at_night_or_quiet(self):
        mood = Mood('moderate', greeted_day='2026-10-06')
        self.assertEqual(mood.update(0, self.day(23, 30), idle=TUNING['moderate'].night_sleep_after), 'sleep')
        quiet = Mood('moderate', greeted_day='2026-10-06')
        self.assertEqual(quiet.update(0, self.day(14), idle=TUNING['moderate'].night_sleep_after, quiet=True),
                         'sleep')

    def test_boredom_follows_clinginess(self):
        def bored_pose(level):
            mood = Mood(level, rng=random.Random(3), greeted_day='2026-10-06')
            mood.update(0, self.day(14), idle=1)
            return mood.update(20 * 60, self.day(14, 20), idle=1)
        self.assertIsNone(bored_pose('quiet'))
        self.assertEqual(bored_pose('moderate'), 'bored')
        self.assertIn(bored_pose('clingy'), ('bored', 'peek', 'coquettish'))

    def test_nothing_spontaneous_while_busy_quiet_or_fullscreen(self):
        for extra in (dict(busy=True), dict(quiet=True), dict(fullscreen=True)):
            mood = Mood('clingy', rng=random.Random(0))
            mood.update(0, self.day(9), idle=1, **extra)
            self.assertIsNone(mood.update(3600, self.day(10), idle=1, **extra), extra)

    def test_interaction_resets_boredom_and_wakes(self):
        mood = Mood('moderate', greeted_day='2026-10-06')
        mood.update(0, self.day(14), idle=1)
        mood.interacted(14 * 60)
        self.assertIsNone(mood.update(15 * 60, self.day(14, 15), idle=1))
        mood.update(16 * 60, self.day(14, 40), idle=TUNING['moderate'].sleep_after)
        self.assertTrue(mood.sleeping)
        mood.interacted(17 * 60)
        self.assertFalse(mood.sleeping)

    def test_good_night_when_quiet_hours_start_late(self):
        mood = Mood('moderate', greeted_day='2026-10-06')
        mood.update(0, self.day(23, 10), idle=1, quiet=False)
        self.assertEqual(mood.update(1, self.day(23, 11), idle=1, quiet=True), 'greet_night')


if __name__ == '__main__':
    unittest.main()
