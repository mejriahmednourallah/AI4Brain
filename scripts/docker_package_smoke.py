"""Meaningful SQLite transfer checks using disposable WAL-backed records only."""
from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sqlite_transfer', ROOT / 'deploy/sqlite_transfer.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory(prefix='ai4brain-compose-') as folder:
    root = Path(folder)
    source, target = root / 'live.sqlite3', root / 'backups' / 'snapshot.sqlite3'
    with closing(sqlite3.connect(source)) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE evidence(id TEXT PRIMARY KEY, payload TEXT)')
        db.execute("INSERT INTO evidence VALUES('qa-event', 'isolated committed WAL record')")
        db.execute("CREATE TRIGGER immutable_evidence BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT,'immutable'); END")
        db.commit()
        module.copy_database(source, target)
        with closing(sqlite3.connect(target)) as copied:
            assert copied.execute('SELECT * FROM evidence').fetchall() == [('qa-event', 'isolated committed WAL record')]
            assert copied.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0] == 1
            assert copied.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        original_bytes = target.read_bytes()
        try:
            module.copy_database(source, target)
        except FileExistsError:
            pass
        else:
            raise AssertionError('An existing database was overwritten')
        assert target.read_bytes() == original_bytes
        try:
            module.copy_database(source, source)
        except ValueError:
            pass
        else:
            raise AssertionError('Same-file import was permitted')
    invalid = root / 'invalid.sqlite3'
    invalid.write_text('not a database', encoding='utf8')
    failed_target = root / 'invalid-import.sqlite3'
    try:
        module.copy_database(invalid, failed_target)
    except sqlite3.DatabaseError:
        pass
    else:
        raise AssertionError('Invalid SQLite was accepted')
    assert not failed_target.exists()
    assert not list(root.rglob('.sqlite-transfer-*'))
print('PASS: live WAL snapshot, rows/triggers/integrity, overwrite refusal, same-file refusal and invalid-source cleanup.')
