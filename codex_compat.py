"""Read-only Codex structure probes; no transcript or credential values."""
import hashlib
import json
import re
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path


THREAD_REQUIRED = {'id': 'TEXT', 'rollout_path': 'TEXT', 'updated_at': 'INTEGER'}
THREAD_OPTIONAL = {key: 'TEXT' for key in (
    'name', 'title', 'cwd', 'model', 'reasoning_effort', 'source',
    'project_id', 'git_origin_url', 'cli_version')}
THREAD_OPTIONAL['archived'] = 'INTEGER'
TURN_REQUIRED = {'thread_id': 'TEXT', 'turn_id': 'TEXT',
                 'status': 'TEXT', 'started_at': ('INTEGER', 'REAL')}


def affinity(declaration):
    declaration = declaration.upper()
    if 'INT' in declaration:
        return 'INTEGER'
    if any(t in declaration for t in ('CHAR', 'CLOB', 'TEXT')):
        return 'TEXT'
    if not declaration or 'BLOB' in declaration:
        return 'BLOB'
    if any(t in declaration for t in ('REAL', 'FLOA', 'DOUB')):
        return 'REAL'
    return 'NUMERIC'


def inspect_table(connection, table, required, optional=None):
    optional = optional or {}
    columns = [{'name': r[1], 'type': r[2], 'affinity': affinity(r[2])}
               for r in connection.execute(f'PRAGMA table_info("{table}")')]
    fingerprint = dict(columns=columns,
        tables=sorted(r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")),
        schema_version=connection.execute('PRAGMA schema_version').fetchone()[0],
        user_version=connection.execute('PRAGMA user_version').fetchone()[0])
    fingerprint['sha256'] = hashlib.sha256(json.dumps(
        fingerprint, sort_keys=True).encode()).hexdigest()
    actual = {c['name'].lower(): c['affinity'] for c in columns}
    valid = []
    reasons = []
    for name, expected in {**required, **optional}.items():
        if name not in actual:
            reasons.append(f'missing_field:{table}:{name}')
        elif actual[name] not in (expected if isinstance(expected, tuple) else (expected,)):
            reasons.append(f'invalid_type:{table}:{name}')
        else:
            valid.append(name)
    if not columns or table not in fingerprint['tables']:
        valid = []
        reasons = [f'missing_table:{table}']
    status = ('unsupported' if not set(required).issubset(valid)
              else 'partial' if reasons else 'supported')
    return dict(status=status, reasons=reasons, fingerprint=fingerprint,
                valid_fields=valid)


def probe_database(path, table, required, optional=None):
    try:
        if path is None or not path.is_file():
            return dict(status='unsupported', reasons=[f'missing_file:{table}'],
                        fingerprint=None, valid_fields=[])
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro',
                                     uri=True, timeout=.2)) as connection:
            return inspect_table(connection, table, required, optional)
    except (OSError, ValueError, sqlite3.Error):
        return dict(status='unsupported', reasons=[f'unreadable_database:{table}'],
                    fingerprint=None, valid_fields=[])


def state_database(home):
    try:
        paths = [p for p in home.glob('state_*.sqlite')
                 if p.stem.removeprefix('state_').isdigit()]
        return max(paths, key=lambda p: int(p.stem.removeprefix('state_'))) if paths else None
    except OSError:
        return None


def installed_version():
    """Inspect the installed npm launcher, never version.json.latest_version.

    Bundled desktop writers can differ; their cli_version is reported separately.
    No executable, shell, account endpoint or update check is launched.
    """
    launcher = shutil.which('codex')
    if not launcher:
        return None
    package = Path(launcher).parent / 'node_modules' / '@openai' / 'codex' / 'package.json'
    try:
        if package.stat().st_size > 65536:
            return None
        value = json.loads(package.read_text(encoding='utf-8')).get('version')
        return version_string(value)
    except (OSError, ValueError, AttributeError):
        return None


def version_string(value):
    return value if isinstance(value, str) and len(value) < 100 and re.fullmatch(
        r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?', value) else None


def log_fingerprint(info):
    """Only field names/types are hashed; numbers and free text are not retained."""
    shape = {key: ({k: type(v).__name__ for k, v in value.items()}
                   if isinstance(value, dict) else type(value).__name__)
             for key, value in info.items()}
    return hashlib.sha256(json.dumps(shape, sort_keys=True).encode()).hexdigest()
