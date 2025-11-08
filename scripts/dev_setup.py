import os
import sys
import subprocess
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT/'.venv'
PY = sys.executable

def run(cmd, check=True, **kw):
    print('[cmd]', ' '.join(cmd))
    return subprocess.run(cmd, check=check, **kw)

def ensure_venv():
    if not VENV.exists():
        run([PY, '-m', 'venv', str(VENV)])
    vp = VENV / ('Scripts' if os.name=='nt' else 'bin') / ('python.exe' if os.name=='nt' else 'python')
    if not vp.exists():
        print('virtualenv not created correctly'); sys.exit(1)
    return str(vp)

def merge_env():
    example = ROOT/'config'/'.env.dev.example'
    target = ROOT/'.env'
    def parse(path):
        d={}
        if not path.exists(): return d
        for line in path.read_text(encoding='utf-8',errors='ignore').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v = line.split('=',1)
            d[k.strip()] = v.strip()
        return d
    src=parse(example); dst=parse(target)
    for k,v in src.items():
        if k not in dst or dst[k]=='': dst[k]=v
    if not dst.get('SERVICE_API_KEY'):
        dst['SERVICE_API_KEY']=secrets.token_urlsafe(32)
    target.write_text('\n'.join(f"{k}={v}" for k,v in dst.items())+'\n',encoding='utf-8')
    print('Wrote .env with', len(dst), 'keys')

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--no-venv', action='store_true')
    p.add_argument('--no-tests', action='store_true')
    p.add_argument('--start', action='store_true')
    args=p.parse_args()

    vpy = PY
    if not args.no_venv:
        vpy = ensure_venv()
        run([vpy,'-m','ensurepip','--upgrade'])
        run([vpy,'-m','pip','install','-U','pip','wheel','setuptools'])
        if (ROOT/'requirements.txt').exists():
            run([vpy,'-m','pip','install','-r',str(ROOT/'requirements.txt')])
    merge_env()
    if (ROOT/'check_config.py').exists():
        run([vpy, str(ROOT/'check_config.py')], check=False)
    if not args.no_tests:
        run([vpy,'-m','pip','install','pytest'], check=False)
        run([vpy,'-m','pytest','-q'], check=False)
    if args.start:
        if (ROOT/'start_api.py').exists():
            subprocess.Popen([vpy, str(ROOT/'start_api.py')])
        if (ROOT/'start_web.py').exists():
            subprocess.Popen([vpy, str(ROOT/'start_web.py')])
        print('Services starting at http://localhost:8000')

if __name__=='__main__':
    main()

