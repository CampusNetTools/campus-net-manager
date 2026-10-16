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
| Android | Kivy 登录/环境检查/档案/前台保活；API 36 APK 与 unsigned AAB 正在 Actions 构建 | 后台保活通过系统前台服务实现，用户可见、可停止、可恢复；凭据存储与网络切换处理完成；Android API 36 构建；单元/打包/真实设备测试；signed AAB、Play 测试和正式发布 |
| iOS | SwiftUI 系统 IKEv2 客户端源码已接入；Mac enrollment 输出与 unsigned simulator build workflow 已加入 | 编译/签名、真实证书安装、IKEv2 连接和双向流量、真机升级、App Store 资料与审核仍需验证 |

## 已核实基线

- 当前分支 `codex/full-project-closure` 从 `main` 提交 `57f9640` 派生；开始改动前工作树干净，另有可恢复基线标签。
- `APP_VERSION` 为 `5.5.0`。已有 Python 测试 485 项通过、3 项跳过；这些测试不能证明 UI、打包、设备或商店验收。
- 桌面端最新 Release 为 2026-09-17 的 v5.5.0；CI 最近一次主线运行在 2026-09-21 成功。
- Android 当前 `mobile/buildozer.spec` 目标 API 为 36；尚无本轮 API 36 APK/AAB 构建成功或商店发布记录。
- iOS 原 Packet Tunnel 代码没有配套 Mac TLS/TUN 网关，已从正式 App target 移除；项目已有 strongSwan IKEv2 生成/安装脚本，iOS App 使用系统 IKEv2。
- 当前 Mac 缺完整 Xcode、XcodeGen、Java、Android SDK/adb 和 Buildozer；没有 iOS provisioning profile 或已安装的 CampusNetManager.app。真机与商店发布需另行获得设备/账号证据。

## 阶段顺序

1. Android 后台保活和手机端凭据/网络生命周期。
2. iOS `NEVPNManager` IKEv2 客户端，复用现有 Mac strongSwan 路线。
3. Windows/macOS 桌面功能清单逐项运行验收，修复发现的缺口并重建部署。
4. Android/iOS 真机验收，处理商店签名、隐私、测试轨道和审核要求。
5. 更新 `HANDOFF.md`、README、版本记录与 release workflow；完成桌面和手机商店发布回读。

## 当前 Android 检查点（2026-10-16）

- 已接入 `campusguard` sticky foreground service 源码：串行每分钟检测认证/互联网，掉线后重登并复检；服务状态文件不写账号或密码，UI 每 5 秒读取服务状态。用户可从 App 显式启动/停止，Android 13+ 先申请通知权限。
- Buildozer 目标 API 36、p4a `v2026.05.09`、Python/hostpython 3.11.8 和 Kivy 2.3.1；manifest 使用 `specialUse`，工作流固定 p4a 源码 tag 并注入 subtype 说明，再对 APK manifest 作构建期校验。
- 当前完整 Python 测试 `500 passed, 3 skipped`；手机服务/Manifest patch 专项 14 项通过；Python 编译、版本同步、控制台 HTML lint（8/8）、secret scan 通用模式、workflow/YAML 解析及 `git diff --check` 通过。
- 这些证据只覆盖源码与本地检查。API 36 APK 构建、合并后 manifest、手机安装、锁屏/切网持续运行均未验证。当前机器缺 Java Runtime、Android SDK/adb 和 Buildozer；`xcodebuild` 只有 CommandLineTools stub，完整 Xcode 不可用。
- Android 档案现通过 Java Android Keystore AES-GCM helper 写入 `profile.enc`；旧版明文 `profile.json` 会在加密迁移成功后删除。文件仍原子写入并设置 POSIX `0600`，Android backup 关闭。Python 层有加解密边界测试，但 Android Java 编译、真实密钥生成/轮换/迁移仍待 APK 和真机验证。
- GitHub Actions run `38851368170` 对提交 `28c55dd` 的 API 36 构建曾失败：Kivy 2.3.0 生成的 `cgl_gl.c` 在 NDK r28c Clang 下因 `glShaderSource` 函数指针 const 限定不匹配而终止。Buildozer 已改为 pin `kivy==2.3.1`。随后 run `38852810567` 仍失败：p4a `v2026.05.09` 执行 `pip install -U pip` 时，日志为 `ImportError: cannot import name 'open_rich_spinner'`。固定 p4a patch 已加入创建 venv 时 `--clear` 的修复。APK run `38856748022`（head `cf794ed`）已编译成功，但后续 Manifest 校验准确发现没有生成服务声明；Actions 中真实 Buildozer 命令不含 `--service`，根因是 `mobile/buildozer.spec` 把服务键写成了不受支持的 `android.services`，Buildozer 读取的键名为 `services`。当前工作树已改正配置并加回归检查，待提交和新 Actions 构建验证。unsigned AAB run `38856949123`（head `2c83f6b`）成功完成 API 36 构建、移除临时签名并验证 unsigned 状态，artifact `12028181480` CRC 检查通过（47 个条目，无 JAR 签名文件，SHA-256 `45b5d9579a47bc3c6f81662f8f76044300f3e1383b0115ec54dabcb245d80dc9`）。这仅证明产物构建与结构检查，不代表 Play Console 接收或设备安装。signed AAB 仍需真实上传密钥。
- iOS `NEVPNManager` + `NEVPNProtocolIKEv2` 的 unsigned simulator workflow 已在 run `38852926224` 对提交 `38ccfef` 构建成功。head `a349b8b` 的 run `38855620015` 成功完成 simulator 编译、安装和启动，但 artifact `12026888784` 下载后发现 `.app` 顶层目录被展平。修复后的 run `38856309857`（head `a15e83d`）成功完成 simulator 编译、安装、启动、ZIP 打包和 artifact 上传；artifact `12027332700` 内含完整 `CampusNetCompanion.app/` 目录结构。bundle id `com.campusnettools.companion`、版本 `0.2.0 (3)`、Simulator 支持 `x86_64/arm64`，adhoc/linker 签名且无 Team ID；ZIP SHA-256 为 `267682d52e82b7e6047d71a8bb364b5c975d348192c86d8d8e842316b333364b`。以上不证明真机安装、证书信任、IKEv2 连通、双向流量或 App Store 发布。
- 随后扩展 iOS workflow：run `38853483784` 的编译成功，但 Simulator 安装失败，日志指出 `.app` 的 `Info.plist` 缺少有效 `CFBundleExecutable`。补上 `$(EXECUTABLE_NAME)` 与 `$(PRODUCT_NAME)` 后，run `38853975796` 已在 iPhone Simulator 编译、安装、启动成功，并上传 unsigned `.app` artifact（ID `12026980614`，SHA-256 `e30d3d4bc9d5f7cbc426a1d068fca5c43583f6c0e025b20620e575be174afe32`）。模拟器启动不替代真机 VPN 与网络验收。
- 新增 Android API 36 AAB 手动 workflow：unsigned 模式用 runner 临时密钥满足 Buildozer/Gradle 的签名任务，再移除临时 JAR 签名块并检查 bundle 确实无签名；signed 模式要求 GitHub Actions secrets 提供 Play upload keystore 和 alias 信息，构建后验证签名并上传 artifact。它不会自动发布到 Google Play。run `38856949123` 已证实 unsigned AAB 真实构建与剥除临时签名成功。
- 草稿 PR #1 当前 head `2c83f6b4a4c8f92155ce50c25d3a2275c949ea2e` 的 CI run `38856946133` 已完成，macOS 与 Windows 测试/静态检查均通过，Release 构建 job 按 PR 事件配置跳过。该证据不代表 Windows 安装/运行或桌面逐功能验收。

## 最新核验（2026-10-16）

- 本次 macOS 构建基于 `codex/full-project-closure` 的源码提交 `38ccfef7efe7aa6586d2bcd3cd1aefcad0057ca2`；安装验证开始前工作树干净。该提交完整 Python 测试为 `498 passed, 3 skipped`。
- 本机以项目 `.venv` 的 Python 3.13.12 / PyInstaller 6.22.2 成功构建 Apple Silicon `.app`，并安装到 `/Applications/校园网连接管家.app`。安装前 5.0.15 包已备份至 `archives/installed-macos-5.0.15-2026-10-16/`，恢复说明随包保留。
- 安装包 `CFBundleShortVersionString` 和 `CFBundleVersion` 均为 5.5.0；`codesign --verify --deep --strict` 通过，Mach-O 为 arm64，应用已成功启动，进程路径位于 `/Applications/校园网连接管家.app/Contents/MacOS/校园网连接管家`，窗口显示 v5.5.0。
- 该本机构建使用 ad-hoc 签名，未进行 Apple Developer 分发签名或公证。桌面全功能逐项验收、Windows 端当前版本重新构建/安装、macOS 跨版本升级和 Release 资产回读仍待完成。

## 外部发布门槛

- Google Play 新应用和更新当前要求 target API 36；若开发者是 2023-11-13 后创建的个人账号，申请生产发布前需 12 名测试者连续参加封闭测试 14 天。
- Apple VPN App Store 发布需组织开发者账号，并按审核要求披露网络数据处理；账号、法律主体、隐私政策和实际审核需用户本人参与。
- 不把开发者密码、验证码、签名私钥或账号恢复码写入仓库/记忆。

## 验收记录模板

每个功能记录：源码位置、自动测试、打包结果、安装设备和 OS、操作步骤、可观察结果、失败/恢复证据、版本/构建号。未覆盖的步骤写明“未验证”，不以推测补齐。
