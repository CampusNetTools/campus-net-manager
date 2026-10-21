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
| 桌面浏览器/PWA 页面 | 已通过（页面可用性） | 当前 in-app browser 标签 `https://campusnettools.github.io/campus-net-manager/` 可读到完整渲染首页、Windows/macOS/Android 下载说明、iPhone 主屏安装说明、隐私边界和最新 Release 入口。之前同一验收轮次记录过窄屏无横向溢出和离线 shell 缓存恢复；离线结果不代表 iPhone 已验收。 |
| 本轮公开站点回读 | 已通过 | 2026-10-21 再次用 `/usr/bin/python3` 默认 CA 验证生产站点，无关闭 TLS 校验：首页、`app.js`、`sw.js`、`manifest.webmanifest` 均 HTTP 200，SHA-256 与前次记录一致（首页 `86071a1f9e2a61b4ca529e75278743ac86d90aaff26819751a023f662a790653`；其余见上表）。首页下载入口指向 GitHub Releases 最新版；Release API 当前仍为 v5.6.0，三平台资产与 sidecar 均存在。 |
| iPhone 主屏安装、Safari 远程页面、缓存离线恢复 | 部分通过；本轮无法复核，离线冷启动未覆盖 | 项目此前记录有 iPhone 将 PWA 添加到主屏并在线启动的设备证据；本轮 `idevicepair validate` 成功，USB 只读设备信息报告 `AirplaneMode=false`，但 `WiFiEnabled` 键没有返回值。内置 browser 标签可读桌面页面，native app automation runtime 缺失且 Mac 锁屏，未能检查镜像 UI。只读启动 USB WebKit proxy 时已连接 iPhone，但 `http://127.0.0.1:9222/json` 返回 `[]`；代理随后停止。因此本轮没有 Safari 页面/主屏截图，手机离线冷启动与缓存恢复仍未覆盖。没有更改手机网络设置。 |

## macOS

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| v5.6.0 安装包与运行 | 已通过 | 公共 ZIP SHA-256 与 Release API digest/sidecar 一致；CRC 通过；`ditto` 解包保留 62 个 symlink，`codesign --verify --deep --strict` 通过。Bundle `com.campusnettools.campusnetmanager`，v5.6.0，adhoc、无 Team ID。当前安装版同 bundle/version/signature，进程运行且窗口标题 v5.6.0。最新 PR candidate run `39550469356` 的 arm64 ZIP SHA-256 `f1fd36e2757ff7421d86048bf61b8d6e0050b132eeaf27a9d0dd8e299bfc516d` 与 sidecar 一致、ZIP CRC 通过；解包后 strict codesign 通过，adhoc、无 Team ID。该候选包不是公证或正式 Release。 |
| 界面逐项操作/向导 | 未覆盖 | 本轮确认 app 进程运行、bundle `com.campusnettools.campusnetmanager` v5.6.0，`codesign --verify --deep --strict` 通过，adhoc、无 Team ID。Native app Computer Use runtime 连续三次未能启动；另一 UI 状态接口报告 Mac 锁屏且无法自动解锁。没有对 Tk 控件执行坐标点击。 |
| 只读网络诊断 | 部分失败 | 一次本机代理可达性提示显示回环地址 `127.0.0.1:7890` 不可达；没有保存配置、启动隧道或更改 Wi-Fi/VPN/热点。 |
| 隧道共享到 iPhone 外网 | 未覆盖 | 热点窗口可见已连接客户端，但无法确认客户端身份；本轮没有可读的系统授权提示，未批准任何请求，也没有证明 iPhone 通过 Mac 出口访问外网。用户之前仅授权对明确属于本项目的提示允许一次，不能用来源不明的连接替代该条件。 |
| 升级流程 | 未覆盖 | 没有在真实用户数据上执行升级；开发者签名/公证不属于本目标范围。 |

## Android API 36 模拟器

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| v5.6.0 公共 APK | 已通过下载包校验 | 公共 Release APK SHA-256 `16fe62629ea30c3ab59d59fd12e0160d5b8dac6d0ba5a8c84342b9e1b1b7937e`。本轮 run `39542561956` 的 API36 debug APK sidecar 与下载文件 SHA-256 一致：`98b41da9aa4dd8efc11a4a3871290e316c9eff4191ef66dd91f45f2e367d974e`；ZIP CRC 通过。 |
| API 36 安装/启动/UI | 已通过（run `39557218041`，commit `122a3fc`） | API36 APK 构建、Manifest gate、KVM、模拟器安装启动成功。回读截图显示主界面已退出加载态并呈现“非校园网环境（认证服务器不可达）”；logcat 有 `CNM_NETWORK_STATUS_READY`，本次证据未见崩溃标记。APK 外层 Actions artifact `12326713740` digest / 本地 SHA-256 一致 `6f78518bd87be5e49488ed53c38e50b7f236dea99d8b65bbc0d7ef8dafd43233`，ZIP CRC 通过；内层 APK SHA-256 与 sidecar 一致 `16f92b00be40af1b167f14cc2b617d6726a4c14f10b27883fb3ca8bc0d29f924`。 |
| Keystore、前台服务、进程重启、模拟 Wi-Fi 变化 | 已通过（同一 run） | 私有文件检查确认路径 `files/profile.enc`；第一次写入输出 `CNM_ANDROID_PROFILE_STORE_WRITE_PASS`，应用进程重启后输出 `CNM_ANDROID_PROFILE_STORE_RESTART_PASS`。前台服务在首次启动、进程重启、模拟 Wi-Fi 状态变化后三个检查点均存在。模拟器记录初始 Wi-Fi `1`，测试期间 `0`，恢复检查回到 `1`；日志含 `CNM_ANDROID_WIFI_RESTORED=1` 与 `CNM_ANDROID_ACCEPTANCE_DATA_CLEARED`。证据 artifact `12326409733` digest `sha256:b3a855e157ffa706b89d04128abc85e9d780534f7a7e1de1ef112f0f83e10ecd`；本地回读证据包 CRC 通过，logcat SHA-256 `77cc9b62f5f936e2fe31aef4abadee398e71e79ebbeaef09e93d91dcbaa6eefe`，截图 SHA-256 `d8149d729f68de713aca76ed807831c8cc6d04df74b1791755aba3334fa5b23a`。模拟器软件状态模拟不等同真实无线电/硬件密钥/OEM 后台策略验收。 |
| 真机锁屏/硬件行为 | 未覆盖 | 按用户目标不用 Android 真机；模拟器结果不等同电池/厂商后台策略验收。 |

## Windows x64 hosted VM

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| 当前源码候选包 | 已通过（主界面/向导导航） | 当前 head `122a3fc` 的 run `39557218038` 在 GitHub-hosted Windows x64 VM 构建；主窗体和首次向导可见，Plan A 导航通过，截图差异比例 `0.097`。合成档案保留有效 JSON，重启根进程后主窗体和档案仍正常；网络/热点操作未调用。候选报告 artifact `12325054626` digest `sha256:0faed9d3b9c434ac02b83fa3bdb0dd8d6ecba44e1a1c94e017f651aaca2e8d9d`，ZIP CRC 通过。 |
| 公开 v5.6.0 EXE 校验与 UI/持久化重启 | 已通过（Windows x64 hosted VM） | 同一 run 下载并校验公开 Windows Release EXE；公开版向导从方式选择进入 Plan A，截图差异比例 `0.097`；合成档案跨根进程重启后保留。报告 `windows-release-ui-acceptance.txt` 为 `result=passed`。before/after 截图 SHA-256 与上一轮记录一致；没有触发 Wi-Fi/热点操作。证据只代表 hosted VM，不代表真实 Windows 设备、物理无线网或手机网络。 |
| 代理流程/真实网络 | 未覆盖 | hosted VM 不连接真实校园网、热点或手机网络；本轮探针不得请求外网认证。 |
| Windows 实机 | 延后 | 本目标结束后交给用户指定的 Windows AI 按本机说明执行。 |

## 本地回归修复

- 修复 `tests/test_shared_proxy_loopback.py` 的本地模拟控制台线程在一次空闲 socket timeout 后退出的问题；新增空闲超过 timeout 后仍可回环访问的回归用例。
- Android 新增验收专用 Keystore/前台服务探针、空凭据合成 fixture 与流程检查。生产/商店 APK 不包含探针模块；目标分支相关 push/PR 与显式手动验收会加入探针，结束时清除模拟器数据。
- Windows hosted VM 脚本增加独立目录合成档案的格式/重启持久化检查，并增加公开 EXE 的下载校验。
- Android fixture 传入修复新增 `test_fixture_transfer_uses_direct_run_as_commands`；新增前台服务有界等待及诊断测试 `test_foreground_service_assertion_waits_for_startup_and_reports_state`，定向 7 tests passed；最新完整本地套件 `python3 -m unittest discover -s tests` 为 568 passed、3 skipped。`bash -n`、YAML parse 与 `git diff --check` 通过。当前 Mac 没有安装 Ruff；最新 PR CI `39550469337` 的 Windows/macOS `F,E9` 静态与测试 checks 已成功。
- 修复 desktop-candidate detector 只比较 `HEAD^`、遗漏同一 PR 先前代码提交的问题：PR 场景现在比较 base SHA 到 HEAD；新增 `test_desktop_candidate_detects_changes_across_the_entire_pull_request`，commit `2d086b7`。PR run `39550469356` 已确认 Windows VM 与 macOS build 都实际执行。

## PR CI / 桌面候选 Actions

| run | 结果 | 证据与边界 |
|---|---|---|
| PR CI `39557218050` | success | 当前 head `122a3fc` 的 Windows/macOS 全套测试、静态、版本、页面和敏感值检查通过；Release 和 PR Android artifact job 按规则 skip。 |
| Desktop candidate `39557218038` | success | Windows x64 VM 源码候选、公开 v5.6.0 EXE 向导/持久化验收通过；macOS arm64 candidate build、签名检查与 artifact 上传通过。Windows reports/screenshots artifact CRC 已回读。 |

## 待补终态

终态：Android run `39557218041`、PR CI `39557218050`、Desktop candidate `39557218038` 均以当前 head `122a3fc6f5dead21ce99b58b6bc63d8ff831811c` 成功结束；APK、模拟器日志/截图、Windows VM 报告均已下载回读并校验。Mac 本机 v5.6.0 仍运行，bundle 与 adhoc 签名 strict 校验通过，但 Tk 控件级验收未覆盖；Computer Use runtime 连续三次未能启动，另一 UI 状态接口报告 Mac 锁屏且自动解锁失败。iPhone USB 配对仍有效、AirplaneMode=false；只读启动 USB WebKit proxy 后本机 `/json` 返回空数组，随后代理已停止，因此本轮没有 Safari 页面证据。此前 PWA 主屏安装和在线启动有 iPhone 设备记录，离线冷启动仍未覆盖。隧道共享系统授权提示不可见，未批准来源不明请求；Mac 到 iPhone 外网流量验证未覆盖。公开 Pages TLS/核心资源已复核，当前桌面浏览器能读到完整 PWA 首页，之前桌面浏览器离线缓存测试仍通过，但不替代 iPhone 离线冷启动。PR #6 open，head/origin 均为 `122a3fc`。原有 `docs/PROJECT_CLOSURE_PLAN.md` 修改和 `交付物/` 未触碰。恢复 native app Computer Use 前需手动解锁 Mac 并重新启动 Codex/ChatGPT 桌面应用；之后打开项目 PWA 的 iPhone Safari 页面，让 USB Web Inspector target 可读，再继续手机离线缓存检查和条件明确的一次隧道共享验证。
