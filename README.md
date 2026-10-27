# 微信会话导出（Codex Skill）

在 64 位 Windows 本机发现微信数据，列出有本地消息表的私聊和群聊；分别确认后，仅将选定的一个会话导出为 TXT、Markdown、JSON 和本机已缓存的媒体。**不会自动分析、批量导出或上传聊天内容。**

## 安装与依赖

将整个目录放入个人 Codex skills 目录，保持目录名 `wechat-export-fresh`。本仓库**只有源码，不包含 Python 解释器或 PyInstaller 运行目录**。电脑需要已安装 64 位 Python 3.12，并可通过 pip 访问依赖源。首次调用 `invoke.ps1` 会在用户本机的 `%LOCALAPPDATA%\wechat-chat-export\venv312` 创建独立环境，并按 `requirements.txt` 安装固定版本的后端；该步骤需要网络，但不读取微信数据。可以先显式运行 `scripts/setup.ps1`。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\invoke.ps1' doctor
```

`doctor` 检查依赖和脚本入口，不读取微信消息或进程。以后通过 `$wechat-export-fresh` 请求列出会话或导出，模型会分别询问列表授权、目标及输出位置、导出授权。参见 [使用说明](references/usage.md)。

## 来源与限制

核心导出和数据目录发现源码来自 [wechat-chat-export](https://github.com/zhuzhangxue/wechat-chat-export)，固定参考其 v1.4.0 提交 `2c49469a91e2f3b0c73a581e15a8ad2db25b7923`，并用 `scripts/upstream_source.json` 校验两份上游源码散列；本 skill 的入口脚本限制为单会话、两次确认和指定本机输出目录。列表与导出使用同一套“存在本地消息表且身份可确认”的判定：只有 session 缓存、没有 contact 条目的会话也能按唯一标识导出；未聊天的普通联系人不会误入导出。底层数据库库固定为 `wechatauto-replica==1.2.4.4`，通过 pip 安装。上游项目采用 Apache-2.0 许可证，详见 [LICENSE](LICENSE) 和 [第三方说明](THIRD_PARTY_NOTICES.md)。

默认只取本机已缓存的图片、文件、语音、视频。没有安装语音转换器时会保留本机可读的 SILK 原始语音，不会为此下载可执行文件；不下载语音识别模型、不转录。未同步或未缓存的内容无法恢复。临时解密文件会尽力清理，**不等于安全擦除**。导出文件是明文，需由使用者妥善保管。

```powershell
python -X utf8 .\scripts\build\check_release.py
```


