"""Game mode detection: what counts as a game, and the enter/leave hysteresis."""
import unittest

import game_detect
from game_detect import GameDetector, is_game


def frame(exe, fullscreen=True):
    return dict(pid=1234, exe=exe, name=exe.replace('/', '\\').rsplit('\\', 1)[-1].lower(),
                window_class='X', rect=(0, 0, 1920, 1080), monitor=(0, 0, 1920, 1080),
                fullscreen=fullscreen)


class Scene:
    """A fake foreground window the test can change between polls."""

    def __init__(self, info=None, d3d=False):
        self.info = info
        self.d3d_on = d3d
        self.fail = False

    def scan(self):
        if self.fail:
            raise OSError('boom')
        return self.info

    def d3d(self):
        if self.fail:
            raise OSError('boom')
        return self.d3d_on


class IsGameTests(unittest.TestCase):
    def test_launcher_libraries(self):
        for path in (r'D:\SteamLibrary\steamapps\common\Hades\Hades.exe',
                     r'C:\Program Files\Epic Games\Fortnite\FortniteClient.exe',
                     r'C:\Riot Games\VALORANT\live\Foo.exe',
                     r'C:\Program Files (x86)\World of Warcraft\_retail_\Wow.exe',
                     r'D:\Games\Genshin Impact\Genshin Impact Game\Whatever.exe',
                     r'C:\Program Files\HoYoPlay\games\Star Rail Game\Game.exe',
                     r'C:\XboxGames\Forza\Content\gamelaunchhelper.exe'):
            self.assertTrue(is_game(path), path)

    def test_known_names_anywhere(self):
        for name in ('YuanShen.exe', 'cs2.exe', 'League of Legends.exe', 'TslGame.exe',
                     'NarakaBladepoint.exe', 'eldenring.exe'):
            self.assertTrue(is_game(r'E:\random\%s' % name), name)

    def test_known_non_games_even_in_a_library(self):
        for path in (r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                     r'C:\Program Files\VideoLAN\VLC\vlc.exe',
                     r'C:\Program Files\Microsoft VS Code\Code.exe',
                     r'C:\Program Files (x86)\Steam\steam.exe',
                     r'C:\Program Files\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe',
                     r'C:\Windows\explorer.exe',
                     r'C:\Program Files\Java\bin\javaw.exe',
                     r'D:\SteamLibrary\steamapps\common\Foo\javaw.exe'):
            self.assertFalse(is_game(path), path)

    def test_unknown_program_is_not_a_game(self):
        self.assertFalse(is_game(r'C:\Tools\photoeditor.exe'))
        self.assertFalse(is_game(''))
        self.assertFalse(is_game(None))

    def test_user_lists(self):
        mine = r'C:\Stuff\MyIndie.exe'
        self.assertFalse(is_game(mine))
        self.assertTrue(is_game(mine, extra=('myindie.EXE',)))
        self.assertFalse(is_game(r'D:\steamapps\common\X\Game.exe', excluded=('game.exe',)))
        self.assertFalse(is_game(r'E:\cs2.exe', extra=('cs2.exe',), excluded=('CS2.exe',)))
        self.assertTrue(is_game(r'C:\Program Files\Chrome\chrome.exe', extra=('chrome.exe',)))

    def test_case_and_separators(self):
        self.assertTrue(is_game('D:/SteamLibrary/STEAMAPPS/Common/Hades/Hades.EXE'))
        self.assertTrue(is_game(r'd:\steamlibrary\steamapps\common\hades\hades.exe'))
        self.assertTrue(is_game('E:/x/CS2.EXE'))
        self.assertFalse(is_game('C:/Program Files/Google/Chrome/CHROME.EXE'))


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.game = frame(r'D:\SteamLibrary\steamapps\common\Hades\Hades.exe')
        self.scene = Scene(self.game)
        self.detector = GameDetector(scan=self.scene.scan, d3d=self.scene.d3d)

    def test_enters_after_four_seconds(self):
        self.assertFalse(self.detector.poll(0))
        self.assertFalse(self.detector.poll(3.9))
        self.assertTrue(self.detector.poll(4.0))
        self.assertTrue(self.detector.playing)
        self.assertEqual(self.detector.game, 'hades.exe')

    def test_a_flicker_resets_the_enter_timer(self):
        self.detector.poll(0)
        self.scene.info = frame(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        self.detector.poll(3)
        self.scene.info = self.game
        self.detector.poll(3.5)
        self.assertFalse(self.detector.poll(7.0))
        self.assertTrue(self.detector.poll(7.5))

    def test_short_alt_tab_keeps_playing_and_long_one_leaves(self):
        self.detector.poll(0)
        self.detector.poll(5)
        self.assertTrue(self.detector.playing)
        self.scene.info = frame(r'C:\Windows\explorer.exe')
        self.assertTrue(self.detector.poll(10))
        self.assertTrue(self.detector.poll(19.9))
        self.scene.info = self.game                     # Back in the game before the 15 s are up.
        self.assertTrue(self.detector.poll(20))
        self.scene.info = None
        self.assertTrue(self.detector.poll(34.9))
        self.assertFalse(self.detector.poll(35))
        self.assertFalse(self.detector.playing)
        self.assertEqual(self.detector.game, 'hades.exe')   # The last game is remembered.

    def test_windowed_game_needs_d3d_fullscreen(self):
        self.scene.info = frame(self.game['exe'], fullscreen=False)
        for t in (0, 5, 10):
            self.assertFalse(self.detector.poll(t))
        self.scene.d3d_on = True
        self.detector.poll(11)
        self.assertTrue(self.detector.poll(15))

    def test_fullscreen_non_games_never_start_it(self):
        for exe in (r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                    r'C:\Program Files\VideoLAN\VLC\vlc.exe', r'C:\Windows\explorer.exe'):
            self.scene.info = frame(exe)
            self.scene.d3d_on = True
            self.assertFalse(any(self.detector.poll(t) for t in range(0, 60, 2)), exe)
        self.assertIsNone(self.detector.game)

    def test_user_lists_reach_the_detector(self):
        self.scene.info = frame(r'C:\Stuff\MyIndie.exe')
        self.assertFalse(self.detector.poll(0))
        self.assertFalse(self.detector.poll(10))
        self.assertFalse(self.detector.poll(20, extra=('myindie.exe',), excluded=('myindie.exe',)))
        self.detector.poll(30, extra=('myindie.exe',))
        self.assertTrue(self.detector.poll(34, extra=('myindie.exe',)))
        # Excluding it afterwards counts as no game frames, so it ends after 15 s.
        self.assertTrue(self.detector.poll(40, excluded=('myindie.exe',)))
        self.assertFalse(self.detector.poll(49, extra=('myindie.exe',), excluded=('myindie.exe',)))

    def test_exceptions_count_as_no_game(self):
        self.detector.poll(0)
        self.detector.poll(5)
        self.assertTrue(self.detector.playing)
        self.scene.fail = True
        self.assertTrue(self.detector.poll(10))          # Tolerated, still inside the 15 s.
        self.assertFalse(self.detector.poll(20))
        fresh = GameDetector(scan=self.scene.scan, d3d=self.scene.d3d)
        self.assertFalse(fresh.poll(0))
        self.assertFalse(fresh.poll(100))


class WindowsTests(unittest.TestCase):
    def test_foreground_info_does_not_crash(self):
        info = game_detect.foreground_info()
        if info is not None:
            self.assertEqual(set(info), {'pid', 'exe', 'name', 'window_class', 'rect', 'monitor', 'fullscreen'})
            self.assertIsInstance(info['fullscreen'], bool)
            self.assertEqual(info['name'], info['name'].lower())
            self.assertEqual(len(info['rect']), 4)

    def test_d3d_fullscreen_returns_a_bool(self):
        self.assertIsInstance(game_detect.d3d_fullscreen(), bool)

    def test_covers_tolerates_one_pixel(self):
        monitor = (0, 0, 1920, 1080)
        self.assertTrue(game_detect._covers((0, 0, 1920, 1080), monitor))
        self.assertTrue(game_detect._covers((-1, -1, 1921, 1081), monitor))
        self.assertTrue(game_detect._covers((1, 1, 1919, 1079), monitor))
        self.assertFalse(game_detect._covers((0, 0, 1920, 1040), monitor))   # Taskbar showing.
        self.assertFalse(game_detect._covers((100, 100, 1000, 700), monitor))


if __name__ == '__main__':
    unittest.main()
