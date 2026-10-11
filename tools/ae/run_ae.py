"""Run one After Effects scene script headless (no window): lib.jsx + the scene, joined.

    python tools/ae/run_ae.py tools/ae/reveal.jsx [more scenes...]

Needs After Effects 2022 (and the Visual C++ 2012 runtime it depends on). Output goes
to build/ae_out/<comp>/<comp>_00000.tif, a log to build/ae_out/log.txt.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AE = Path(r'D:\Program Files\Adobe After Effects 2022\Support Files')
OUT = ROOT / 'build' / 'ae_out'


def run(scenes, timeout=1800):
    OUT.mkdir(parents=True, exist_ok=True)
    lib = (Path(__file__).with_name('lib.jsx')).read_text(encoding='utf-8')
    body = '\n'.join(Path(s).read_text(encoding='utf-8') for s in scenes)
    joined = OUT / 'run.jsx'
    # ExtendScript reads a BOM-marked file as UTF-8 (the localised template names need it).
    script = ('try {\n' + lib + '\n' + body + '\n} catch (e) { log("ERROR " + e.toString() + " line " + e.line); }\n'
              'app.quit();\n')
    joined.write_text(script, encoding='utf-8-sig')
    log = OUT / 'log.txt'
    if log.exists():
        log.unlink()
    # After Effects runs one instance: a stuck earlier one would swallow this script.
    subprocess.run(['taskkill', '/F', '/IM', 'AfterFX.exe'], capture_output=True)
    started = time.time()
    process = subprocess.Popen([str(AE / 'AfterFX.exe'), '-noui', '-r', str(joined)], cwd=str(AE))
    try:
        code = process.wait(timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        code = 'timeout'
    print(f'After Effects finished ({code}) in {time.time() - started:.0f} s')
    if log.exists():
        print(log.read_text(encoding='utf-8', errors='replace')[-3000:])


if __name__ == '__main__':
    run(sys.argv[1:])
