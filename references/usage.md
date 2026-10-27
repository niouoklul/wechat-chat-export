# 执行与确认流程

所有命令将 `<技能目录>` 替换为当前技能的真实绝对路径。使用宿主本机命令工具；每个参数单独传递，不能将联系人名称拼成脚本。`invoke.ps1` 仅接受 `doctor`、`list`、`export`，不提供批量导出。

## 首次安装与自检

需要 64 位 Windows Python 3.12。`invoke.ps1` 首次运行会通过 pip 安装 `requirements.txt` 到 `%LOCALAPPDATA%\wechat-chat-export\venv312`，需要网络；不会在这一步读取微信。若无法联网或 Python 不兼容，应停止并说明依赖未装好。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<技能目录>\scripts\invoke.ps1' doctor
```

`doctor` 只导入模块和检查列表/导出入口帮助模式，不读取微信。失败停止，不跳过。
## 读取会话列表（第一次确认）

用户请求导出时先说明：将使用后端的配置、注册表、常见路径，以及微信安装位置周边的有界目录探测来发现数据根；读取正在运行的微信进程密钥和本机数据库以列出可可靠识别的私聊/群聊，不在此步导出聊天正文。请求用户回复“确认列表”并结束本回合。原始请求里的“确认”不能跳过。

收到后续真实确认才运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<技能目录>\scripts\invoke.ps1' list --confirm '确认列表'
```

默认每页 50 条；如果用户要求完整列表，设置 `--page-size 100`，并继续翻页直到 `pages` 全部展示。翻页时沿用同一个已确认的账号与数据根，不读取正文。结果包含 `db_dir`、`account`、总数、页数、候选 username、显示名、备注/昵称、类型与最近时间。用 `--page 2` 或 `--keyword '<关键词>'` 浏览时传入上次返回的 `--db-dir '<绝对路径>'` 和账号，避免切换数据根。列表基于本机缓存，不是服务器好友列表；不可靠的消息表数量会单列。


`needs_permission` 表示列进程失败（例如执行环境对 `tasklist` 返回 Access denied），不是微信未运行。已获“确认列表”时可按系统权限流程申请在非隔离环境原样重运行 `list` 一次；不要绕过授权或自行读取密钥。若依然失败，说明权限限制并停止。只有成功读取进程列表且没有 `Weixin.exe` 的 `not_running`，才建议打开微信。

`needs_selection` 表示多个数据根或账号：显示路径、来源/账号数或账号名，让用户选定；数据范围改变需重新说明并征得列表同意。若仍找不到，先排查是否存在安装目录旁的 `document/xwechat_files` 等目录（只检查目录元数据，不读取聊天）；确实找不到时再请用户到微信设置查看真实位置并以 `--db-dir` 指定。不要编造默认路径。

## 导出单个会话（第二次确认）

用户从已显示列表选编号或名称后，以该条**唯一 username**固定身份；询问本机绝对输出基目录。展示名称、username、账号、实际微信数据根、输出基目录、TXT/Markdown/JSON、默认四类本机媒体（缺少本机语音解码器时保留 SILK）、范围（本机可读历史）；说明明文结果会在基目录下新建唯一子目录，未同步或未缓存内容无法恢复。请用户回复“确认导出”，结束本回合。只有此计划的后续真实确认才能运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<技能目录>\scripts\invoke.ps1' export --name '<唯一 username>' --db-dir '<列表返回的绝对路径>' --account '<列表返回的账号>' --output-base '<用户指定的本机绝对目录>' --confirm '确认导出'
```

`--account` 在单账号时可省略；仅用户明确仅文字才加 `--text-only`。对象、账号、数据目录、输出目录或媒体选项改变，重新展示计划并等待确认。`needs_permission` 时按权限流程申请重运行一次，仍失败则停止；`needs_selection` / `error` 时如实说明，不选第一个近似结果、不自动重试。系统执行权限批准不能替代聊天授权。

输出可能包含个人资料；只汇报返回的路径、消息数和媒体统计，不主动贴聊天正文。导出内容和任何持续缓存都由用户保管。使用技能仅支持兼容的 64 位 Windows 微信，真实环境兼容性不能由合成测试保证。
