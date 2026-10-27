# 结构与边界

```text
wechat-export-fresh/
├─ SKILL.md / README.md / LICENSE / THIRD_PARTY_NOTICES.md
├─ requirements.txt
├─ scripts/upstream_source.json       # 上游提交与源码散列
├─ agents/openai.yaml
├─ references/{usage.md,architecture.md}
└─ scripts/
   ├─ invoke.ps1 / setup.ps1 / doctor.py
   ├─ list_chats.py / export_one.py / discover_data.py / process_access.py
   ├─ exporter_core.py / wechat_data_dirs.py   # 上游 v1.4.0 源码
   └─ build/check_release.py
```

依赖由 pip 安装到用户本机独立环境，不从技能目录加载 PyInstaller 字节码。`exporter_core.py`、`wechat_data_dirs.py` 来自 zhuzhangxue/wechat-chat-export v1.4.0；`wechatauto-replica==1.2.4.4` 提供数据库解密与媒体接口。固定来源与许可证见 README 和 THIRD_PARTY_NOTICES.md。

`list_chats.py` 只列可可靠识别且有本地消息表的会话；`export_one.py` 使用相同的候选集，仅接受一个会话，要求精确匹配，禁止网络输出目录和批量导出。发现多个数据根或账号时停止供用户选择。读取运行中微信的密钥并解密本地数据库；明文密钥和解密库放在一次性工作目录，结束后尽力清理，不能承诺安全擦除。媒体仅取本机缓存，不主动下载模型或工具。

`doctor` 仅校验依赖版本、上游源码散列与入口；模拟测试不读真实微信。底层微信版本兼容性及第三方依赖网络行为未作全面动态审计。
