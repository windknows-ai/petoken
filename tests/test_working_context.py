import json
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from usage import CodexStore, project_identity


class ContextFixture:
    def __init__(self, root):
        self.home = Path(root)
        self.rows = []
        self.projects = {}
        self.assignments = {}

    def add(self, thread, name, total, project_id=None, project_name=None,
            working=True, mtime=None, cwd='', origin=''):
        path = self.home / f'{thread}.jsonl'
        usage = dict(input_tokens=total-10, cached_input_tokens=0,
                     output_tokens=10, reasoning_output_tokens=0, total_tokens=total)
        events = [
            dict(type='session_meta', payload=dict(id=thread, timestamp='2026-09-19T12:00:00Z')),
            dict(type='turn_context', payload=dict(model='gpt-6-astra', effort='high')),
            dict(type='event_msg', timestamp='2026-09-19T12:00:01Z', payload=dict(type='task_started')),
            dict(type='event_msg', timestamp='2026-09-19T12:00:02Z', payload=dict(
                type='token_count', info=dict(total_token_usage=usage,last_token_usage=usage,
                                              model_context_window=1000))),
        ]
        if not working:
            events.append(dict(type='event_msg', timestamp='2026-09-19T12:00:03Z',
                               payload=dict(type='task_complete')))
        path.write_text(''.join(json.dumps(event)+'\n' for event in events), encoding='utf-8')
        stamp = time.time() if mtime is None else mtime
        os.utime(path, (stamp,stamp))
        self.rows.append(dict(id=thread,name=name,title='',cwd=cwd,rollout_path=str(path),
            model='gpt-6-astra',reasoning_effort='high',source='desktop',project_id=project_id,
            git_origin_url=origin,updated_at=int(stamp),archived=0))
        if project_id:
            self.assignments[thread] = {'projectId':project_id}
            self.projects[project_id] = {'name':project_name} if project_name else {}

    def finish(self):
        with closing(sqlite3.connect(self.home/'state_1.sqlite')) as db:
            db.execute('''create table threads (
                id text, name text, title text, cwd text, rollout_path text, model text,
                reasoning_effort text, source text, project_id text, git_origin_url text,
                updated_at integer, archived integer)''')
            for row in self.rows:
                db.execute('insert into threads values (?,?,?,?,?,?,?,?,?,?,?,?)', tuple(row.values()))
            db.commit()
        state = {'local-projects':self.projects,'thread-project-assignments':self.assignments}
        (self.home/'.codex-global-state.json').write_text(json.dumps(state), encoding='utf-8')
        return CodexStore(self.home)


class WorkingContextTests(unittest.TestCase):
    def test_one_active_session_maps_to_explicit_project(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=ContextFixture(directory)
            fixture.add('a','Task A',120,'project-a','Alpha')
            data=fixture.finish().read('Task A',activity_detection_valid=True)
        context=data['working_context']
        self.assertEqual(context['thread'],'a')
        self.assertEqual(context['project'],'Alpha')
        self.assertEqual(context['project_source'],'project_metadata')
        self.assertEqual(context['tokens']['total_tokens'],120)

    def test_foreground_working_session_keeps_project_and_tokens_coherent(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=ContextFixture(directory);now=time.time()
            fixture.add('a','Task A',110,'project-a','Alpha',mtime=now-1)
            fixture.add('b','Task B',220,'project-b','Beta',mtime=now)
            data=fixture.finish().read('Task A',activity_detection_valid=True)
        context=data['working_context']
        self.assertEqual((context['thread'],context['project'],context['tokens']['total_tokens']),
                         ('a','Alpha',110))
        self.assertEqual(context['selection'],'foreground')

    def test_unmapped_foreground_falls_back_to_most_recent_working_session(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=ContextFixture(directory);now=time.time()
            fixture.add('a','Task A',110,'project-a','Alpha',mtime=now-2)
            fixture.add('b','Task B',220,'project-b','Beta',mtime=now-1)
            data=fixture.finish().read('Unknown Task',activity_detection_valid=True)
        context=data['working_context']
        self.assertEqual((context['thread'],context['project'],context['tokens']['total_tokens']),
                         ('b','Beta',220))
        self.assertEqual(context['selection'],'most_recent')

    def test_foreground_switch_updates_identity_and_tokens_together(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=ContextFixture(directory);now=time.time()
            fixture.add('a','Task A',110,'project-a','Alpha',mtime=now-1)
            fixture.add('b','Task B',220,'project-b','Beta',mtime=now)
            store=fixture.finish();store.activity.SWITCH_SECONDS=0
            first=store.read('Task A',activity_detection_valid=True)['working_context']
            store.read('Task B',activity_detection_valid=True)
            second=store.read('Task B',activity_detection_valid=True)['working_context']
        self.assertEqual((first['project'],first['tokens']['total_tokens']),('Alpha',110))
        self.assertEqual((second['project'],second['tokens']['total_tokens']),('Beta',220))

    def test_missing_project_metadata_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=ContextFixture(directory)
            fixture.add('a','Task A',120)
            context=fixture.finish().read('Task A',activity_detection_valid=True)['working_context']
        self.assertIsNone(context['project'])
        self.assertEqual(context['project_source'],'unavailable')

    def test_completed_session_cannot_steal_context(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=ContextFixture(directory);now=time.time()
            fixture.add('done','Finished',330,'project-done','Finished Project',working=False,mtime=now)
            fixture.add('live','Working',140,'project-live','Live Project',mtime=now-1)
            context=fixture.finish().read('Unknown Task',activity_detection_valid=True)['working_context']
        self.assertEqual((context['thread'],context['project'],context['tokens']['total_tokens']),
                         ('live','Live Project',140))

    def test_project_identity_uses_repository_then_directory_without_exposing_path(self):
        name,source,_=project_identity({'id':'a','git_origin_url':'https://github.com/acme/petoken.git'}, {})
        self.assertEqual((name,source),('petoken','git_origin'))
        name,source,_=project_identity({'id':'b','cwd':r'D:\Documents\3D-Portfolio'}, {})
        self.assertEqual((name,source),('3D-Portfolio','cwd_basename'))


if __name__=='__main__':unittest.main()
