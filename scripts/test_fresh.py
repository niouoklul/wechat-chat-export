import sqlite3
import hashlib
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_one import exact_contact, SelectionNeeded, absolute_local_dir, verify_assets, discover_wechat_db_dir, summarize_export
from list_chats import summarize

class FakeDB:
    def __init__(self):
        self.uri = 'file:skilltest?mode=memory&cache=shared'
        self.keep = sqlite3.connect(self.uri, uri=True)
        self.keep.execute('CREATE TABLE contact(username TEXT,nick_name TEXT,remark TEXT)')
        self.keep.executemany('INSERT INTO contact VALUES(?,?,?)', [
            ('wxid_a','同名','张三'),('wxid_b','同名','另一备注'),('grp@chatroom','项目群','工作群')])
        self.keep.commit()
    def _contact_conn(self): return sqlite3.connect(self.uri,uri=True)
    def search_contact(self,name): return [{'username':'wxid_a','nick_name':'同名','remark':'张三'}]

class TestSafeSelection(unittest.TestCase):
    def setUp(self): self.db=FakeDB()
    def tearDown(self): self.db.keep.close()

    def resolve(self, name, chats=None, db=None):
        if chats is None:
            chats = [
                {'username':'wxid_a','name':'同名','is_group':False},
                {'username':'wxid_b','name':'同名','is_group':False},
                {'username':'grp@chatroom','name':'项目群','is_group':True},
            ]
        with patch('exporter_core._batch_chat_candidates', return_value=(chats, 0)):
            return exact_contact(db or self.db, name)

    def test_unique_remark(self): self.assertEqual(self.resolve('张三')['username'],'wxid_a')
    def test_unique_group(self): self.assertEqual(self.resolve('工作群')['username'],'grp@chatroom')
    def test_duplicate_name_stops(self):
        with self.assertRaises(SelectionNeeded) as e: self.resolve('同名')
        self.assertEqual(len(e.exception.candidates),2)
    def test_fuzzy_does_not_export(self):
        with self.assertRaises(SelectionNeeded): self.resolve('张')
    def test_session_only_chat_can_export_by_id_or_display(self):
        chats = [{'username':'wxid_session','name':'临时会话','is_group':False}]
        self.assertEqual(self.resolve('wxid_session',chats)['username'], 'wxid_session')
        self.assertEqual(self.resolve('临时会话',chats)['username'], 'wxid_session')
    def test_contact_without_message_table_cannot_export(self):
        chats = [{'username':'wxid_a','name':'同名','is_group':False}]
        with self.assertRaises(SelectionNeeded): self.resolve('另一备注', chats)
    def test_stable_id_takes_precedence_over_same_text_remark(self):
        self.db.keep.execute('UPDATE contact SET remark=? WHERE username=?', ('wxid_a','wxid_b'))
        self.db.keep.commit()
        self.assertEqual(self.resolve('wxid_a')['username'], 'wxid_a')
    def test_session_only_chat_without_contact_db(self):
        chats = [{'username':'wxid_session','name':'临时会话','is_group':False}]
        with patch.object(self.db, '_contact_conn', return_value=None):
            self.assertEqual(self.resolve('临时会话', chats)['username'], 'wxid_session')
    def test_single_discovered_root(self):
        import wechat_data_dirs as dirs
        root=Path('D:/chosen/root')
        fake=types.SimpleNamespace(resolve_db_dir=lambda p: str(p))
        with patch('discover_data.discover_data_roots',return_value=[{'path':str(root),'auto_selected':False}]):
            self.assertEqual(discover_wechat_db_dir(fake),root.resolve())
    def test_upstream_auto_selected_root_wins(self):
        import wechat_data_dirs as dirs
        roots=[{'path':'D:/old','auto_selected':False},{'path':'E:/active','auto_selected':True}]
        fake=types.SimpleNamespace(resolve_db_dir=lambda p: str(p))
        with patch('discover_data.discover_data_roots',return_value=roots):
            self.assertEqual(discover_wechat_db_dir(fake),Path('E:/active').resolve())
    def test_ambiguous_roots_stop(self):
        import wechat_data_dirs as dirs
        roots=[{'path':'D:/one','auto_selected':False},{'path':'E:/two','auto_selected':False}]
        fake=types.SimpleNamespace(resolve_db_dir=lambda p: str(p))
        with patch('discover_data.discover_data_roots',return_value=roots):
            with self.assertRaises(SelectionNeeded) as error: discover_wechat_db_dir(fake)
        self.assertEqual(len(error.exception.candidates),2)
    def test_explicit_root_skips_discovery(self):
        import wechat_data_dirs as dirs
        fake=types.SimpleNamespace(resolve_db_dir=lambda p: str(p))
        with patch('discover_data.discover_data_roots',side_effect=AssertionError('不应自动发现')):
            self.assertEqual(discover_wechat_db_dir(fake,'D:/selected'),Path('D:/selected').resolve())
    def test_original_directory_discovery_on_synthetic_root(self):
        import wechat_data_dirs as dirs
        import wechatauto
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'WeChatData'
            account=root/'xwechat_files'/'wxid_test'/'db_storage'
            account.mkdir(parents=True)
            (account/'contact.db').write_bytes(b'fake')
            with patch.object(wechatauto,'auto_detect_db_dir',return_value=None), \
                 patch.object(dirs,'_config_candidate_paths',return_value=[str(root)]), \
                 patch.object(dirs,'_registry_candidate_paths',return_value=[]), \
                 patch.object(dirs,'_common_candidate_paths',return_value=[]), \
                 patch.object(dirs,'_shallow_drive_candidates',return_value=[]):
                found=dirs.discover_wechat_data_dirs()
            self.assertEqual(len(found),1)
            self.assertEqual(Path(found[0]['path']),root/'xwechat_files')
            self.assertEqual(found[0]['account_count'],1)
    def test_adjacent_custom_install_root_and_merge(self):
        import discover_data
        import wechat_data_dirs as dirs
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'wx'
            install = base / 'Weixin'
            install.mkdir(parents=True)
            (install / 'Weixin.exe').touch()
            root = base / 'document' / 'xwechat_files'
            storage = root / 'wxid_test' / 'db_storage'
            storage.mkdir(parents=True)
            (storage / 'contact.db').touch()
            self.assertEqual(discover_data.adjacent_data_roots([base]), [root])
            with patch.object(dirs, '_fixed_drive_roots', return_value=[Path(tmp)]), \
                 patch('psutil.process_iter', return_value=[]), \
                 patch.object(dirs, 'discover_wechat_data_dirs', return_value=[]):
                found = discover_data.discover_data_roots()
            self.assertEqual(len(found), 1)
            self.assertEqual(Path(found[0]['path']), root)
            self.assertEqual(found[0]['account_count'], 1)

    def test_adjacent_root_deduplicated(self):
        import discover_data
        import wechat_data_dirs as dirs
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'xwechat_files'
            storage = root / 'wxid_test' / 'db_storage'
            storage.mkdir(parents=True)
            (storage / 'contact.db').touch()
            previous = {'path': str(root), 'auto_selected': False}
            with patch.object(dirs, 'discover_wechat_data_dirs', return_value=[previous]), \
                 patch('discover_data.adjacent_data_roots', return_value=[root]):
                self.assertEqual(discover_data.discover_data_roots(), [previous])
    def test_process_access_denied_not_reported_as_absent(self):
        import process_access
        fake = types.SimpleNamespace(returncode=1, stdout='', stderr='ERROR: Access denied')
        with patch.object(process_access.subprocess, 'run', return_value=fake):
            with self.assertRaises(process_access.ProcessCheckError) as error:
                process_access.check_weixin_process()
        self.assertEqual(error.exception.status, 'needs_permission')

    def test_process_present_and_absent_are_distinct(self):
        import process_access
        running = types.SimpleNamespace(returncode=0, stdout='"Weixin.exe","42","Console"\n', stderr='')
        with patch.object(process_access.subprocess, 'run', return_value=running):
            self.assertEqual(process_access.check_weixin_process(), [42])
        absent = types.SimpleNamespace(returncode=0, stdout='INFO: No tasks are running', stderr='')
        with patch.object(process_access.subprocess, 'run', return_value=absent):
            with self.assertRaises(process_access.ProcessCheckError) as error:
                process_access.check_weixin_process()
        self.assertEqual(error.exception.status, 'not_running')
    def test_list_only_actual_chats_and_page(self):
        chats=[{'username':'wxid_a','name':'Alice','is_group':False,'last_time':2},
               {'username':'grp@chatroom','name':'群','is_group':True,'last_time':1}]
        first=summarize(chats,self.db,'',1,1)
        self.assertEqual(first['total'],2)
        self.assertEqual(first['pages'],2)
        self.assertEqual(first['chats'][0]['name'],'张三')
        second=summarize(chats,self.db,'',2,1)
        self.assertEqual(second['chats'][0]['type'],'群聊')
        self.assertEqual(second['chats'][0]['name'],'工作群')
        filtered=summarize(chats,self.db,'工作',1,50)
        self.assertEqual(filtered['total'],1)
    def test_export_summary_maps_upstream_chat_name_without_body(self):
        result = {'chat_name':'项目群', 'message_count':3, 'output_dir':'D:/out',
                  'messages':[{'content':'敏感正文'}], 'sensitive_cache_cleanup':False}
        summary = summarize_export(result, 'fallback')
        self.assertEqual(summary['name'], '项目群')
        self.assertEqual(summary['message_count'], 3)
        self.assertNotIn('messages', summary)
        self.assertIn('cleanup_warning', summary)
    def test_relative_path_refused(self):
        with self.assertRaises(ValueError): absolute_local_dir('relative/path')
    def test_original_chat_discovery_on_synthetic_db(self):
        import exporter_core as core
        class Stub:
            _db_files={}
            def _nickname_index(self): return {'wxid_a':'Alice'}
            def _message_dbs(self): return []
            def get_self_info(self): return {'username':'wxid_me'}
        with patch.object(core,'_batch_message_hashes',return_value={hashlib.md5(b'wxid_a').hexdigest()}):
            chats, unresolved=core._batch_chat_candidates(Stub())
        self.assertEqual(chats[0]['username'],'wxid_a')
        self.assertEqual(unresolved,0)
    def test_pinned_upstream_source(self):
        verify_assets()
        import exporter_core as core
        import zstandard
        self.assertEqual(core.decompress_zstd(zstandard.ZstdCompressor().compress('测试'.encode())), '测试'.encode())
        self.assertNotIn('/', core.safe_folder_name('测试/会话'))
    def test_network_share_refused(self):
        with self.assertRaises(ValueError): absolute_local_dir('\\\\server\\share')

if __name__=='__main__': unittest.main()




