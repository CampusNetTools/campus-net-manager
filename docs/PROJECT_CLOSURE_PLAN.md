# 校园网连接管家全端闭环基线

更新时间：2026-10-16  
基线提交：`57f9640e322a7525f4eb0f99967051e6256ba9bd`  
可恢复标签：`codex/full-project-closure-baseline-2026-10-16`

Android 前台保活改动前检查点：提交 `c03bfd26817b14eb4aabefabf4fc8678d6f2db38`，标签 `codex/android-fgs-before-2026-10-16`。

## 目标

按平台完成现有功能的开发、自动检测、构建、部署、真实设备验收和正式发布。源码、单元测试、CI 构建、安装包、已安装运行和商店上线分别记录，不能互相替代。

## 平台交付矩阵

| 平台 | 当前基线 | 完成条件 |
|---|---|---|
| Windows 桌面 | Python/Tkinter 主程序；GitHub 已发布 v5.5.0 exe | README 中的桌面功能逐项验收；当前源码通过测试；构建、签名/安全检查、安装、启动和升级验证；Release 资产及 SHA256 远端回读 |
| macOS 桌面 | Apple Silicon 构建脚本；GitHub 已发布 v5.5.0 zip | 功能逐项验收；本机 `.app` 构建、安装、启动和升级验证；正式分发签名与公证状态明确；Release 资产回读 |
| Android | Kivy 登录/环境检查/档案/前台保活原型；只有 debug APK 构建证据 | 后台保活通过系统前台服务实现，用户可见、可停止、可恢复；凭据存储与网络切换处理完成；Android API 36 构建；单元/打包/真实设备测试；signed AAB、Play 测试和正式发布 |
| iOS | SwiftUI Packet Tunnel 原型；配对网关缺失。历史已选系统 IKEv2 | 改用 `NEVPNManager` + `NEVPNProtocolIKEv2`，连接现有 strongSwan 网关；配置、凭据、VPN 状态和错误处理可用；Xcode 编译、签名、真机验证；App Store 资料与审核完成 |

## 已核实基线

- 当前分支 `codex/full-project-closure` 从 `main` 提交 `57f9640` 派生；开始改动前工作树干净，另有可恢复基线标签。
- `APP_VERSION` 为 `5.5.0`。已有 Python 测试 485 项通过、3 项跳过；这些测试不能证明 UI、打包、设备或商店验收。
- 桌面端最新 Release 为 2026-09-17 的 v5.5.0；CI 最近一次主线运行在 2026-09-21 成功。
- Android `mobile/buildozer.spec` 当前 `android.api=35`，此前只有 2026-09-06 的 debug APK Actions 成功记录。
- iOS 自定义 Packet Tunnel 代码没有配套 Mac TLS/TUN 网关。项目已有 strongSwan IKEv2 生成/安装脚本，故 iOS App 优先走系统 IKEv2，而不是引入另一套 VPN 数据面。
- 当前 Mac 缺完整 Xcode、XcodeGen、Java、Android SDK/adb 和 Buildozer；没有 iOS provisioning profile 或已安装的 CampusNetManager.app。真机与商店发布需另行获得设备/账号证据。

## 阶段顺序

1. Android 后台保活和手机端凭据/网络生命周期。
2. iOS `NEVPNManager` IKEv2 客户端，复用现有 Mac strongSwan 路线。
3. Windows/macOS 桌面功能清单逐项运行验收，修复发现的缺口并重建部署。
4. Android/iOS 真机验收，处理商店签名、隐私、测试轨道和审核要求。
5. 更新 `HANDOFF.md`、README、版本记录与 release workflow；完成桌面和手机商店发布回读。

## 当前 Android 检查点（2026-10-16）

- 已接入 `campusguard` sticky foreground service 源码：串行每分钟检测认证/互联网，掉线后重登并复检；服务状态文件不写账号或密码，UI 每 5 秒读取服务状态。用户可从 App 显式启动/停止，Android 13+ 先申请通知权限。
- Buildozer 已切到 API 36、p4a `v2026.05.09`、Python/hostpython 3.11.8 和 Kivy 2.3.0；manifest 使用 `specialUse`，工作流固定 p4a 源码 tag 并注入 Google 要求的 subtype 说明，再对 APK manifest 作构建期校验。
- 当前完整 Python 测试 `497 passed, 3 skipped`；手机服务/manifest patch 专项 12 项通过；Python 编译、版本同步、控制台 HTML lint（8/8）、secret scan 通用模式、workflow YAML 解析及 `git diff --check` 通过。
- 这些证据只覆盖源码与本地检查。API 36 APK 构建、合并后 manifest、手机安装、锁屏/切网持续运行均未验证。当前机器缺 Java Runtime、Android SDK/adb 和 Buildozer；`xcodebuild` 只有 CommandLineTools stub，完整 Xcode 不可用。
- Android 档案现通过 Java Android Keystore AES-GCM helper 写入 `profile.enc`；旧版明文 `profile.json` 会在加密迁移成功后删除。文件仍原子写入并设置 POSIX `0600`，Android backup 关闭。Python 层有加解密边界测试，但 Android Java 编译、真实密钥生成/轮换/迁移仍待 APK 和真机验证。

## 外部发布门槛

- Google Play 新应用和更新当前要求 target API 36；若开发者是 2023-11-13 后创建的个人账号，申请生产发布前需 12 名测试者连续参加封闭测试 14 天。
- Apple VPN App Store 发布需组织开发者账号，并按审核要求披露网络数据处理；账号、法律主体、隐私政策和实际审核需用户本人参与。
- 不把开发者密码、验证码、签名私钥或账号恢复码写入仓库/记忆。

## 验收记录模板

每个功能记录：源码位置、自动测试、打包结果、安装设备和 OS、操作步骤、可观察结果、失败/恢复证据、版本/构建号。未覆盖的步骤写明“未验证”，不以推测补齐。
