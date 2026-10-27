"""Pre-publication check for the source-only skill (not a license audit)."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BINARY_SUFFIXES = {'.exe', '.dll', '.pyd', '.pyc', '.zip', '.7z', '.whl'}
PRIVATE_PATH = re.compile(r'(?i)\b[A-Z]:\\(?:Users\\|wx\\|vcchat\\)')
ACCOUNT_ID = re.compile(r'wxid_[0-9a-zA-Z]{15,}')
paths = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                       cwd=ROOT, capture_output=True, check=True).stdout.split(b'\0')
problems = []
seen = 0
for item in paths:
    if not item:
        continue
    rel = Path(item.decode('utf-8', 'surrogateescape'))
    path = ROOT / rel
    if not path.is_file():
        continue
    seen += 1
    if any(p in ('runtime', '__pycache__', '.venv', '.pytest_cache') for p in rel.parts):
        problems.append((str(rel), '打包运行目录或缓存不应发布'))
        continue
    if path.name.lower() in ('keys.json', 'voice_asr_cache.json') or path.suffix.lower() in ('.db', '.log'):
        problems.append((str(rel), '疑似个人数据/密钥'))
        continue
    if path.suffix.lower() in BINARY_SUFFIXES or path.stat().st_size > 1024 * 1024:
        problems.append((str(rel), '源码仓库包含二进制或异常大文件'))
        continue
    try:
        text = path.read_text(encoding='utf-8-sig')
    except UnicodeError:
        problems.append((str(rel), '非 UTF-8 文本'))
        continue
    if PRIVATE_PATH.search(text) or ACCOUNT_ID.search(text):
        problems.append((str(rel), '疑似个人路径或账号标识'))
manifest_path = ROOT / 'scripts' / 'upstream_source.json'
try:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (manifest.get('version') != '1.4.0' or
            set(manifest.get('sha256', {})) != {'exporter_core.py', 'wechat_data_dirs.py'}):
        problems.append(('scripts/upstream_source.json', '源码清单版本或文件集合不符'))
    else:
        for name, digest in manifest['sha256'].items():
            with (ROOT / 'scripts' / name).open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                    problems.append((f'scripts/{name}', '与固定的上游源码散列不符'))
except (OSError, ValueError, TypeError, KeyError):
    problems.append(('scripts/upstream_source.json', '源码清单缺失或不可读取'))
if problems:
    for rel, reason in problems[:30]:
        print(f'FAIL {rel}: {reason}')
    raise SystemExit(f'发布检查失败：{len(problems)} 项；不显示敏感文本。')
print(f'发布检查通过：{seen} 个源码文件；未发现预设的个人信息、打包运行目录或二进制。')
