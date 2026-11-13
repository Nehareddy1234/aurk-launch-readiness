"""Linux consistent MySQL + upload backup; upload privately to a configured S3 bucket.
Run while the app and notification worker are stopped for a maintenance window.
Credentials remain in a chmod-600 MySQL defaults file, never process arguments.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
try:
    from .backup_archive import pack_backup
except ImportError:
    from backup_archive import pack_backup


def run(*args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mysql-defaults',required=True,type=Path)
    parser.add_argument('--database',required=True)
    parser.add_argument('--uploads',required=True,type=Path)
    parser.add_argument('--destination',required=True,type=Path)
    parser.add_argument('--s3',required=True,help='Private s3://bucket/prefix')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_]+',args.database): parser.error('Invalid database name')
    if not re.fullmatch(r's3://[a-z0-9][a-z0-9.-]+/[A-Za-z0-9/_-]*',args.s3): parser.error('Use an S3 bucket and safe prefix')
    defaults=args.mysql_defaults.resolve()
    if not defaults.is_file() or defaults.stat().st_mode & 0o077: parser.error('MySQL defaults must be a private chmod-600 file')
    uploads=args.uploads.resolve(strict=True)
    if not uploads.is_dir(): parser.error('Uploads must be a directory')
    for service in ('aurk.service','aurk-notifications.service','aurk-customer-emails.service','aurk-customer-emails.timer','aurk-notifications.timer'):
        if subprocess.run(['systemctl','is-active','--quiet',service]).returncode==0:
            parser.error('Stop the app and notification worker for a consistent backup')
    os.umask(0o077)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target=args.destination.resolve()/stamp
    target.mkdir(parents=True,exist_ok=False)
    dump=target/'database.sql'
    with dump.open('wb') as stream:
        run('mysqldump',f'--defaults-extra-file={defaults}','--single-transaction','--quick','--no-tablespaces','--set-gtid-purged=OFF','--hex-blob',args.database,stdout=stream)
    bundle=target/'store.tar.gz'
    digest=pack_backup(dump, uploads, bundle)
    meta=target/'manifest.json'
    meta.write_text(json.dumps({'created_at':stamp,'database':args.database,'sha256':digest,'file':bundle.name}))
    bucket=args.s3[5:].split('/')[0]
    block=run('aws','s3api','get-public-access-block','--bucket',bucket,capture_output=True,text=True)
    settings=json.loads(block.stdout)['PublicAccessBlockConfiguration']
    if not all(settings.get(k) for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets')):
        raise RuntimeError('Enable all S3 Block Public Access settings before backing up customer data')
    destination=args.s3.rstrip('/')+'/'+stamp+'/'
    for path in (bundle,meta): run('aws','s3','cp',str(path),destination+path.name,'--sse','AES256','--only-show-errors')
    # Remove only the intermediate SQL after the archive and off-server copy succeed.
    dump.unlink()
    print('Private backup completed:',stamp)


if __name__=='__main__': main()
