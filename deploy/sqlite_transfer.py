"""Explicit SQLite import/backup, independent of application startup and credentials."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile


def copy_database(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if source == destination:
        raise ValueError('Source and destination must be different files')
    if destination.exists():
        raise FileExistsError('Destination exists; choose a new backup or an unused application volume')
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.sqlite-transfer-', dir=destination.parent)
    os.close(handle)
    temporary_path = Path(temporary)
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
            if src.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Source SQLite integrity check failed')
            with closing(sqlite3.connect(temporary_path)) as dst:
                src.backup(dst)
                dst.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        # Hard-link publication fails rather than overwriting a competing destination.
        os.link(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['import', 'backup'])
    parser.add_argument('path', type=Path, help='Import source or new backup destination')
    args = parser.parse_args()
    database = Path(os.environ.get('AI4BRAIN_DB', '/var/lib/ai4brain/ai4brain.sqlite3'))
    source, destination = (args.path, database) if args.operation == 'import' else (database, args.path)
    copy_database(source, destination)
    print('SQLite ' + args.operation + ' complete. Existing databases were not overwritten.')


if __name__ == '__main__':
    main()
