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
| 桌面浏览器/PWA 页面 | 在线页面和响应式已通过；离线导航未证实 | 当前 in-app browser 标签 `https://campusnettools.github.io/campus-net-manager/` 可读到完整首页、Windows/macOS/Android 下载说明、iPhone 主屏安装说明、隐私边界和最新 Release 入口。390px viewport 无横向溢出。当前 Service Worker 已控制页面，`campusnet-pwa-shell-v2` 存在且缓存根页。离线模拟时 `navigator.onLine=false`，CSS/app.js/图标来自 Cache Storage，但主导航响应标记为 Service Worker 的网络来源；因此只证明部分静态资源缓存，不能证明整页离线冷启动成功。 |
| 本轮公开站点回读 | 已通过 | 2026-10-21 再次用 `/usr/bin/python3` 默认 CA 验证生产站点，无关闭 TLS 校验：首页、`app.js`、`sw.js`、`manifest.webmanifest` 均 HTTP 200，SHA-256 与前次记录一致（首页 `86071a1f9e2a61b4ca529e75278743ac86d90aaff26819751a023f662a790653`；其余见上表）。首页下载入口指向 GitHub Releases 最新版；Release API 当前仍为 v5.6.0，三平台资产与 sidecar 均存在。 |
| iPhone 主屏安装、Safari 远程页面、缓存离线恢复 | 部分通过；本轮无法复核，离线冷启动未覆盖 | 项目此前记录有 iPhone 将 PWA 添加到主屏并在线启动的设备证据；本轮 `idevicepair validate` 成功，USB 只读设备信息报告 `AirplaneMode=false`，但 `WiFiEnabled` 键没有返回值。内置 browser 标签可读桌面页面，native app automation runtime 缺失且 Mac 锁屏，未能检查镜像 UI。只读启动 USB WebKit proxy 时已连接 iPhone，但 `http://127.0.0.1:9222/json` 返回 `[]`；代理随后停止。因此本轮没有 Safari 页面/主屏截图，手机离线冷启动与缓存恢复仍未覆盖。没有更改手机网络设置。 |

## macOS

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| v5.6.0 安装包与运行 | 已通过 | 公共 ZIP SHA-256 与 Release API digest/sidecar 一致；CRC 通过；`ditto` 解包保留 62 个 symlink，`codesign --verify --deep --strict` 通过。Bundle `com.campusnettools.campusnetmanager`，v5.6.0，adhoc、无 Team ID。当前安装版同 bundle/version/signature，进程运行且窗口标题 v5.6.0。最新 PR candidate run `39560792145` 的 arm64 app build、strict signature check、10 秒 runner launch 和 artifact upload 均 success；本机安装包 strict signature 验证独立通过。候选包不是公证或正式 Release。 |
| 界面逐项操作/向导 | 未覆盖 | 本轮确认 app 进程运行、bundle `com.campusnettools.campusnetmanager` v5.6.0，`codesign --verify --deep --strict` 通过，adhoc、无 Team ID。Native app Computer Use runtime 连续三次未能启动；另一 UI 状态接口报告 Mac 锁屏且无法自动解锁。没有对 Tk 控件执行坐标点击。 |
| 只读网络诊断 | 部分失败 | 一次本机代理可达性提示显示回环地址 `127.0.0.1:7890` 不可达；没有保存配置、启动隧道或更改 Wi-Fi/VPN/热点。 |
| 隧道共享到 iPhone 外网 | 未覆盖 | 热点窗口可见已连接客户端，但无法确认客户端身份；本轮没有可读的系统授权提示，未批准任何请求，也没有证明 iPhone 通过 Mac 出口访问外网。用户之前仅授权对明确属于本项目的提示允许一次，不能用来源不明的连接替代该条件。 |
| 升级流程 | 未覆盖 | 没有在真实用户数据上执行升级；开发者签名/公证不属于本目标范围。 |

## Android API 36 模拟器

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| v5.6.0 公共 APK | 已通过下载包校验 | 公共 Release APK SHA-256 `16fe62629ea30c3ab59d59fd12e0160d5b8dac6d0ba5a8c84342b9e1b1b7937e`。本轮 run `39542561956` 的 API36 debug APK sidecar 与下载文件 SHA-256 一致：`98b41da9aa4dd8efc11a4a3871290e316c9eff4191ef66dd91f45f2e367d974e`；ZIP CRC 通过。 |
| API 36 安装/启动/UI | 已通过（run `39560792156`，head `e2cfd90`；应用代码仍为 `122a3fc`） | APK 构建、Manifest gate、KVM、模拟器安装/启动和运行步骤成功。回读截图显示主界面已退出加载态并呈现“非校园网环境（认证服务器不可达）”；logcat 有 `CNM_NETWORK_STATUS_READY`。APK artifact `12328419155` digest / 本地 SHA-256 一致 `7e5d46a236c09ba544f797d021e1918f41a4994fa57832b2f8fbfb61a9ce122f`，ZIP CRC 通过；内层 APK SHA-256 与 sidecar 一致 `b5262f8d654a3db6ca0658b2c98d611e80b1341bb13c1afbc6d41fba590cd639`。 |
| Keystore、前台服务、进程重启、模拟 Wi-Fi 变化 | 已通过（run `39560792156`） | 私有文件路径 `files/profile.enc` 写入成功，marker 为 `CNM_ANDROID_PROFILE_STORE_WRITE_PASS`；进程重启后 `CNM_ANDROID_PROFILE_STORE_RESTART_PASS`。前台服务在首次启动、重启、模拟 Wi-Fi 状态变化后均存在。模拟器 Wi-Fi 初始值 `1`，测试时 `0`，恢复为 `1`；logcat 有 `CNM_ANDROID_WIFI_RESTORED=1` 和 `CNM_ANDROID_ACCEPTANCE_DATA_CLEARED`。证据 artifact `12329486735` digest `sha256:8a5ac4f57648d2e4b67926388ee91e83116a5a8ba8061714f20b0a7d314db679`，ZIP CRC 通过；logcat SHA-256 `65b4ad7d756b9858903c1d589e1bdd0f80341af088859404019674be7d4e1e61`，截图 SHA-256 `84cc1b00e88d60f0dfb2711148a5d100218130ae63434d084b85aef803d805d4`。模拟器不证明硬件-backed key、实体无线电、OEM 后台策略或真实校园网。 |
| 真机锁屏/硬件行为 | 未覆盖 | 按用户目标不用 Android 真机；模拟器结果不等同电池/厂商后台策略验收。 |

## Windows x64 hosted VM

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| 当前源码候选包 | 已通过（run `39560792145`，Windows x64 hosted VM） | 主窗体与首次向导可见，Plan A 导航通过，截图差异比例 `0.097`。合成档案 JSON 有效，根进程重启后主窗体和档案仍正常；网络/热点操作未调用。候选 VM 报告 artifact `12327901025` digest `sha256:53a85e017282e02bad2c4b28d75578fdb99ae9a6821159bc53b4d30a05fa9fc1`。 |
| 公开 v5.6.0 EXE 校验与 UI/持久化重启 | 已通过（同一 Windows x64 hosted VM run） | 下载并校验公开 Windows Release EXE；公开版向导从方式选择进入 Plan A，合成档案跨根进程重启后保留，报告 `result=passed`。没有触发 Wi-Fi/热点操作；不代表真实 Windows 设备或无线网验收。 |
| 代理流程/真实网络 | 部分覆盖 | 本轮 VM 未触发 GUI 代理/共享或系统网络操作。PR CI 全套测试通过，其中回环代理、PAC/本机 setup page 组件用例已运行；这不是 Windows GUI 代理流程或真实网络路径验收。 hosted VM 不连接真实校园网、热点或手机网络。 |
| Windows 实机 | 延后 | 本目标结束后交给用户指定的 Windows AI 按本机说明执行。 |

## 本轮补充复核

- 当前本地分支 `codex/windows-vm-ui-acceptance` 与远端一致，HEAD 为 `ce7cc410d918c97e969dd5e7d360edf3c1a3c210`。PR #6 仍 open、未合并且 mergeable。对该 HEAD 的 Android APK (`39565615809`)、PR CI (`39565615855`) 和 Desktop candidate (`39565615829`) 均为 completed/success；本轮没有重启 workflow，也没有改应用源码。
- PWA：新的在线标签仍可打开公开站点；Service Worker 控制页面，`campusnet-pwa-shell-v2` 仍存在且根页已缓存。再次对旧标签做离线主导航时，浏览器将导航转换成内部 `data:text/html` 的 `ERR_INTERNET_DISCONNECTED` 错误页；工具不允许把该内部 URL 导回站点，也不允许关闭该错误标签。随后新开在线标签并复核页面正常。该浏览器标签副作用不代表系统断网或线上站点故障；本次重测没有证明离线冷启动成功，没有更改 Mac 或 iPhone 网络设置。旧错误标签留在浏览器中，在线站点在新标签可用。
- iPhone：本轮 `idevicepair validate` 返回 `SUCCESS`，`ideviceinfo -k AirplaneMode` 返回 `false`；`WiFiEnabled` 键未提供值。iPhone Mirroring 辅助功能树仅暴露窗口级元素，Safari 仍无可读的 iPhone 页面目标。前次镜像 UI 要求锁定 iPhone 才能连接；本轮未自动锁屏、未改 Wi-Fi/蜂窝/VPN/代理，也未运行离线启动或外网路径测试。
- macOS：安装版 v5.6.0 进程仍在运行。本轮没有点击网络、隧道、共享、登录或升级控件；前面记录的向导 A/B/C 键盘导航有效。控件级主要流程仍受 Computer Use runtime 缺失、辅助功能只暴露窗口级元素影响；任何可能触发登录、共享或系统网络操作的控件均未盲点。
- Android API 36 模拟器及 Windows x64 hosted VM 的完整范围沿用上表已成功记录的最新 Actions 证据；Android 真机硬件行为、Windows 用户实机不在本轮证据范围。没有执行商店发布或付费签名。
- 本轮保留既有 `docs/PROJECT_CLOSURE_PLAN.md` 修改与 `交付物/`，未覆盖或清理；未对项目应用代码作改动。

## 本地回归修复

- 修复 `tests/test_shared_proxy_loopback.py` 的本地模拟控制台线程在一次空闲 socket timeout 后退出的问题；新增空闲超过 timeout 后仍可回环访问的回归用例。
- Android 新增验收专用 Keystore/前台服务探针、空凭据合成 fixture 与流程检查。生产/商店 APK 不包含探针模块；目标分支相关 push/PR 与显式手动验收会加入探针，结束时清除模拟器数据。
- Windows hosted VM 脚本增加独立目录合成档案的格式/重启持久化检查，并增加公开 EXE 的下载校验。
- Android fixture 传入修复新增 `test_fixture_transfer_uses_direct_run_as_commands`；新增前台服务有界等待及诊断测试 `test_foreground_service_assertion_waits_for_startup_and_reports_state`，定向 7 tests passed；当时完整本地套件 `python3 -m unittest discover -s tests` 为 568 passed、3 skipped。当前 head 的 PR CI `39560792142` Windows/macOS 全套测试、ruff `F,E9` 静态检查均 success。
- 修复 desktop-candidate detector 只比较 `HEAD^`、遗漏同一 PR 先前代码提交的问题：PR 场景现在比较 base SHA 到 HEAD；新增 `test_desktop_candidate_detects_changes_across_the_entire_pull_request`，commit `2d086b7`。PR run `39550469356` 已确认 Windows VM 与 macOS build 都实际执行。

## PR CI / 桌面候选 Actions

| run | 结果 | 证据与边界 |
|---|---|---|
| PR CI `39560792142` | success | head `e2cfd90` 的 Windows/macOS 全套测试、静态、版本、页面和敏感值检查通过；Release 与 PR Android release job 按规则 skip。 |
| Desktop candidate `39560792145` | success | Windows x64 VM 源码候选、公开 v5.6.0 EXE 向导/持久化验收通过；macOS arm64 candidate build、签名检查和 runner launch 上传通过。 |
| Android `39560792156` | success | API 36 APK build、Manifest/KVM gate、模拟器安装/启动和验收脚本均通过；两个 artifact 已下载回读并核对 SHA-256/CRC。 |

## 待补终态

终态：当前 head `e2cfd905c42d0fd0c54330784fc39284d9f86186` 的 CI `39560792142`、Desktop candidate `39560792145`、Android API 36 emulator `39560792156` 均 success。Windows x64 hosted VM 对源码候选和公开 v5.6.0 EXE 的首次向导、Plan A 导航、合成配置跨根进程重启通过；未触发网络/热点。Android APK 与模拟器证据 artifact 已下载回读并校验；配置探针、前台服务、进程重启、模拟 Wi-Fi 关闭/恢复通过。macOS 本机 v5.6.0 运行、bundle 与 adhoc strict 签名通过，但 Tk 控件逐项验收未覆盖。Computer Use runtime 连续三次未能启动，另一 UI 状态接口报告 Mac 锁屏且无法自动解锁。iPhone USB 配对有效、AirplaneMode=false；只读启动 USB WebKit proxy 后 `/json` 返回空数组，随后代理已停止。此前 PWA 主屏安装与在线启动有 iPhone 设备记录；本轮未读到 Safari target。公开 Pages TLS/核心资源、桌面首页和响应式已复核；Service Worker 根页缓存存在，但离线模拟时主文档仍由网络来源返回，离线冷启动未证实。隧道共享系统授权提示不可见，未批准来源不明请求；Mac 到 iPhone 外网流量验证未覆盖。PR #6 open，head/origin 均为 `e2cfd90`。原有 `docs/PROJECT_CLOSURE_PLAN.md` 修改和 `交付物/` 未触碰。恢复 native app Computer Use 前需手动解锁 Mac 并重启 Codex/ChatGPT 桌面应用；之后在 iPhone Safari 打开项目 Pages，待 USB Web Inspector target 可读后再继续手机缓存和已授权的隧道共享验收。
