#!/usr/bin/env python3
from pathlib import Path
import sys

OLD="furina-2026.08.21-rc62-rc50"
NEW="furina-2026.08.21-rc63-rc51"

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: apply.py <furina-root>')
    root=Path(sys.argv[1]).resolve(); core=root/'core/furina_agent'
    version=core/'version.py'; hub=core/'hub.py'
    if not version.is_file() or not hub.is_file(): raise SystemExit('RC63 source missing')
    v=version.read_text(); h=hub.read_text()
    if 'VERSION = "1.0.0-rc62"' not in v: raise SystemExit('RC63 version marker missing')
    v=v.replace('VERSION = "1.0.0-rc62"','VERSION = "1.0.0-rc63"',1)
    if OLD not in h: raise SystemExit('RC63 bundle marker missing')
    h=h.replace(OLD,NEW).replace('"bridge_target": "1.0.0-rc50"','"bridge_target": "1.0.0-rc51"')
    h=h.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.21-r31"','EXPECTED_DEPENDENCY_REVISION = "2026.08.21-r33"')
    for marker in (NEW,'"bridge_target": "1.0.0-rc51"','EXPECTED_DEPENDENCY_REVISION = "2026.08.21-r33"'):
        if marker not in h: raise SystemExit(f'RC63 integration incomplete: {marker}')
    version.write_text(v); hub.write_text(h)
    print('FURINA_RC63_ATOMIC_BUNDLE_STATUS_OK')

if __name__=='__main__': main()
