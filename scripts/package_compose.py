"""Build a complete runtime source ZIP without secrets, learner data or local caches."""
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'output' / 'packages' / 'AI4BRAIN-Docker-Compose.zip'


def source_files() -> list[Path]:
    selected = {
        ROOT / name for name in [
            'compose.yaml', '.dockerignore', '.env.example', 'README.md', 'docs/DOCKER.md',
            'scripts/compose-up.ps1', 'scripts/package_compose.py',
            'scripts/setup.ps1', 'scripts/start.ps1', 'scripts/stop.ps1',
            'scripts/backend_smoke.py', 'scripts/battery_smoke.py',
            'scripts/personalization_smoke.py', 'scripts/coach_v2_smoke.py',
            'scripts/collaboration_v2_smoke.py', 'scripts/dashboard_smoke.py',
            'scripts/r4_case_manifest.py', 'scripts/r5_recovery_matrix.py',
            'scripts/r7_rejudge_fixes_smoke.py', 'scripts/docker_package_smoke.py',
            'scripts/generalisation_eval.py',
            'docs/REQUIREMENTS.md', 'docs/CONTRACTS.md',
            'docs/submission/AI4BRAIN-Technical-Report.pdf',
            'docs/submission/AI4BRAIN-Pitch.pptx', 'docs/submission/demo-script.md',
            'output/verification/generalisation-rejudge-2026-10-22/REPORT.md',
            'output/verification/docker-compose-2026-10-22/REPORT.md',
            'tests/generalisation/manifest.json', 'tests/generalisation/FREEZE.json',
        ]
    }
    for pattern in ['backend/**/*.py', 'backend/requirements*.txt', 'frontend/src/**/*',
                    'frontend/public/**/*', 'frontend/package*.json', 'frontend/tsconfig*.json',
                    'frontend/index.html', 'frontend/vite.config.ts', 'deploy/**/*']:
        selected.update(ROOT.glob(pattern))
    return sorted(p for p in selected if p.is_file() and not p.is_symlink()
                  and '__pycache__' not in p.parts and p.suffix != '.pyc')


def build() -> dict:
    files = source_files()
    entries = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in files}
    # The runtime image/package must never carry this checkout's actual credentials.
    from dotenv import dotenv_values
    secrets = [str(value).encode() for key, value in dotenv_values(ROOT / '.env').items()
               if value and (key.endswith('_KEY') or key.endswith('_PASSWORD'))
               and value != 'replace-with-local-password' and len(str(value)) >= 8]
    if any(secret in content for content in entries.values() for secret in secrets):
        raise RuntimeError('A credential was found in the selected package files; packaging stopped')
    manifest = {name: hashlib.sha256(content).hexdigest() for name, content in entries.items()}
    entries['PACKAGE_MANIFEST.json'] = (json.dumps({
        'package': 'AI4BRAIN Docker Compose runtime source',
        'scope': 'Clean source, assets and deployment files; no learner history, credentials, prebuilt Docker images or model cache',
        'files_sha256': manifest,
    }, indent=2) + '\n').encode()
    payload = io.BytesIO()
    with ZipFile(payload, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
        for name, content in entries.items():
            archive.writestr('AI4BRAIN/' + name, content)
    data = payload.getvalue()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(data)
    result = {'path': str(TARGET), 'files': len(entries), 'bytes': len(data),
              'sha256': hashlib.sha256(data).hexdigest(), 'secret_scan': 'PASS'}
    TARGET.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    return result


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
