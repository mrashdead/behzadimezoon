from datetime import datetime
from pathlib import Path
import os

from django.conf import settings
from django.core import signing
from django.utils import timezone

ALLOWED_BACKUP_EXTENSION = '.dump'
SIGNING_SALT = 'dashboard-backup-download'
MAX_TOKEN_AGE_SECONDS = 600


def _get_backup_dir() -> Path:
    backup_dir = Path(settings.BACKUP_DIR)
    if not backup_dir.exists() or not backup_dir.is_dir():
        return backup_dir
    return backup_dir


def _validate_backup_name(filename: str) -> str:
    basename = Path(filename).name
    if basename != filename:
        raise ValueError('Invalid file name.')
    if not basename.endswith(ALLOWED_BACKUP_EXTENSION):
        raise ValueError('Only .dump files are allowed.')
    return basename


def generate_backup_download_token(filename: str) -> str:
    filename = _validate_backup_name(filename)
    backup_path = _get_backup_dir() / filename
    if not backup_path.exists() or not backup_path.is_file():
        raise FileNotFoundError('Backup file does not exist.')
    return signing.dumps({'filename': filename}, salt=SIGNING_SALT)


def validate_backup_download_token(token: str) -> str:
    data = signing.loads(token, max_age=MAX_TOKEN_AGE_SECONDS, salt=SIGNING_SALT)
    filename = data.get('filename')
    if not isinstance(filename, str):
        raise signing.BadSignature('Invalid token payload.')
    return _validate_backup_name(filename)


def resolve_backup_file_path(filename: str) -> Path:
    filename = _validate_backup_name(filename)
    backup_dir = _get_backup_dir().resolve()
    backup_path = (backup_dir / filename).resolve()

    if not backup_path.exists() or not backup_path.is_file():
        raise FileNotFoundError('Backup file does not exist.')

    try:
        backup_path.relative_to(backup_dir)
    except ValueError:
        raise ValueError('Backup path is outside the allowed directory.')

    if backup_path.suffix != ALLOWED_BACKUP_EXTENSION:
        raise ValueError('Only .dump files are allowed.')

    return backup_path


def list_backup_files() -> list[dict]:
    backup_dir = _get_backup_dir()
    if not backup_dir.exists() or not backup_dir.is_dir():
        return []

    backups = []
    for path in sorted(backup_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file() or path.suffix != ALLOWED_BACKUP_EXTENSION:
            continue

        backups.append({
            'name': path.name,
            'modified_at': datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.get_current_timezone()),
            'token': generate_backup_download_token(path.name),
        })

    return backups
