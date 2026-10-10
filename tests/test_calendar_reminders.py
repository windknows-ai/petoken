import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication

import calendar_reminders as cr

APP = QApplication.instance() or QApplication([])

TORONTO = """BEGIN:VTIMEZONE
TZID:America/Toronto
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
TZNAME:EDT
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
TZNAME:EST
END:STANDARD
END:VTIMEZONE"""

ICS = f"""BEGIN:VCALENDAR
VERSION:2.0
{TORONTO}
BEGIN:VEVENT
UID:standup
SUMMARY:Stand-up\\, team
DTSTART;TZID=America/Toronto:20261005T093000
DTEND;TZID=America/Toronto:20261005T094500
RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR
EXDATE;TZID=America/Toronto:20261007T093000
END:VEVENT
BEGIN:VEVENT
UID:standup
RECURRENCE-ID;TZID=America/Toronto:20261009T093000
SUMMARY:Stand-up (moved)
DTSTART;TZID=America/Toronto:20261009T110000
DTEND;TZID=America/Toronto:20261009T111500
END:VEVENT
BEGIN:VEVENT
UID:review
SUMMARY:Design review
LOCATION:Room 4
DTSTART:20261009T190000Z
DURATION:PT1H
END:VEVENT
BEGIN:VEVENT
UID:holiday
SUMMARY:Holiday
DTSTART;VALUE=DATE:20261009
DTEND;VALUE=DATE:20261010
END:VEVENT
BEGIN:VEVENT
UID:gone
SUMMARY:Cancelled thing
STATUS:CANCELLED
DTSTART:20261009T150000Z
DTEND:20261009T160000Z
END:VEVENT
END:VCALENDAR
"""


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc).timestamp()


class ParseTests(unittest.TestCase):
    def test_zones_recurrence_exdates_and_overrides(self):
        now = utc(2026, 10, 8, 12)
        found = cr.events(ICS, now, days=3)
        titles = [(e['title'], e['start']) for e in found if not e['all_day']]
        # Wed 7 Oct is excluded; Fri 9 Oct moved to 11:00; EDT = UTC-4.
        self.assertNotIn(('Stand-up, team', utc(2026, 10, 7, 13, 30)), titles)
        self.assertIn(('Stand-up (moved)', utc(2026, 10, 9, 15)), titles)
        self.assertNotIn(('Stand-up, team', utc(2026, 10, 9, 13, 30)), titles)
        self.assertIn(('Design review', utc(2026, 10, 9, 19)), titles)
        review = next(e for e in found if e['title'] == 'Design review')
        self.assertEqual((review['end'] - review['start'], review['location']), (3600, 'Room 4'))
        self.assertTrue(any(e['all_day'] and e['title'] == 'Holiday' for e in found))
        self.assertFalse(any(e['title'] == 'Cancelled thing' for e in found))

    def test_daylight_saving_ends(self):
        zone = cr.Zone(cr.components(cr.unfold(TORONTO))['children'][0])
        self.assertEqual(zone.utcoffset(datetime(2026, 7, 1, 12)).total_seconds(), -4 * 3600)
        self.assertEqual(zone.utcoffset(datetime(2026, 11, 2, 12)).total_seconds(), -5 * 3600)
        self.assertEqual(cr.nth_weekday(2026, 11, '1SU').day, 1)
        self.assertEqual(cr.nth_weekday(2026, 10, '-1SU').day, 25)

    def test_count_until_and_folding(self):
        text = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:a\nSUMMARY:Long\n  name\nDTSTART:20261009T100000Z\n"
                "DTEND:20261009T103000Z\nRRULE:FREQ=DAILY;COUNT=2\nEND:VEVENT\nEND:VCALENDAR\n")
        found = cr.events(text, utc(2026, 10, 9, 0), days=5)
        self.assertEqual([e['title'] for e in found], ['Long name', 'Long name'])
        self.assertEqual(cr.duration('P1DT2H'), 93600)


class WatcherTests(unittest.TestCase):
    def make(self, now, **prefs):
        class Panel:
            pass
        panel = Panel()
        panel.prefs = dict(dict(calendar_enabled=True, calendar_sources=['test.ics'], calendar_lead_minutes=10,
                                calendar_dnd=True), **prefs)
        clock = mock.Mock(return_value=now)
        watcher = cr.CalendarWatcher(panel, clock=clock, reader=lambda link: ICS)
        watcher.refresh(wait=True)
        return watcher, clock

    def tearDown(self):
        cr._ACTIVE['meeting'] = None

    def test_soon_start_end_and_quiet(self):
        start = utc(2026, 10, 9, 19)
        watcher, clock = self.make(start - 9 * 60)
        self.assertEqual([k for k, _ in watcher.tick(start - 9 * 60)], ['soon'])
        self.assertEqual(watcher.tick(start - 8 * 60), [])                 # Only once.
        self.assertEqual([k for k, e in watcher.tick(start + 60)], ['start'])
        from notifications import quiet_now
        self.assertTrue(quiet_now({}, start + 60))
        self.assertFalse(quiet_now({}, start + 60, meetings=False))      # Pajamas stay off.
        actions = watcher.tick(start + 3700)
        self.assertEqual([k for k, _ in actions], ['end'])
        self.assertIsNone(cr.in_meeting())

    def test_no_quiet_when_turned_off_and_disabled_without_links(self):
        start = utc(2026, 10, 9, 19)
        watcher, _ = self.make(start, calendar_dnd=False)
        watcher.tick(start + 60)
        self.assertIsNone(cr.in_meeting())
        watcher.panel.prefs['calendar_sources'] = []
        self.assertEqual(watcher.tick(start + 120), [])

    def test_a_broken_link_does_not_hide_the_others(self):
        class Panel:
            prefs = dict(calendar_enabled=True, calendar_sources=['bad', 'good'])

        def reader(link):
            if link == 'bad':
                raise OSError('nope')
            return ICS
        watcher = cr.CalendarWatcher(Panel(), clock=lambda: utc(2026, 10, 8, 12), reader=reader)
        watcher.refresh(wait=True)
        self.assertTrue(watcher.items)
        self.assertEqual(watcher.error, 'OSError')


class PanelCalendarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pref_patch = mock.patch('widget.PREF_DIR', Path(self.temp.name))
        self.pref_patch.start()
        from widget import Panel
        from pet import DesktopPet
        self.panel = Panel(live=False)
        self.pet = DesktopPet(self.panel)
        self.panel.pet = self.pet
        self.pet.activity_timer.stop()
        self.pet.timer.stop()

    def tearDown(self):
        cr._ACTIVE['meeting'] = None
        self.panel.focus_mode.abandon()
        self.panel.tray.hide()
        self.pet.close()
        self.panel.closing = True
        self.panel.close()
        self.panel.deleteLater()
        APP.processEvents()
        self.pref_patch.stop()
        self.temp.cleanup()

    def test_card_before_and_summary_after(self):
        start = utc(2026, 10, 9, 19)
        self.panel.prefs.update(calendar_enabled=True, calendar_sources=['x.ics'])
        self.panel.calendar.reader = lambda link: ICS
        self.panel.calendar.clock = lambda: start - 5 * 60
        self.panel.calendar.refresh(wait=True)
        self.pet.show()
        self.panel.calendar_tick(start - 5 * 60)
        self.assertEqual(self.pet.interaction_state, 'hold_card')
        self.panel.calendar_tick(start + 60)
        self.panel.notifications.store.add_event(dict(kind='finished', provider='claude', task_key='t', at=start + 600,
                                                   project='site', detail='', dedupe='m1'))
        with mock.patch.object(self.panel.tray, 'showMessage') as shown, \
                mock.patch.object(self.panel.tray, 'isVisible', return_value=True):
            self.panel.preview_toasts = True
            self.panel.calendar_tick(start + 3700)
        self.assertTrue(shown.called)
        self.assertIn('1', shown.call_args[0][1])

    def test_settings_calendar_page_saves(self):
        from widget import Settings
        settings = Settings(self.panel)
        settings.calendar_enabled.setChecked(True)
        settings.calendar_sources.setPlainText('https://example.com/a.ics\n\n  ')
        settings.calendar_lead.setCurrentIndex(settings.calendar_lead.findData(15))
        with mock.patch('widget.write_preferences'):
            settings.save()
        self.assertEqual(self.panel.prefs['calendar_sources'], ['https://example.com/a.ics'])
        self.assertEqual(self.panel.prefs['calendar_lead_minutes'], 15)
        settings.deleteLater()


if __name__ == '__main__':
    unittest.main()
