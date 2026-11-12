"""Create source + consistent user data archives; no dependencies or credentials."""
import json
import os
from pathlib import Path
import sqlite3
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'deploy'
OUT.mkdir(parents=True, exist_ok=True)

source = OUT / 'fitness-release.tar.gz'
with tarfile.open(str(source), 'w:gz') as archive:
    for folder in ('backend', 'frontend', 'scripts', 'docs'):
        for directory, children, files in os.walk(str(ROOT / folder), followlinks=False):
            children[:] = [name for name in children if name not in ('node_modules', '__pycache__', '.venv')]
            for name in sorted(files):
                path = Path(directory) / name
                if not path.is_symlink():
                    archive.add(str(path), arcname=path.relative_to(ROOT).as_posix(), recursive=False)
    for name in ('Dockerfile', '.dockerignore', 'compose.yaml', '.env.example', '.gitignore', 'README.md', 'start.ps1'):
        archive.add(str(ROOT / name), arcname=name, recursive=False)

database = ROOT / 'data' / 'fitness.sqlite'
seed = OUT / 'fitness-seed.tar.gz'
counts = {}
with sqlite3.connect(str(database)) as origin:
    with sqlite3.connect(str(OUT / 'seed.sqlite')) as target:
        origin.backup(target)
        target.execute('DELETE FROM sessions')
        target.execute('DELETE FROM attempts')
        counts = {name: target.execute('SELECT COUNT(*) FROM '+name).fetchone()[0]
                  for name in ('templates', 'schedule', 'records')}
with tarfile.open(str(seed), 'w:gz') as archive:
    archive.add(str(OUT / 'seed.sqlite'), arcname='fitness.sqlite')
    archive.add(str(ROOT / 'data' / 'videos'), arcname='videos')
print(json.dumps({'source': str(source), 'source_bytes': source.stat().st_size,
                  'seed': str(seed), 'seed_bytes': seed.stat().st_size, 'counts': counts}))
