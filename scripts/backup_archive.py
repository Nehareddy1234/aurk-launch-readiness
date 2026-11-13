"""Small, independently testable archive boundary for trusted store backups."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile


def checksum(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pack_backup(dump, uploads, bundle):
    dump, uploads, bundle = map(Path, (dump, uploads, bundle))
    if dump.is_symlink() or uploads.is_symlink() or not dump.is_file() or not uploads.is_dir():
        raise ValueError('Backup inputs must be regular SQL and upload paths')
    if bundle.resolve().is_relative_to(uploads.resolve()):
        raise ValueError('Backup destination cannot be inside uploads')
    def safe_member(member):
        if not (member.isfile() or member.isdir()):
            raise ValueError('Refusing non-regular upload entry')
        return member
    with tarfile.open(bundle, 'w:gz') as archive:
        archive.add(dump, arcname='database.sql', filter=safe_member)
        archive.add(uploads, arcname='uploads', filter=safe_member)
    return checksum(bundle)


def extract_backup(bundle, manifest, scratch):
    bundle, manifest, scratch = map(Path, (bundle, manifest, scratch))
    metadata = json.loads(manifest.read_text(encoding='utf-8'))
    if checksum(bundle) != metadata.get('sha256'):
        raise ValueError('Backup checksum mismatch')
    scratch = scratch.resolve()
    if scratch.exists():
        raise ValueError('Restore destination must be a new directory')
    with tarfile.open(bundle, 'r:gz') as archive:
        members = archive.getmembers()
        seen = set()
        for member in members:
            name = PurePosixPath(member.name)
            target = (scratch / member.name).resolve()
            if (not name.parts or name.is_absolute() or '..' in name.parts or '\\' in member.name
                    or ':' in member.name or not target.is_relative_to(scratch)
                    or not (member.isfile() or member.isdir()) or member.name in seen
                    or (member.name != 'database.sql' and name.parts[0] != 'uploads')):
                raise ValueError('Unsafe backup archive entry')
            if member.name == 'database.sql' and not member.isfile():
                raise ValueError('Backup SQL must be a regular file')
            seen.add(member.name)
        if 'database.sql' not in seen or 'uploads' not in seen:
            raise ValueError('Backup lacks SQL or uploads')
        if sum(m.size for m in members) + 1024**3 > shutil.disk_usage(scratch.parent).free:
            raise ValueError('Insufficient restore disk space including 1 GiB reserve')
        scratch.mkdir(exist_ok=False, mode=0o700)
        archive.extractall(scratch, filter='data')
    return scratch
