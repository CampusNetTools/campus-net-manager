# 验收收尾记录（2026-10-21）

本文件记录本轮独立验收证据。项目原有的 `docs/PROJECT_CLOSURE_PLAN.md` 和 `交付物/` 属于既有工作，本轮没有覆盖或清理。

## 证据边界

- 源码/回归测试、Actions 构建、Actions 虚拟机/模拟器运行、Mac 本机运行、iPhone USB/Safari、真实网络路径分别记录；一种证据不替代另一种。
- 本轮不做商店发布、付费签名或 Android 真机验收。Windows 实机最终交由用户指定的 Windows AI。
- 设备测试只用空账号/合成资料和本机回环地址；没有输入校园网账号或密码。

## 网站 / PWA

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| GitHub Pages | 已通过 | 生产页面 `https://campusnettools.github.io/campus-net-manager/` 可打开；最近部署 run `39388792710` success。页面有软件下载、安装引导、隐私边界与 PWA 添加说明。本轮用系统 Python 经 TLS 回读首页、`app.js`、`sw.js`、`manifest.webmanifest`，均 HTTP 200；SHA-256 依次为 `86071a1f9e2a61b4ca529e75278743ac86d90aaff26819751a023f662a790653`、`e4ba18a4a9cf8cb93e29904d4c3bda04934c406cb5b0872016ec39762a2181e5`、`83d8dd9b5b6f995cf3fb66ab44fba1495e0740c0eb1358812ba1a514a5808772`、`62b3833072178b288ba61fc0de6b5a1c4b7f30a15d20455b3fa35bb3a98a3bac`。默认 Python 的 CA bundle 不信任链失败；切换到 `/usr/bin/python3` 后 TLS 验证成功，未关闭证书验证。 |
| v5.6.0 下载资产 | 已通过校验 | APK `16fe62629ea30c3ab59d59fd12e0160d5b8dac6d0ba5a8c84342b9e1b1b7937e`；macOS ZIP `07a92be36aa279020b9efadc1bccd9f4ba9f66b4f2ce001ab35a748a4f9f685b`；Windows EXE `a0faeff9ea197e7e34be582059fdfc64d97679e6cfac265010c3bc9df337c689`。发布 API digest、下载文件和 `.sha256` sidecar 一致；APK 与 macOS ZIP CRC 通过，Windows 为 x64 PE32+ GUI。 |
| 桌面浏览器/PWA 页面 | 已通过（页面可用性） | 本轮当前浏览器无障碍树可读到已渲染的首页与各平台下载/帮助入口。之前同一验收轮次记录过窄屏无横向溢出和离线 shell 缓存恢复；离线结果不代表 iPhone 已验收。 |
| iPhone 主屏安装、Safari 远程页面、缓存离线恢复 | 未完成 | 本轮 `idevicepair validate` 成功；但桌面 Computer Use runtime 无法启动，不能读取 iPhone 镜像或 Safari DOM，因此没有本轮页面/主屏截图或缓存离线恢复证据。先前尝试输入页面地址时界面没有落到预期项目域名，因此已停止交互；没有打开陌生页面、提交信息或更改网络设置。USB 配对只证明配对链路，不替代手机页面验收。 |

## macOS

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| v5.6.0 安装包与运行 | 已通过 | 公共 ZIP SHA-256 与 Release API digest/sidecar 一致；CRC 通过；`ditto` 解包保留 62 个 symlink，`codesign --verify --deep --strict` 通过。Bundle `com.campusnettools.campusnetmanager`，v5.6.0，adhoc、无 Team ID。当前安装版同 bundle/version/signature，进程运行且窗口标题 v5.6.0。 |
| 界面逐项操作/向导 | 未覆盖 | 只能读到窗口标题和少量窗口系统按钮；Tk 内容控件没有可用的辅助功能标签。坐标自动化曾误触，不再据坐标执行设置类点击。本轮 Computer Use runtime 也未能启动。 |
| 只读网络诊断 | 部分失败 | 一次本机代理可达性提示显示回环地址 `127.0.0.1:7890` 不可达；没有保存配置、启动隧道或更改 Wi-Fi/VPN/热点。 |
| 隧道共享到 iPhone 外网 | 未覆盖 | 热点窗口可见已连接客户端，但无法确认客户端身份；本轮没有批准来源身份不明的请求，没有证明 iPhone 通过 Mac 出口访问外网。当前无法读取实际系统授权提示，故未批准任何请求。 |
| 升级流程 | 未覆盖 | 没有在真实用户数据上执行升级；开发者签名/公证不属于本目标范围。 |

## Android API 36 模拟器

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| v5.6.0 公共 APK | 已通过下载包校验 | 公共 Release APK SHA-256 `16fe62629ea30c3ab59d59fd12e0160d5b8dac6d0ba5a8c84342b9e1b1b7937e`。本轮 run `39542561956` 的 API36 debug APK sidecar 与下载文件 SHA-256 一致：`98b41da9aa4dd8efc11a4a3871290e316c9eff4191ef66dd91f45f2e367d974e`；ZIP CRC 通过。 |
| API 36 安装/启动/UI | 已通过（run `39542561956`，源码 `d1265da`） | APK 构建、Manifest gate、KVM、模拟器安装启动和运行 smoke success；回读截图显示“非校园网环境（认证服务器不可达）”，不是卡在加载态；日志有 `CNM_NETWORK_STATUS_READY`，无 `FATAL EXCEPTION`。该旧 run 未运行新 Keystore/前台服务探针，不覆盖真机硬件。 |
| Keystore、前台服务、进程重启、模拟 Wi-Fi 变化 | 修复后待 Actions | run `39545118250` 的 APK 编译、Manifest gate、项目密钥签名与 KVM 全部通过；模拟器启动并安装 APK 成功，但验收脚本在启动应用前退出，GitHub 日志显示 `mkdir: Needs 1 argument`。上传的模拟器证据包 digest `sha256:4a45dc200d1e1ef63d8969c8321edd78ab3c0a3a66fd1d61b7275c8971ae992c`，其中 logcat 文件为空。另一个旧代码 run `39545460665` 同样在模拟器验收步骤失败，证据 artifact digest `sha256:70139db272263c28a4509e1a08b15ec1de6f5027eaa7520e639b61a01f5f94ad`、logcat 为空；其 job 日志接口返回 EOF，故不推断具体故障。新发现的 runner-to-app 私有目录写入步骤原用嵌套 `run-as sh -c` 复合命令，现已本地改为分开的 `run-as mkdir` 与 `run-as tee` 参数调用，并加回归断言；提交 `9360973`，等待推送后验证。 |
| 真机锁屏/硬件行为 | 未覆盖 | 按用户目标不用 Android 真机；模拟器结果不等同电池/厂商后台策略验收。 |

## Windows x64 hosted VM

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| 当前源码候选包 | 已通过（主界面/向导导航） | run `39542762333` 构建、runner UI smoke、向导和 Plan A 导航通过；没有触发 Wi-Fi/热点操作。 |
| 公开 v5.6.0 EXE 校验与 UI/持久化重启 | 部分通过，截图判定修复待 Actions | run `39545118239` 与 `39545460024` 的公开 EXE 下载、Release API digest/sidecar/SHA-256 比对及隔离配置重启持久化均通过；截图显示向导进入 Plan A，但 UIA 标题一直为“新手向导”，两次标题断言都失败。已在本地 commit `d3f5bbb` 改为比较主内容区域截图变化（标题栏与按钮悬停区排除；先前实测截图中心差异约 9.7%，门槛 5%）；此修复尚未推送/执行。 |
| 代理流程/真实网络 | 未覆盖 | hosted VM 不连接真实校园网、热点或手机网络；本轮探针不得请求外网认证。 |
| Windows 实机 | 延后 | 本目标结束后交给用户指定的 Windows AI 按本机说明执行。 |

## 本地回归修复

- 修复 `tests/test_shared_proxy_loopback.py` 的本地模拟控制台线程在一次空闲 socket timeout 后退出的问题；新增空闲超过 timeout 后仍可回环访问的回归用例。
- Android 新增验收专用 Keystore/前台服务探针、空凭据合成 fixture 与流程检查。生产/商店 APK 不包含探针模块；目标分支相关 push/PR 与显式手动验收会加入探针，结束时清除模拟器数据。
- Windows hosted VM 脚本增加独立目录合成档案的格式/重启持久化检查，并增加公开 EXE 的下载校验。
- Android fixture 传入修复新增 `test_fixture_transfer_uses_direct_run_as_commands`；最新本地完整 `python3 -m unittest discover -s tests` 为 566 passed、3 skipped，`bash -n` 与 `git diff --check` 通过。当前 Mac 没有安装 Ruff；推送后的 CI 会检查 `F,E9`。

## 待补终态

补写 push `9360973` 后 Android 模拟器、Windows hosted VM、PR CI 与 Desktop candidate Actions 的 run ID、逐 job 结果、artifact 回读和哈希；不得将未回读项表述为成功。当前 PR #6 远端头 `f7d607e`；本地在其上有两个待推送提交 `d3f5bbb` 与 `9360973`。工作区既有 `docs/PROJECT_CLOSURE_PLAN.md` 改动和 `交付物/` 均保持原样。
