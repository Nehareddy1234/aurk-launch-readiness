"""Restore a downloaded backup into a NEW scratch directory and NEW local MySQL schema.
Never drops databases or replaces production uploads. A failed drill retains evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import tarfile
try:
    from .backup_archive import extract_backup
except ImportError:
    from backup_archive import extract_backup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',required=True,type=Path)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--scratch-parent',required=True,type=Path)
    parser.add_argument('--mysql-defaults',required=True,type=Path)
    args=parser.parse_args()
    defaults=args.mysql_defaults.resolve(strict=True)
    if defaults.stat().st_mode & 0o077: parser.error('MySQL defaults must have chmod 600')
    schema='aurk_restore_'+secrets.token_hex(8)
    scratch=args.scratch_parent.resolve()/schema
    scratch.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    extract_backup(args.bundle, args.manifest, scratch)
    command=['mysql',f'--defaults-extra-file={defaults}','--host=127.0.0.1','--protocol=TCP']
    subprocess.run(command+['-e',f'CREATE DATABASE `{schema}` CHARACTER SET utf8mb4'],check=True)
    with (scratch/'database.sql').open('rb') as stream:
        subprocess.run(command+[schema],stdin=stream,check=True)
    subprocess.run(command+[schema,'-e','SELECT version_num FROM alembic_version; SELECT COUNT(*) AS orders FROM orders; SELECT COUNT(*) AS products FROM products;'],check=True)
    print('Restored isolated schema:',schema)
    print('Restored uploads:',scratch/'uploads')
    print('Next: run migrations and schema checks against this schema with SMTP disabled, then verify sample media and orders.')


if __name__=='__main__': main()
