"""Single-conversation CLI for the pinned open-source exporter. No batch entrypoint."""
import argparse
import contextlib
import hashlib
import json

import sys
import uuid
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from process_access import ProcessCheckError, check_weixin_process


def verify_assets():
    """Check the source backend and exact pip package used by this skill."""
    from importlib.metadata import version
    if version('wechatauto-replica') != '1.2.4.4':
        raise RuntimeError('需要 wechatauto-replica==1.2.4.4，请运行 scripts/setup.ps1。')
    manifest = json.loads((Path(__file__).parent / 'upstream_source.json').read_text(encoding='utf-8'))
    expected = {'exporter_core.py', 'wechat_data_dirs.py'}
    if set(manifest.get('sha256', {})) != expected:
        raise RuntimeError('上游源码清单不完整。')
    for filename, digest in manifest['sha256'].items():
        with (Path(__file__).parent / filename).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise RuntimeError(f'上游源码与固定版本不符：{filename}')
    import exporter_core
    if exporter_core.APP_VERSION != manifest['version']:
        raise RuntimeError('导出源码版本不匹配。')


def absolute_local_dir(text):
    p = Path(text).expanduser()
    if not p.is_absolute() or str(p).startswith('\\\\'):
        raise ValueError('输出目录必须是本机绝对路径，不能使用网络共享。')
    return p.resolve()


def discover_wechat_db_dir(core, requested_dir=None):
    """Combine original discovery with bounded install-adjacent probing."""
    if requested_dir:
        return Path(core.resolve_db_dir(requested_dir)).resolve()
    from discover_data import discover_data_roots
    candidates = discover_data_roots()
    if not candidates:
        raise ValueError('未自动发现微信数据目录；请在微信设置中确认数据位置，再传入 --db-dir。')
    if len(candidates) == 1:
        chosen = candidates[0]
    else:
        auto = [item for item in candidates if item.get('auto_selected')]
        if len(auto) != 1:
            raise SelectionNeeded('发现多个微信数据目录，无法唯一确定，请选定一个绝对路径。', [
                {'db_dir': item.get('path'), 'account_count': item.get('account_count'),
                 'latest_text': item.get('latest_text'), 'sources': item.get('sources')}
                for item in candidates
            ])
        chosen = auto[0]
    return Path(core.resolve_db_dir(chosen['path'])).resolve()


class SelectionNeeded(Exception):
    def __init__(self, reason, candidates):
        self.reason, self.candidates = reason, candidates[:20]
        super().__init__(reason)


def exact_contact(db, name):
    """Resolve only reliably identified chats with local message tables.

    A session-only chat can be listed without a contact row; conversely an
    ordinary contact with no message table must not become an export target.
    """
    import exporter_core as core
    chats, _ = core._batch_chat_candidates(db)
    if not chats:
        raise SelectionNeeded('没有找到可可靠识别的本机会话。', [])
    known = {item['username']: item for item in chats}
    details = {}
    connection = db._contact_conn()
    if connection is not None:
        with contextlib.closing(connection) as conn:
            for username, nick, remark in conn.execute(
                'SELECT username,nick_name,remark FROM contact'
            ):
                if username in known:
                    details[username] = (nick or '', remark or '')

    entries = []
    for username, chat in known.items():
        nick, remark = details.get(username, ('', ''))
        display = remark or nick or chat.get('name') or username
        entries.append({
            'username': username,
            'nick_name': nick or (display if not remark else ''),
            'remark': remark,
            'name': display,
            'type': '群聊' if chat.get('is_group') else '私聊',
            '_match_names': (remark, nick, chat.get('name')),
        })
    # The stable identity always takes precedence over someone else's label.
    for item in entries:
        if item['username'] == name:
            return {key: value for key, value in item.items() if key != '_match_names'}
    matches = [item for item in entries if name in item['_match_names']]
    if len(matches) == 1:
        return {key: value for key, value in matches[0].items() if key != '_match_names'}
    if len(matches) > 1:
        raise SelectionNeeded('同名会话不止一个，请使用列表中的唯一 username 重新确认。', [
            {key: value for key, value in item.items() if key != '_match_names'}
            for item in matches[:20]
        ])
    suggestions = [
        {key: value for key, value in item.items() if key != '_match_names'}
        for item in entries
        if any(name.casefold() in str(value).casefold()
               for value in (item['username'], *item['_match_names']) if value)
    ]
    raise SelectionNeeded('未找到完全匹配且有本地消息表的会话。', suggestions[:20])


def summarize_export(result, fallback_name):
    """Return operational metadata only, never any message body."""
    if not isinstance(result, dict):
        raise RuntimeError('导出器没有返回有效结果。')
    fields = ('message_count', 'output_dir', 'txt', 'md', 'json',
              'media_stats', 'sender_resolution_counts', 'sensitive_cache_cleanup')
    summary = {key: result[key] for key in fields if key in result}
    summary['name'] = result.get('chat_name') or fallback_name
    if result.get('sensitive_cache_cleanup') is False:
        summary['cleanup_warning'] = '敏感临时目录未能完全清理，请检查本机临时目录。'
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description='只导出一个本机微信私聊或群聊。')
    parser.add_argument('--name', required=True, help='精确备注、昵称、群名或 username')
    parser.add_argument('--output-base', required=True, help='用户指定的本机绝对输出目录')
    parser.add_argument('--db-dir', help='微信数据目录；不填则由后端自动探测')
    parser.add_argument('--account', help='多账号时须明确指定账号目录名')
    parser.add_argument('--text-only', action='store_true')
    parser.add_argument('--confirm', required=True, help='只有用户在单独回合明确确认后才传入“确认”')
    args = parser.parse_args(argv)
    if args.confirm != '确认导出': parser.error('必须在展示导出计划并得到用户后续确认后执行。')
    name = args.name.strip()
    if not name or len(name) > 256 or '\x00' in name: parser.error('名称无效。')
    try:
        base = absolute_local_dir(args.output_base)
        verify_assets()
        import exporter_core as core
        resolved = discover_wechat_db_dir(core, args.db_dir)
        accounts = sorted(p.name for p in resolved.iterdir() if p.is_dir() and (p/'db_storage').is_dir())
        if not accounts: raise ValueError('所选微信数据目录下没有账号数据库。')
        if len(accounts) > 1 and not args.account:
            raise SelectionNeeded('检测到多个微信账号，请先指定账号并重新确认。', [{'account': x} for x in accounts])
        if args.account and args.account not in accounts:
            raise ValueError('指定账号不在所选微信数据目录中。')
        if base == resolved or resolved in base.parents:
            raise ValueError('不能将导出结果保存到微信原始数据目录内。')
        check_weixin_process()
        # No silent downloader invocation; missing rust-silk retains cached voice as SILK.
        core.install_rust_silk = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("不自动下载解码器。"))
        original = core.WeChatDB
        core.WeChatDB = lambda db_dir=None, workdir=None: original(db_dir=str(resolved), account=args.account or accounts[0], workdir=workdir)
        core.find_contact = lambda db, keyword: exact_contact(db, keyword)
        base.mkdir(parents=True, exist_ok=True)
        run = base / ('wechat-export-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
        result = core.export_chat(
            name, out_root=str(run), db_dir=str(resolved),
            export_images=not args.text_only, export_files=not args.text_only,
            export_voices=not args.text_only, export_videos=not args.text_only,
            transcribe_voices=False,
        )
        # No chat text in tool output.
        summary = summarize_export(result, name)
        print(json.dumps({'status':'ok','db_dir':str(resolved),'result':summary}, ensure_ascii=False, default=str))
        return 0
    except ProcessCheckError as exc:
        print(json.dumps({'status':exc.status,'error':str(exc)},ensure_ascii=False))
        return 4
    except SelectionNeeded as exc:
        print(json.dumps({'status':'needs_selection','reason':exc.reason,'candidates':exc.candidates},ensure_ascii=False))
        return 3
    except Exception as exc:
        print(json.dumps({'status':'error','error':f'{type(exc).__name__}: {exc}'},ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

