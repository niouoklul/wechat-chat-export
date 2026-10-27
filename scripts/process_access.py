"""Distinguish process-enumeration denial from an absent WeChat process."""
import csv
import io
import subprocess


class ProcessCheckError(RuntimeError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def check_weixin_process():
    command = ['tasklist', '/FI', 'IMAGENAME eq Weixin.exe', '/FO', 'CSV', '/NH']
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding='gbk', errors='replace',
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except OSError as exc:
        raise ProcessCheckError('needs_permission',
                                f'无法检查微信进程（{type(exc).__name__}）；不能据此判定微信未运行。') from exc
    if result.returncode != 0:
        raise ProcessCheckError('needs_permission',
                                '无法读取本机进程列表（可能被执行环境拦截）；不能据此判定微信未运行。')
    pids = [int(row[1]) for row in csv.reader(io.StringIO(result.stdout))
            if len(row) >= 2 and row[0].lower() == 'weixin.exe' and row[1].isdigit()]
    if not pids:
        raise ProcessCheckError('not_running', '当前可见进程列表中没有 Weixin.exe；请确认电脑版微信已登录。')
    return pids
