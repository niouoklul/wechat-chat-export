"""Offline source/backend/entrypoint check; never probes WeChat."""
import json
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

if platform.system() != 'Windows' or sys.maxsize < 2**32 or sys.version_info[:2] not in ((3, 12),):
    raise RuntimeError('需要 64 位 Windows Python 3.12。')
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_one import verify_assets
verify_assets()
for requirement in (Path(__file__).parents[1] / 'requirements.txt').read_text(encoding='ascii').splitlines():
    if not requirement or requirement.startswith('#'):
        continue
    package, separator, expected = requirement.partition('==')
    if not separator or version(package) != expected:
        raise RuntimeError(f'依赖版本不匹配：{package}；请运行 scripts/setup.ps1。')
import exporter_core
import wechat_data_dirs
for entry in ('list_chats.py', 'export_one.py'):
    result = subprocess.run([sys.executable, '-B', '-I', '-X', 'utf8',
                             str(Path(__file__).parent / entry), '--help'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(f'{entry} 启动失败：{result.stderr.strip()[:500]}')
print(json.dumps({'status': 'ok', 'backend_version': exporter_core.APP_VERSION,
                  'dependency_version': version('wechatauto-replica'),
                  'message': '依赖与导出源码检查通过；未读取微信。'}, ensure_ascii=False))

