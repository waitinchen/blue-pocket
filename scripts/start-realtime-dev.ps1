Param(
  [switch]$SkipTests,
  [switch]$SkipStart
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg){ Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

Write-Info 'Detecting Python...'
$py = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue) }
if (-not $py) { Write-Err 'Python not found. Please install Python 3.10+.'; exit 1 }

Write-Info 'Detecting Node.js / npm...'
$node = (Get-Command node -ErrorAction SilentlyContinue)
$npm = (Get-Command npm -ErrorAction SilentlyContinue)
if (-not $node -or -not $npm) {
  Write-Err 'Node.js (with npm) not found. Install Node.js 18+ before running realtime dev.'
  exit 1
}

function RunPython($args){
  if (Get-Command py -ErrorAction SilentlyContinue) { py $args }
  else { python $args }
}

Write-Info 'Ensuring virtual environment (.venv)'
if (-not (Test-Path .venv)) { RunPython '-m venv .venv' }
$venvPy = Join-Path (Join-Path .venv 'Scripts') 'python.exe'
if (-not (Test-Path $venvPy)) { Write-Err 'Virtualenv not created correctly.'; exit 1 }

Write-Info 'Upgrading pip'
& $venvPy -m ensurepip --upgrade | Out-Null
& $venvPy -m pip install --upgrade pip wheel setuptools | Out-Null

Write-Info 'Installing requirements.txt'
if (Test-Path requirements.txt) {
  & $venvPy -m pip install -r requirements.txt
} else {
  Write-Warn 'requirements.txt not found, skipping install.'
}

Write-Info 'Generating/merging .env from config/.env.dev.example'
if (-not (Test-Path 'scripts')) { New-Item -ItemType Directory -Path 'scripts' | Out-Null }
$genScript = Join-Path 'scripts' 'generate_env.py'
@'
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

# merge, keep existing values in dst
for k,v in src.items():
    if k not in dst or dst[k] == '':
        dst[k] = v

# ensure SERVICE_API_KEY
if 'SERVICE_API_KEY' not in dst or not dst['SERVICE_API_KEY']:
    dst['SERVICE_API_KEY'] = secrets.token_urlsafe(32)

with target.open('w', encoding='utf-8') as f:
    for k,v in dst.items():
        f.write(f"{k}={v}\n")
print('Wrote .env with', len(dst), 'keys')
'@ | Set-Content -Path $genScript -Encoding UTF8

& $venvPy $genScript

Write-Info 'Checking environment with check_config.py'
if (Test-Path 'check_config.py') {
  & $venvPy check_config.py
} else {
  Write-Warn 'check_config.py not found; skipping env checks.'
}

if (-not $SkipTests) {
  Write-Info 'Running tests (pytest -q)'
  & $venvPy -m pip install pytest -q | Out-Null
  try {
    & $venvPy -m pytest -q
  } catch {
    Write-Err 'Tests failed.'
  }
} else { Write-Warn 'SkipTests enabled, not running tests.' }

Write-Info 'Installing frontend dependencies (npm install)'
Push-Location 'frontend'
try {
  & $npm.Source install
} catch {
  Pop-Location
  Write-Err 'npm install failed.'
  exit 1
}
$envTemplate = Join-Path (Get-Location) 'env.local.template'
$envTarget = Join-Path (Get-Location) '.env.local'
if ((Test-Path $envTemplate) -and -not (Test-Path $envTarget)) {
  Write-Info 'Creating frontend .env.local from template'
  Copy-Item $envTemplate $envTarget
}
Pop-Location

if (-not $SkipStart) {
  Write-Info 'Starting API and Web...'
  $apiCmd = "$venvPy start_api.py"
  $webCmd = "$venvPy start_web.py"
  if (Test-Path 'start_api.py') { Start-Process -NoNewWindow -FilePath $venvPy -ArgumentList 'start_api.py' }
  if (Test-Path 'start_web.py') { Start-Process -NoNewWindow -FilePath $venvPy -ArgumentList 'start_web.py' }
  $frontendPath = Join-Path (Get-Location) 'frontend'
  Start-Process -NoNewWindow -FilePath $npm.Source -ArgumentList 'run','dev','--','--host','0.0.0.0' -WorkingDirectory $frontendPath
  Write-Host "API/Web starting. Visit http://localhost:8000" -ForegroundColor Green
  Write-Host "Frontend starting. Visit http://localhost:5173" -ForegroundColor Green
} else { Write-Warn 'SkipStart enabled, not starting services.' }

Write-Info 'Done.'

