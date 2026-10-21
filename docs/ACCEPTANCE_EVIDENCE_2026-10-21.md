# 验收收尾记录（2026-10-21）

本文件记录本轮独立验收证据。项目原有的 `docs/PROJECT_CLOSURE_PLAN.md` 和 `交付物/` 属于既有工作，本轮没有覆盖或清理。

## 证据边界

- 源码/回归测试、Actions 构建、Actions 虚拟机/模拟器运行、Mac 本机运行、iPhone USB/Safari、真实网络路径分别记录；一种证据不替代另一种。
- 本轮不做商店发布、付费签名或 Android 真机验收。Windows 实机最终交由用户指定的 Windows AI。
- 设备测试只用空账号/合成资料和本机回环地址；没有输入校园网账号或密码。

## 网站 / PWA

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| GitHub Pages | 已通过 | 生产页面 `https://campusnettools.github.io/campus-net-manager/` 可打开；最近部署 run `39388792710` success。页面有软件下载、安装引导、隐私边界与 PWA 添加说明。 |
| v5.6.0 下载资产 | 已通过校验 | APK `16fe62629ea30c3ab59d59fd12e0160d5b8dac6d0ba5a8c84342b9e1b1b7937e`；macOS ZIP `07a92be36aa279020b9efadc1bccd9f4ba9f66b4f2ce001ab35a748a4f9f685b`；Windows EXE `a0faeff9ea197e7e34be582059fdfc64d97679e6cfac265010c3bc9df337c689`。发布 API digest、下载文件和 `.sha256` sidecar 一致；APK 与 macOS ZIP CRC 通过，Windows 为 x64 PE32+ GUI。 |
| 桌面浏览器/PWA 页面 | 已通过（页面可用性） | 本轮当前浏览器无障碍树可读到已渲染的首页与各平台下载/帮助入口。之前同一验收轮次记录过窄屏无横向溢出和离线 shell 缓存恢复；离线结果不代表 iPhone 已验收。 |
| iPhone 主屏安装、Safari 远程页面、缓存离线恢复 | 未完成 | USB 配对仍有效（设备枚举数量 1，`idevicepair validate` 成功）；没有本轮可回读的 iPhone 页面/主屏截图或 Safari DOM 证据。先前尝试输入页面地址时界面没有落到预期项目域名，因此已停止交互；没有打开陌生页面、提交信息或更改网络设置。 |

## macOS

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| v5.6.0 安装包与运行 | 已通过 | 公共 ZIP SHA-256 与 Release API digest/sidecar 一致；CRC 通过；`ditto` 解包保留 62 个 symlink，`codesign --verify --deep --strict` 通过。Bundle `com.campusnettools.campusnetmanager`，v5.6.0，adhoc、无 Team ID。当前安装版同 bundle/version/signature，进程运行且窗口标题 v5.6.0。 |
| 界面逐项操作/向导 | 未覆盖 | 只能读到窗口标题和少量窗口系统按钮；Tk 内容控件没有可用的辅助功能标签。坐标自动化曾误触，不再据坐标执行设置类点击。 |
| 只读网络诊断 | 部分失败 | 一次本机代理可达性提示显示回环地址 `127.0.0.1:7890` 不可达；没有保存配置、启动隧道或更改 Wi-Fi/VPN/热点。 |
| 隧道共享到 iPhone 外网 | 未覆盖 | 热点窗口可见已连接客户端，但无法确认客户端身份；本轮没有批准来源身份不明的请求，没有证明 iPhone 通过 Mac 出口访问外网。 |
| 升级流程 | 未覆盖 | 没有在真实用户数据上执行升级；开发者签名/公证不属于本目标范围。 |

## Android API 36 模拟器

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| v5.6.0 公共 APK | 已通过下载包校验 | 公共 Release APK SHA-256 `16fe62629ea30c3ab59d59fd12e0160d5b8dac6d0ba5a8c84342b9e1b1b7937e`。本轮 run `39542561956` 的 API36 debug APK sidecar 与下载文件 SHA-256 一致：`98b41da9aa4dd8efc11a4a3871290e316c9eff4191ef66dd91f45f2e367d974e`；ZIP CRC 通过。 |
| API 36 安装/启动/UI | 已通过（run `39542561956`，源码 `d1265da`） | APK 构建、Manifest gate、KVM、模拟器安装启动和运行 smoke success；回读截图显示“非校园网环境（认证服务器不可达）”，不是卡在加载态；日志有 `CNM_NETWORK_STATUS_READY`，无 `FATAL EXCEPTION`。该旧 run 未运行新 Keystore/前台服务探针，不覆盖真机硬件。 |
| Keystore、前台服务、进程重启、模拟 Wi-Fi 变化 | 本轮待 Actions | 新增模拟器探针使用空凭据、仅 `127.0.0.1:9` 的合成档案；会核对 Android Keystore 密文、进程重启后解密、服务确实处于 foreground、模拟器 Wi-Fi 状态切换及原状态恢复，并在结束时清除模拟器 app 数据。等探针提交对应 Actions 后补写终态。 |
| 真机锁屏/硬件行为 | 未覆盖 | 按用户目标不用 Android 真机；模拟器结果不等同电池/厂商后台策略验收。 |

## Windows x64 hosted VM

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| 当前源码候选包 | 已通过（主界面/向导导航） | run `39542762333` 构建、runner UI smoke、向导和 Plan A 导航通过；没有触发 Wi-Fi/热点操作。 |
| 公开 v5.6.0 EXE 校验与 UI/持久化重启 | 本轮待 Actions | 新增 VM 步骤会比对 Release API digest、`.sha256` 与下载文件，然后用空账号、回环 URL、关闭自动更新的隔离配置检查 JSON 持久化和进程重启。结果未回读前不记为通过。 |
| 代理流程/真实网络 | 未覆盖 | hosted VM 不连接真实校园网、热点或手机网络；本轮探针不得请求外网认证。 |
| Windows 实机 | 延后 | 本目标结束后交给用户指定的 Windows AI 按本机说明执行。 |

## 本地回归修复

- 修复 `tests/test_shared_proxy_loopback.py` 的本地模拟控制台线程在一次空闲 socket timeout 后退出的问题；新增空闲超过 timeout 后仍可回环访问的回归用例。
- Android 新增验收专用 Keystore/前台服务探针、空凭据合成 fixture 与流程检查。生产/商店 APK 不包含探针模块；目标分支相关 push/PR 与显式手动验收会加入探针，结束时清除模拟器数据。
- Windows hosted VM 脚本增加独立目录合成档案的格式/重启持久化检查，并增加公开 EXE 的下载校验。
- 本地完整 `unittest discover -s tests` 为 565 passed、3 skipped；定向测试 28 passed；ruff F/E9、Python 编译、Bash 语法、YAML 解析和 diff 检查通过。

## 待补终态

补写本轮 push 后 Android 模拟器、Windows hosted VM、PR CI 与 Desktop candidate Actions 的 run ID、逐 job 结果、artifact 回读和哈希；不得将未回读项表述为成功。
