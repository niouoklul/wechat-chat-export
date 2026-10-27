"""List reliably identifiable local conversations; never export messages."""
import argparse
import contextlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_one import verify_assets, SelectionNeeded, discover_wechat_db_dir
from process_access import ProcessCheckError, check_weixin_process


def select_account(core, requested_dir, account):
    resolved = discover_wechat_db_dir(core, requested_dir)
    accounts = sorted(p.name for p in resolved.iterdir() if p.is_dir() and (p/'db_storage').is_dir())
    if not accounts: raise ValueError('所选目录下没有微信账号数据库。')
    if len(accounts) > 1 and not account:
        raise SelectionNeeded('检测到多个微信账号，请选定一个后重新同意读取列表。', [{'account':x} for x in accounts])
    if account and account not in accounts: raise ValueError('指定账号不在微信数据目录中。')
    return resolved, account or accounts[0]


def summarize(chats, db, keyword, page, page_size):
    detail = {}
    conn = db._contact_conn()
    if conn is not None:
        with contextlib.closing(conn):
            for username, nick, remark in conn.execute('SELECT username,nick_name,remark FROM contact'):
                if username: detail[username] = (nick or '', remark or '')
    entries = []
    for chat in chats:
        username = chat.get('username', '')
        nick, remark = detail.get(username, ('', ''))
        item = {
            'username': username, 'type': '群聊' if chat.get('is_group') else '私聊',
            'name': remark or nick or chat.get('name') or username,
            'remark': remark, 'nickname': nick,
            'last_time': chat.get('last_time'),
        }
        if keyword and not any(keyword.casefold() in str(item[k]).casefold() for k in ('username','name','remark','nickname')):
            continue
        entries.append(item)
    start=(page-1)*page_size
    shown=[dict(item, index=i+1) for i,item in enumerate(entries) if start<=i<start+page_size]
    return {'total':len(entries),'page':page,'page_size':page_size,'pages':(len(entries)+page_size-1)//page_size,
            'chats':shown}


def main(argv=None):
    parser=argparse.ArgumentParser(description='列出本机实际存在消息表的私聊和群聊；不导出正文。')
    parser.add_argument('--db-dir')
    parser.add_argument('--account')
    parser.add_argument('--keyword',default='')
    parser.add_argument('--page',type=int,default=1)
    parser.add_argument('--page-size',type=int,default=50)
    parser.add_argument('--confirm',required=True)
    args=parser.parse_args(argv)
    if args.confirm != '确认列表': parser.error('需要用户在单独回合同意读取本机聊天列表。')
    if args.page<1 or not 1<=args.page_size<=100: parser.error('页码或每页数量无效。')
    workdir=None
    try:
        verify_assets()
        import exporter_core as core
        resolved,account=select_account(core,args.db_dir,args.account)
        check_weixin_process()
        workdir=core._create_sensitive_workdir()
        with core._upstream_sensitive_sandbox(workdir):
            db=core.WeChatDB(db_dir=str(resolved),account=account,workdir=str(workdir))
            chats,unresolved=core._batch_chat_candidates(db)
            result=summarize(chats,db,args.keyword.strip(),args.page,args.page_size)
        result.update({'status':'ok','account':account,'db_dir':str(resolved),'unresolved_message_tables':unresolved})
    except ProcessCheckError as exc:
        result={'status':exc.status,'error':str(exc)}
    except SelectionNeeded as exc:
        result={'status':'needs_selection','reason':exc.reason,'candidates':exc.candidates}
    except Exception as exc:
        result={'status':'error','error':f'{type(exc).__name__}: {exc}'}
    finally:
        if workdir is not None:
            try: core._cleanup_sensitive_workdir(workdir)
            except Exception as exc: result['cleanup_error']=f'{type(exc).__name__}: {exc}'
            if workdir.exists(): result['cleanup_warning']='敏感临时目录可能残留：'+str(workdir)
    print(json.dumps(result,ensure_ascii=False,default=str))
    return 0 if result['status']=='ok' else (3 if result['status']=='needs_selection' else 1)


if __name__=='__main__': raise SystemExit(main())


