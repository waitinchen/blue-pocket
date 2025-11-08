import os, secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
example = root / 'config' / '.env.dev.example'
target = root / '.env'

def parse_env(path):
    data = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,v = line.split('=',1)
        data[k.strip()] = v.strip()
    return data

src = parse_env(example)
dst = parse_env(target)

for k,v in src.items():
    if k not in dst or dst[k] == '':
        dst[k] = v

if 'SERVICE_API_KEY' not in dst or not dst['SERVICE_API_KEY']:
    dst['SERVICE_API_KEY'] = secrets.token_urlsafe(32)

with target.open('w', encoding='utf-8') as f:
    for k,v in dst.items():
        f.write(f"{k}={v}\n")
print('Wrote .env with', len(dst), 'keys')

