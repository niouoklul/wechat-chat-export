"""Bounded metadata-only discovery for WeChat data beside a custom install."""
from pathlib import Path
from itertools import islice

DATA_NAMES = ('xwechat_files', 'WeChat Files', 'xwechat_files_data')
EXECUTABLES = ('Weixin.exe', 'WeChat.exe')


def installation_bases():
    """Use running installs first; fall back to fixed-drive first-level installs."""
    bases = {}
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if (proc.info['name'] or '').lower() not in ('weixin.exe', 'wechat.exe'):
                    continue
                exe = proc.info['exe']
                if exe and Path(exe).name.lower() in ('weixin.exe', 'wechat.exe'):
                    base = Path(exe).parent.parent
                    bases[str(base).casefold()] = base
            except (psutil.Error, OSError):
                continue
    except (ImportError, OSError):
        pass

    from wechat_data_dirs import _fixed_drive_roots
    for drive in _fixed_drive_roots():
        try:
            children = list(islice(drive.iterdir(), 512))
        except OSError:
            continue
        for child in children:
            try:
                if not child.is_dir():
                    continue
                if any((child / folder / exe).is_file()
                       for folder in ('Weixin', 'WeChat') for exe in EXECUTABLES):
                    bases[str(child).casefold()] = child
            except OSError:
                continue
    return list(bases.values())


def adjacent_data_roots(bases=None):
    """At most one level below each install's parent; do not search file contents."""
    from wechat_data_dirs import _resolve_account_root
    roots = {}
    for base in installation_bases() if bases is None else bases:
        try:
            children = list(islice(base.iterdir(), 128))
        except OSError:
            continue
        parents = [base]
        for child in children:
            try:
                if child.is_dir():
                    parents.append(child)
            except OSError:
                continue
        for parent in parents:
            for name in DATA_NAMES:
                root = _resolve_account_root(parent / name)
                if root is not None:
                    roots[str(root).casefold()] = root
    return list(roots.values())


def discover_data_roots():
    """Combine upstream configuration/registry discovery with install-adjacent roots."""
    import wechat_data_dirs as dirs
    found = dirs.discover_wechat_data_dirs()
    seen = {str(Path(row['path']).resolve()).casefold() for row in found}
    for root in adjacent_data_roots():
        key = str(root.resolve()).casefold()
        if key not in seen:
            found.append(dirs._inspect_root(root, {'安装目录周边'}, None))
            seen.add(key)
    return found



