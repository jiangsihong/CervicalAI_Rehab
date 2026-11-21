"""Restore the bundled pose model using only the Python standard library."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

MODEL_DIR = Path(__file__).resolve().parent


def file_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def restore(output=None):
    manifest = json.loads((MODEL_DIR / 'weights-manifest.json').read_text(encoding='utf-8'))
    target = Path(output) if output else MODEL_DIR / manifest['filename']
    if target.exists():
        if target.stat().st_size == manifest['bytes'] and file_digest(target) == manifest['sha256']:
            print('Model already verified: {}'.format(target))
            return target
        raise ValueError('Existing output does not match; it was not overwritten: {}'.format(target))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='pose-restore-', suffix='.tmp', dir=str(target.parent), delete=False) as dest:
            temporary = Path(dest.name)
            combined_hash = hashlib.sha256()
            combined_size = 0
            for part in manifest['parts']:
                part_path = MODEL_DIR / part['name']
                part_hash = hashlib.sha256()
                part_size = 0
                with part_path.open('rb') as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        dest.write(chunk)
                        part_hash.update(chunk)
                        combined_hash.update(chunk)
                        part_size += len(chunk)
                if part_size != part['bytes'] or part_hash.hexdigest() != part['sha256']:
                    raise ValueError('Model part checksum mismatch: {}'.format(part_path))
                combined_size += part_size
            if combined_size != manifest['bytes'] or combined_hash.hexdigest() != manifest['sha256']:
                raise ValueError('Combined model checksum mismatch')
        if os.name == 'nt':
            temporary.rename(target)
        else:
            os.link(str(temporary), str(target))
            temporary.unlink()
        temporary = None
        print('Model restored and SHA-256 verified: {}'.format(target))
        return target
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional output path; defaults to pose-estimator.h5 next to this script')
    args = parser.parse_args()
    try:
        restore(args.output)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, 'Model restore failed: {}\n'.format(exc))
