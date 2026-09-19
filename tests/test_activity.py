import unittest
from activity import ActivityState


class ActivityTests(unittest.TestCase):
    def test_priority_and_return_to_underlying_state(self):
        s=ActivityState()
        s.key(10)
        self.assertEqual(s.state(10),'typing')
        s.sample(microphone=False,music=True,now=10)
        self.assertEqual(s.state(10),'typing')
        s.sample(microphone=False,music=True,now=10.6)
        self.assertEqual(s.state(10.6),'music')
        s.sample(microphone=True,music=True,now=11)
        s.sample(microphone=True,music=True,now=11.6)
        self.assertEqual(s.state(11.6),'microphone')
        self.assertEqual(s.state(11.6,usage_open=True),'usage')
        s.sample(microphone=False,music=True,now=12)
        self.assertEqual(s.state(12),'microphone')
        s.sample(microphone=False,music=True,now=13.6)
        self.assertEqual(s.state(13.6),'music')

    def test_short_spikes_and_missing_signal_do_not_stick(self):
        s=ActivityState()
        s.sample(True,False,now=1)
        s.sample(False,False,now=1.1)
        self.assertEqual(s.state(2),'idle')
        s.key(3)
        self.assertEqual(s.state(4),'typing')
        self.assertEqual(s.state(5),'idle')
        s.sample(True,True,now=6);s.sample(True,True,now=7)
        self.assertEqual(s.state(7),'microphone')
        self.assertEqual(s.state(15),'idle')  # stale detector can't pin activity forever

    def test_codex_working_precedes_daily_activity_without_merging_typing(self):
        s=ActivityState();s.key(10)
        s.sample(True,True,now=10);s.sample(True,True,now=10.6)
        self.assertEqual(s.state(10.6,codex_working=True),'working')
        self.assertEqual(s.state(10.6,usage_open=True,codex_working=True),'usage')
        self.assertEqual(s.state(10.6,codex_working=False),'microphone')
        s.sample(False,True,now=11);s.sample(False,True,now=12.6)
        self.assertEqual(s.state(12.6),'music')
        s.sample(False,False,now=13);s.sample(False,False,now=14.6)
        self.assertEqual(s.state(14.6),'idle')


if __name__=='__main__':unittest.main()
