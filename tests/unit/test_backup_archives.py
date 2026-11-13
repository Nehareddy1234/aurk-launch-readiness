from io import BytesIO
import json
from pathlib import Path
import tarfile
import pytest
from scripts.backup_archive import checksum, pack_backup, extract_backup


def manifest_for(bundle):
    manifest=bundle.with_suffix('.json')
    manifest.write_text(json.dumps({'sha256':checksum(bundle)}),encoding='utf-8')
    return manifest


def test_backup_roundtrip_preserves_sql_and_upload_bytes(tmp_path):
    dump=tmp_path/'input.sql';dump.write_bytes(b'CREATE TABLE sample (id INT);')
    uploads=tmp_path/'media';(uploads/'products').mkdir(parents=True)
    (uploads/'products'/'sample.webp').write_bytes(b'example-upload')
    bundle=tmp_path/'store.tar.gz'
    pack_backup(dump,uploads,bundle)
    restored=extract_backup(bundle,manifest_for(bundle),tmp_path/'restored')
    assert (restored/'database.sql').read_bytes()==dump.read_bytes()
    assert (restored/'uploads/products/sample.webp').read_bytes()==b'example-upload'
    with pytest.raises(ValueError,match='new directory'):
        extract_backup(bundle,manifest_for(bundle),restored)


@pytest.mark.parametrize('kind',['traversal','absolute','symlink','hardlink','duplicate','unexpected','missing_sql','windows_path'])
def test_restore_rejects_unsafe_archive_before_extracting(tmp_path,kind):
    bundle=tmp_path/'bad.tar.gz'
    with tarfile.open(bundle,'w:gz') as tar:
        root=tarfile.TarInfo('uploads');root.type=tarfile.DIRTYPE;tar.addfile(root)
        if kind!='missing_sql':
            sql=tarfile.TarInfo('database.sql');sql.size=1;tar.addfile(sql,BytesIO(b'1'))
        names={'traversal':'uploads/../../escape','absolute':'/escape','duplicate':'database.sql','unexpected':'other/secret','windows_path':'uploads\\..\\escape'}
        if kind in names:
            item=tarfile.TarInfo(names[kind]);item.size=1;tar.addfile(item,BytesIO(b'x'))
        elif kind in {'symlink','hardlink'}:
            item=tarfile.TarInfo('uploads/link');item.type=tarfile.SYMTYPE if kind=='symlink' else tarfile.LNKTYPE
            item.linkname='../database.sql';tar.addfile(item)
    with pytest.raises(ValueError):extract_backup(bundle,manifest_for(bundle),tmp_path/'restore')
    assert not (tmp_path/'restore').exists()


def test_corrupt_checksum_prevents_restore(tmp_path):
    bundle=tmp_path/'bad.tar.gz';bundle.write_bytes(b'not an archive')
    manifest=tmp_path/'manifest.json';manifest.write_text('{"sha256":"wrong"}')
    with pytest.raises(ValueError,match='checksum'):
        extract_backup(bundle,manifest,tmp_path/'restored')
    assert not (tmp_path/'restored').exists()


def test_backup_refuses_destination_inside_uploads(tmp_path):
    dump=tmp_path/'input.sql';dump.write_bytes(b'1')
    with pytest.raises(ValueError,match='inside uploads'):
        pack_backup(dump,tmp_path,tmp_path/'self.tar.gz')
