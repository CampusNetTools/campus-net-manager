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
| Android | Kivy 登录/环境检查/档案/前台保活；API 36 debug APK 与 unsigned AAB 已在 Actions 构建成功 | 后台保活通过系统前台服务实现，用户可见、可停止、可恢复；凭据存储与网络切换处理完成；Android API 36 构建；单元/打包/真实设备测试；signed AAB、Play 测试和正式发布 |
| iOS | SwiftUI 系统 IKEv2 客户端源码已接入；Mac enrollment 输出与 unsigned simulator build workflow 已加入 | 编译/签名、真实证书安装、IKEv2 连接和双向流量、真机升级、App Store 资料与审核仍需验证 |

## 已核实基线

- 当前分支 `codex/full-project-closure` 从 `main` 提交 `57f9640` 派生；开始改动前工作树干净，另有可恢复基线标签。
- `APP_VERSION` 为 `5.5.0`。已有 Python 测试 485 项通过、3 项跳过；这些测试不能证明 UI、打包、设备或商店验收。
- 桌面端最新 Release 为 2026-09-17 的 v5.5.0；CI 最近一次主线运行在 2026-09-21 成功。
- Android 当前 `mobile/buildozer.spec` 目标 API 为 36；本轮 debug APK 和 unsigned AAB 均已构建成功，尚无真机安装/运行和商店发布记录。
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
- 当前已有 API 36 APK 构建和合并 Manifest 的 Actions 证据（见下文）；手机安装、锁屏/切网持续运行仍未验证。当前机器缺 Android SDK/adb 和 Buildozer；`xcodebuild` 只有 CommandLineTools stub，完整 Xcode 不可用。
- Android 档案现通过 Java Android Keystore AES-GCM helper 写入 `profile.enc`；旧版明文 `profile.json` 会在加密迁移成功后删除。文件仍原子写入并设置 POSIX `0600`，Android backup 关闭。Python 层有加解密边界测试，但 Android Java 编译、真实密钥生成/轮换/迁移仍待 APK 和真机验证。
- GitHub Actions run `38851368170` 对提交 `28c55dd` 的 API 36 构建曾失败：Kivy 2.3.0 生成的 `cgl_gl.c` 在 NDK r28c Clang 下因 `glShaderSource` 函数指针 const 限定不匹配而终止。Buildozer 已改为 pin `kivy==2.3.1`。随后 run `38852810567` 仍失败：p4a `v2026.05.09` 执行 `pip install -U pip` 时，日志为 `ImportError: cannot import name 'open_rich_spinner'`。固定 p4a patch 已加入创建 venv 时 `--clear` 的修复。APK run `38856748022`（head `cf794ed`）已编译成功，但后续 Manifest 校验发现没有生成服务声明；实际 Buildozer 命令不含 `--service`，根因为 `mobile/buildozer.spec` 错写 `android.services`，Buildozer 读取的键名是 `services`。提交 `7934fb1` 已修正配置并增加回归检查。APK run `38879167090`（head `7934fb1`）现已成功完成 API 36 debug 构建和合并 Manifest 校验；p4a 命令含 `--service campusguard:...:foregroundServiceType=specialUse`，required service/type/subtype/`0x400` 检查均通过。artifact `12037616953` 下载后 ZIP CRC 通过，含 arm64-v8a 和 armeabi-v7a，SHA-256 `0a49e56c35b734843ef2e0f3dcc2e0142afcd8252c44efab1aa637059f1822df`。这不代表安装、锁屏/切网、Keystore 真机验收或 Play 发布。unsigned AAB run `38856949123`（head `2c83f6b`）成功完成 API 36 构建、移除临时签名并验证 unsigned 状态，artifact `12028181480` CRC 检查通过（47 个条目，无 JAR 签名文件，SHA-256 `45b5d9579a47bc3c6f81662f8f76044300f3e1383b0115ec54dabcb245d80dc9`）。signed AAB 仍需真实上传密钥。
- iOS `NEVPNManager` + `NEVPNProtocolIKEv2` 的 unsigned simulator workflow 已在 run `38852926224` 对提交 `38ccfef` 构建成功。head `a349b8b` 的 run `38855620015` 成功完成 simulator 编译、安装和启动，但 artifact `12026888784` 下载后发现 `.app` 顶层目录被展平。修复后的 run `38856309857`（head `a15e83d`）成功完成 simulator 编译、安装、启动、ZIP 打包和 artifact 上传；artifact `12027332700` 内含完整 `CampusNetCompanion.app/` 目录结构。bundle id `com.campusnettools.companion`、版本 `0.2.0 (3)`、Simulator 支持 `x86_64/arm64`，adhoc/linker 签名且无 Team ID；ZIP SHA-256 为 `267682d52e82b7e6047d71a8bb364b5c975d348192c86d8d8e842316b333364b`。以上不证明真机安装、证书信任、IKEv2 连通、双向流量或 App Store 发布。
- 随后扩展 iOS workflow：run `38853483784` 的编译成功，但 Simulator 安装失败，日志指出 `.app` 的 `Info.plist` 缺少有效 `CFBundleExecutable`。补上 `$(EXECUTABLE_NAME)` 与 `$(PRODUCT_NAME)` 后，run `38853975796` 已在 iPhone Simulator 编译、安装、启动成功，并上传 unsigned `.app` artifact（ID `12026980614`，SHA-256 `e30d3d4bc9d5f7cbc426a1d068fca5c43583f6c0e025b20620e575be174afe32`）。模拟器启动不替代真机 VPN 与网络验收。
- 新增 Android API 36 AAB 手动 workflow：unsigned 模式用 runner 临时密钥满足 Buildozer/Gradle 的签名任务，再移除临时 JAR 签名块并检查 bundle 确实无签名；signed 模式要求 GitHub Actions secrets 提供 Play upload keystore 和 alias 信息，构建后验证签名并上传 artifact。它不会自动发布到 Google Play。run `38856949123` 已证实 unsigned AAB 真实构建与剥除临时签名成功。
- 草稿 PR #1 当前 head `2c83f6b4a4c8f92155ce50c25d3a2275c949ea2e` 的 CI run `38856946133` 已完成，macOS 与 Windows 测试/静态检查均通过，Release 构建 job 按 PR 事件配置跳过。该证据不代表 Windows 安装/运行或桌面逐功能验收。

## 最新核验（2026-10-16）

- 在提交 `7934fb1` 后的 PR CI run `38879156449` 中，Windows job 的新回归测试因 Windows 默认 cp1252 无法解码 UTF-8 `buildozer.spec` 而失败；测试已改为显式 UTF-8 读取。修复后的 PR CI run `38879597002`（head `077a4c6`）和仅更新文档的 run `38880252368`（head `70ab644`）macOS 与 Windows 测试/静态检查均通过。APK run `38879167090` 已完成并上传 artifact `12037616953`，Manifest 校验通过；构建与 artifact 检查不代表手机安装或 Play 验收。
- 本次 macOS 构建基于 `codex/full-project-closure` 的源码提交 `38ccfef7efe7aa6586d2bcd3cd1aefcad0057ca2`；安装验证开始前工作树干净。该提交完整 Python 测试为 `498 passed, 3 skipped`。
- 本机以项目 `.venv` 的 Python 3.13.12 / PyInstaller 6.22.2 成功构建 Apple Silicon `.app`，并安装到 `/Applications/校园网连接管家.app`。安装前 5.0.15 包已备份至 `archives/installed-macos-5.0.15-2026-10-16/`，恢复说明随包保留。
- 安装包 `CFBundleShortVersionString` 和 `CFBundleVersion` 均为 5.5.0；`codesign --verify --deep --strict` 通过，Mach-O 为 arm64，应用已成功启动，进程路径位于 `/Applications/校园网连接管家.app/Contents/MacOS/校园网连接管家`，窗口显示 v5.5.0。
- 该本机构建使用 ad-hoc 签名，未进行 Apple Developer 分发签名或公证。桌面全功能逐项验收、Windows 端当前版本重新构建/安装、macOS 跨版本升级和 Release 资产回读仍待完成。

## 最新 Android APK 与 PR 验证（2026-10-16）

- 最新代码提交 `6ce3418624ccae990b79ae826126553e0fd520d7` 将 Kivy 表单数据读取移到 UI 线程，并增加 worker 线程安全回归检查。完整本地测试为 `505 passed, 3 skipped`；PR CI run `38885818918` 的 Windows/macOS 测试与静态检查均成功，Release job 因 PR 事件跳过。
- 对该提交运行的 API 36 APK workflow `38886079868` 成功完成编译、合并 Manifest 服务声明校验和 artifact 上传。Manifest gate 成功检查 `ServiceCampusguard`、前台服务类型与 special-use subtype。artifact `12040262849` 下载后 ZIP CRC 检查通过；包内 APK `campusnetmanager-1.0.0-arm64-v8a_armeabi-v7a-debug.apk` SHA-256 为 `fd09f7d45f54039c320d0a05d1d9a4e3f5896452ab3e490f3954d3bdff69b334`。
- 以上仅证明指定提交的 CI、debug 包和 Manifest 检查；APK 未安装到真实手机，锁屏/切网、Keystore 运行时、signed AAB、Play Console 接收和商店发布仍未验证。当前 Mac 没有 `adb`、完整 Xcode 或 iOS provisioning profile。

## macOS Release 符号链接复核（2026-10-16）

- 下载并校验 GitHub v5.5.0 macOS Release ZIP：SHA-256 与 GitHub asset digest 一致（`130176b766f1af368e509617cae7c500ce0454c66b76c3e8c97d4519891e5769`），ZIP CRC 检查通过，包内版本和 bundle id 为 `5.5.0` / `com.campusnettools.campusnetmanager`。
- 对该 Release 解压副本运行 `codesign --verify --deep --strict` 失败，系统报告 `Contents/Frameworks/Python.framework` 的 bundle format ambiguous。检查 ZIP 条目发现 Python.framework 的 `Python`、`Resources`、`Versions/Current` 链接被记录成普通文件/目录。当前工作流原先使用 `zip -rq`，会解引用符号链接；更新器又使用 Python `ZipFile.extractall`，不会恢复 macOS 符号链接。
- 源码修复改用 macOS `ditto` 创建 Release ZIP，并在打包后逐一对比源 `.app` 符号链接与 ZIP 的 Unix mode；更新器对经过 SHA-256 校验的包先拒绝绝对路径和 `..`，再使用 `ditto -x -k` 解压。macOS 集成测试创建标准 Python.framework 链接夹具并验证往返后链接仍存在；本机当前 PyInstaller `.app` 的 55 个符号链接也通过发布包检查。
- v5.5.0 是已有旧资产，此次源码改动不会修复或替换该 Release。后续必须用修复后的 release workflow 生成新包，并重新检查符号链接、签名与升级安装；未创建 tag 或发布新版本。
- 基于提交 `9eb93d0` 用项目 `.venv` / PyInstaller 6.22.2 重建并替换本机 app；替换前将现有 5.5.0 包备份到 `archives/installed-macos-5.5.0-before-symlink-fix-2026-10-16/` 并附恢复说明。候选仍显示版本 5.5.0 / bundle id `com.campusnettools.campusnetmanager`，adhoc `codesign --verify --deep --strict` 通过，进程从 `/Applications/校园网连接管家.app/Contents/MacOS/校园网连接管家` 运行，窗口标题显示 v5.5.0。Computer Use runtime 未启动，界面自动化只读到顶层窗口；功能逐项和自动升级仍未验收。
- 按 Release workflow 对该安装包本机模拟复制、`ditto` ZIP、符号链接检查和 updater 解压；55 个链接在 ZIP 中均为 symlink，解压后 `codesign --verify --deep --strict` 通过。临时候选 ZIP SHA-256 为 `c1d483d61c0f3fdad0da6953d256df517564b2ffc6d55ec73bc125929c6baa4a`，校验后临时目录已清理；未上传或发布。

## Android UI 线程安全复核（2026-10-16）

- 代码审查发现手机端 `refresh_status`、`manual_login` 和桌面开发回退保活的后台 worker 会读取 Kivy `TextInput` / `Spinner` 表单值。Kivy 控件应由 UI 线程访问，这可能造成状态检测或登录与界面操作并发时读值不稳定。
- 已在线程启动前复制认证 URL 和登录档案；worker 仅使用普通 Python 数据。新增 AST 回归检查，阻止这三个 worker 再调用表单读取/保存方法。
- 新回归与服务专项共 10 项通过；完整 Python 测试 `505 passed, 3 skipped`，CI 同规则 Ruff 检查及 `py_compile` 通过。
- 当前电脑没有 `adb`、完整 Xcode 或 iOS provisioning profile；上述结论是源码与自动测试证据，不代表 Android/iOS 真机行为。

## 桌面候选包构建与产物复核（2026-10-16）

- 提交 `2d38e3bbb7ffe8c08e0e87532d34a529624595dc` 的 PR 候选包 workflow run `38891904445`（PR #1）在 macOS 与 Windows runner 均成功。两个平台都完成打包、启动烟雾步骤并上传候选 artifact；配套 PR CI run `38891904288` 的 Windows/macOS 测试与静态检查通过，发布 job 因 PR 事件跳过。
- Windows artifact `12042510841`（`campusnetmanager-windows-candidate`）包含 x86-64 PE GUI 可执行文件 `CampusNetManager-windows.exe` 与 SHA-256 sidecar。下载复核值一致：`34eca07cd2281fa49bf1699fdee33695ee3a7925132f33b6df520511b8c3674b`。Actions 启动烟雾步骤通过；尚未在用户 Windows 设备安装，也未逐项验收桌面功能。
- macOS artifact `12041594097`（`campusnetmanager-macos-candidate`）包含 `CampusNetManager-macOS-arm64-candidate.zip` 与 sidecar。SHA-256 `ede14350d9ef20998ed77963b589e8f5e32b15b93dee0958550191f23b4896a0`，ZIP CRC 检查通过；`ditto` 解包后发现 62 个符号链接，app 元数据为版本 `5.5.0`、bundle id `com.campusnettools.campusnetmanager`，Mach-O 为 arm64。`codesign --verify --deep --strict` 通过，但签名是 adhoc 且没有 Team ID；Actions 启动烟雾步骤通过。
- 这些是当前源码的 CI 候选产物，不是 GitHub Release。macOS Developer ID 签名、公证、Windows 正式签名、跨版本升级、真实 Windows/macOS 控件级功能验收及 Release 资产远端回读仍未完成。

## 外部发布门槛

- 商店隐私申报需以实际出站数据流为准。当前源码盘点见 [`PRIVACY_DATA_INVENTORY.md`](PRIVACY_DATA_INVENTORY.md)；它是未签核的审核底稿，不能直接当作面向用户的最终隐私政策或控制台声明。

- 截至 2026-10-16，Google Play 官方政策规定：从 2026-08-31 起，新应用和更新须 target Android 16/API 36 或更高；本项目 API 36 是必要条件，但构建通过不等于 Play 接收。[Target API level requirements](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en)
- 若 Play Console 个人开发者账号创建于 2023-11-13 之后，申请生产访问前需完成封闭测试，至少 12 名测试者连续 opt-in 满 14 天，并提交测试反馈及生产准备情况；组织账号不适用这项个人账号门槛。[App testing requirements](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en)
- 若 iOS 版本提供 VPN 服务，Apple App Review Guideline 5.4 要求使用 `NEVPNManager`，仅允许组织开发者账号提交，并在使用前清楚披露收集/使用的数据；还要求承诺不出售、使用或向第三方披露用户数据，并写入隐私政策。[App Review Guidelines 5.4](https://developer.apple.com/app-store/review/guidelines/uk/)
- 这些账号、组织主体、测试者、隐私声明和实际审核均依赖用户的开发者账号及申报信息；不把开发者密码、验证码、签名私钥或账号恢复码写入仓库/记忆。

## 验收记录模板

每个功能记录：源码位置、自动测试、打包结果、安装设备和 OS、操作步骤、可观察结果、失败/恢复证据、版本/构建号。未覆盖的步骤写明“未验证”，不以推测补齐。

## 最新 CI 候选与模拟器启动复核（2026-10-16）

- PR #1 当前文档 head `2f7052198ccca806114f6bf04153b6d823cd1ca5` 的 macOS/Windows 测试与版本检查、两平台候选包启动 smoke 均通过；PR 发布 job 按配置跳过。
- 从桌面候选 run `38894994317` 下载并检查当前 head artifacts。Windows artifact `12043856291` 含 PE32+ GUI x86-64 EXE，SHA-256 `6bd26d7bb6b85c519711ce0dde2bc44ff476a4557e99aa6959bc77bd081a6f07` 与 sidecar 一致。macOS artifact `12043636826` 的 ZIP SHA-256 `385902e6e302a2cad6795c81a02725f26cce36492d5fde6f3c62492a2f9e6dee` 与 sidecar 一致，CRC 检查通过，含 62 个符号链接；`ditto` 解包后 bundle `com.campusnettools.campusnetmanager` 版本 `5.5.0`、arm64，`codesign --verify --deep --strict` 通过。签名为 adhoc，无 Team ID；这仍是候选包，不是正式发布。
- 当前安装的 macOS app 主窗口截图显示 v5.5.0 界面正常渲染，状态栏显示守护运行中、VPN 与校园网在线及最近检测时间。截图查看后删除；没有操作界面按钮，所以功能逐项验收仍未完成。
- Android API36 run `38892862907`（head `ded3cfe`）成功构建 APK 并通过合并 Manifest gate，但 emulator step 失败，日志为 `Timeout waiting for emulator to boot.`。action 日志显示它因 KVM 不可用而以 `-accel off` 启动；现有 workflow 未设置 runner 的 `/dev/kvm` 权限。APK 上传因此跳过，运行证据上传步骤未找到文件。已在 `.github/workflows/mobile.yml` 增加 GitHub runner KVM udev 权限步骤并启用硬件加速；回归测试覆盖步骤顺序与配置。专项测试 `8 passed`，workflow YAML 解析和 `git diff --check` 通过。新配置仍待 Actions 构建与 API36 emulator 实跑验证。
- 上述模拟器 timeout 不代表 APK 运行失败：模拟器未完成启动，APK 安装/启动步骤没有执行。也不代表实体 Android 设备已验收。

## Android KVM 权限步骤复核（2026-10-16）

- run `38898518619`（head `18be81d3f88cb7fb592077f713cf26f9068c1119`）完成 API 36 APK 构建和合并 Manifest 校验；随后“启用 GitHub runner 的 KVM 权限”步骤失败，模拟器安装/启动与 APK 上传跳过，因此没有该 run 的 APK artifact。GitHub 页面显示整次 job 24m 1s。
- 目前可读的 Actions job 元数据只指出 KVM 步骤退出码 1；日志下载 API 返回 `Transport closed`，GitHub 页面要求登录查看日志，故无法确认步骤内具体哪条命令失败。不能把它归因为 `/dev/kvm` 缺失或权限错误中的任何一个。
- 工作流现在在 `codex/full-project-closure` 上相关 Android 源码/构建文件变更推送时自动运行，也保留手动入口。KVM shell 启用命令跟踪和严格模式，列出 `/dev/kvm` 状态、确认设备节点类型，并在 udev 规则后直接设置节点读写权限；回归测试锁定触发范围、诊断与权限操作。该修复提交后的 API 36 job 仍需重新构建、Manifest 校验和模拟器真实启动验证。

## Android 模拟器 APK 查找失败复核（2026-10-16）

- run `38901859963`（head `8f6b354d8b5bbbe8486ec17d9c47adab9321d745`）完成 APK 编译、合并 Manifest 检查和 KVM 权限步骤；API 36 x86_64 模拟器也成功启动。
- 安装步骤的实际日志显示 runner 将 `apk=$(find build_mobile/bin ...)` 与下一行 `test -n "$apk"` 分别交给独立的 `/usr/bin/sh -c` 执行，第二个 shell 中变量未设置，因而在 APK 安装前退出 1。旧 run 未上传 APK；always 上传步骤也没有找到日志/截图。
- 修复改为单独的 `scripts/android_emulator_smoke.sh`，由模拟器 action 用单条 `bash` 命令启动，使 APK 路径、PID 和循环变量在一个 shell 中有效；EXIT trap 尽力保存应用 logcat 与模拟器截图。新增回归测试锁定调用方式和证据收集。修复后的下一次 Actions run 尚待验证。

## Android 模拟器首次界面观察（2026-10-16）

- run `38915018182`（head `7e10c11a1738d981804d062d918a7922ee0905ca`）现已完成 API 36 debug APK 编译、Manifest gate、KVM 权限、模拟器启动、APK 安装、进程存活和无 `FATAL EXCEPTION` 检查，并上传 APK 与 emulator evidence artifact。
- 下载的屏幕截图显示 Kivy 中文文字为缺字方框；logcat 显示 Kivy 2.3.1 默认 Roboto 字体及 logo 复制的非致命权限错误。初次启动时档案文件不存在也被 `_load_profile()` 记成 `FileNotFoundError`；这是新安装路径而非档案损坏。模拟器未连接校园网，`http://192.168.16.3/` 的状态只能代表 runner 网络环境，不能代替校园网络测试。
- 已修复：把 SIL OFL 1.1 的 Noto Sans SC 字体及许可证随 Android 包分发并用于状态、表单、按钮和 Spinner 控件；首次启动缺少档案改为空档案，已有损坏档案仍报错。完整测试现为 `511 passed, 3 skipped`；专项测试、Ruff（测试文件）、Python 编译与 diff check 通过。修复后的 APK 字形、安装和界面需由后续 Actions run 复核。
- 更正故障归因：截图中的 `FileNotFoundError` 来自首次安装尚无 `profile.enc`，旧逻辑将其记为档案读取错误；不是认证服务器返回的异常。模拟器本身未接校园网，`http://192.168.16.3/` 的不可达状态是独立环境结果，不代表校园网真实登录测试。

## macOS 安装版主窗口复核（2026-10-16）

- 再次打开 `/Applications/校园网连接管家.app`；`CFBundleShortVersionString` 为 `5.5.0`，当前进程从安装目录的 `Contents/MacOS/校园网连接管家` 运行，`codesign --verify --deep --strict` 通过。
- 本机屏幕截图可见安装版主窗口已渲染，中文标题、表单和按钮文字可读；状态区显示“守护：运行中”和“网络：VPN 与校园网在线”。这是界面显示观察，不代表逐个操作按钮，也不独立证明公网/VPN/认证流量当前可用。
- Computer Use 插件仍报告运行时缺失；通过 CUA 窗口树只能读取窗口与菜单，改用本机截图完成只读观察。截图包含已保存档案字段，查看后删除，未写入仓库或记忆。
- 桌面逐功能操作、升级安装、Developer ID 签名、公证和正式 Release 回读仍未验收。

## 桌面候选包回读（2026-10-16）

- PR #1 head `9b3fae0c9de919bcaeb0de34ae2eed7875f8e2eb` 的 Desktop candidate run `38926389230` 中，Windows 与 macOS 构建、runner 启动 smoke、候选 artifact 上传均成功。Windows artifact `12056967604` 为 PE32+ GUI x86-64，sidecar SHA-256 校验通过，文件哈希 `4b965f7437bbb5244a44dcb3703bb7ac0be06753516e3fa9c43fbe2031e424fe`。它只在 Windows runner 完成启动 smoke，未在本机 Windows 安装验收。
- macOS artifact `12056373010` 的 ZIP CRC 和 sidecar SHA-256 校验通过，ZIP 哈希 `652499f8cb0f3260f8384d1bfda35d9445af9e1c14461ca1eceaf376d52bbd11`。`ditto` 解包后 `codesign --verify --deep --strict` 通过；bundle id `com.campusnettools.campusnetmanager`、版本 `5.5.0`，架构 arm64。签名为 adhoc、无 Team ID；候选包未做 Developer ID 公证、用户机器升级或正式 Release 回读。
- 本轮当前安装版仍从 `/Applications/校园网连接管家.app/Contents/MacOS/校园网连接管家` 运行，版本 `5.5.0`，签名严格校验通过。屏幕可见主界面和状态栏，但 Computer Use 插件仍报告运行时缺失；本轮 CUA 对“检查更新”“设备管理”“新手向导”的点击未观察到页面变化，不能据此判断功能失败，也没有形成控件操作验收证据。
- Android API 36 APK run `38923633508` 在早期复核时仍停在 APK 编译步骤，因此只轮询该 run、未重启；其后续终态和产物回读见下方最新核验。

## Android API 36 APK 与桌面候选最新回读（2026-10-16）

- Android run `38923633508`（head `ddfe838118edf4e6936e8d7c4d7c6ad3c726504e`）现已完成：API 36 debug APK 构建、前台服务 Manifest gate、runner KVM 权限、模拟器安装/启动、进程保持和运行证据上传步骤均 success。API36 x86_64 模拟器 smoke 脚本等待进程启动、运行 10 秒、再次确认进程仍在，并检查应用 logcat 无 `FATAL EXCEPTION`。
- APK artifact `12057956277` ZIP CRC 通过，SHA-256 `b6499fe8f8b48248ae422faf63de3d18364898687154bf1e6613c26db681633b`；内含 APK `campusnetmanager-1.0.0-arm64-v8a_armeabi-v7a_x86_64-debug.apk`，其 SHA-256 为 `c20c29e2aed14971e06a6b84ab291fc7c00c09590f6e6d494e7de79a84c622c4`，APK ZIP CRC 通过，包含 arm64-v8a、armeabi-v7a、x86_64。包内 `assets/private.tar` 的 `assets/NotoSansSC.ttf` 存在，SHA-256 与仓库预期 `a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da` 一致。
- emulator evidence artifact `12057194250` ZIP CRC 通过，SHA-256 `d012fe0a8da7ddb1cdd984fb2afaf9cde4436c4ba303dc2a713535317a2ad36e`。截图显示中文标题、字段和登录/保活按钮已渲染，不再停在 `Loading...`；状态仍为“正在检测网络环境…”，runner 未连接校园网，故不代表校园网认证或流量成功。logcat 中 `FATAL EXCEPTION`、ANR、进程退出计数均为 0；仍有 Kivy 默认图标复制的非致命权限告警。
- 对 PR #1 head `688a2fcf350b547083bf701c90132276f0ec40c0`，CI run `38927475080` 的 Windows/macOS 测试、静态检查和版本校验均 success，Release job 按 PR 规则 skipped；Desktop candidate run `38927475081` 两平台 build/launch smoke 与 artifact upload 均 success。Windows artifact `12056439965` PE32+ GUI x86-64，sidecar SHA-256 校验通过，文件 SHA-256 `cfda9408299e4acfa2118a70b6b5382942c005235cff9da735d1be5dfd53133c`。macOS artifact `12057247362` ZIP CRC/sidecar 校验通过，ZIP SHA-256 `b772c639a1f772476e207f2aea2c6da765c5ec555a1369457703ba41f39d8af6`；`ditto` 解包后 strict codesign 验证通过，bundle `com.campusnettools.campusnetmanager` v5.5.0 arm64，签名 adhoc、无 Team ID。两包均为候选包，不是安装验收或正式发行。
- Android 真机锁屏/切网/Keystore、signed Play 测试与发布，iOS 真机签名/IKEv2 流量/App Store，Windows 本机安装和桌面逐功能、macOS Developer ID/公证/升级/正式 Release 回读仍待验证。

## 最新 PR 与 macOS 安装界面复核（2026-10-17）

- 当前分支和 PR #1 head 为 `1207f253800b16db06b76ef09f50c520074d7271`，PR 仍为 OPEN draft，工作树干净。桌面候选 run `38928543184` 成功；PR CI run `38928542680` 对该 head 的 Windows job 全部 511 项测试通过，macOS job 在完整测试步骤失败，随后静态检查被跳过。
- macOS 失败栈落在 `tests/test_tunnel_default_no_key.py` 的两个 `WithKeyTests.setUp`：`SharedProxy.start()` 绑定监听端口时报 `OSError: [Errno 48] Address already in use`。该测试先用 `_free_port()` 绑定并关闭套接字，再让代理重新绑定，存在端口被其他进程抢占的竞争窗口；`SharedProxy.start()` 支持 `port=0` 并保存系统分配的端口。根因判断为测试端口分配竞态，仍需修复并在 macOS/Windows CI 验证。`gh-fix-ci` 工作流要求获得明确授权后再改动失败测试，目前修复未实施。
- 本机 CUA 重新读取 `/Applications/校园网连接管家.app`：可见版本提示“当前已是最新版本 v5.5.0”；关闭提示后，主窗口可见，标题为 `校园网连接管家 v5.5.0`。界面显示“守护：运行中”“网络：VPN 与校园网在线”，这些是应用界面状态，未独立证明当前认证流量、公网连通或设备端行为。
- 当前 CUA 可读取截图、关闭提示并通过 Tab 移动焦点；鼠标坐标输入返回窗口定位错误，因此没有完成主界面功能按钮的逐项操作验收。本次截图含已保存的档案信息，没有作为项目文件或记忆附件保存。

## b53f925 CI 与桌面候选包回读（2026-10-17）

- `b53f92575c51cfd2391552fdf31b1e57418173ab` 的 PR CI run `38929815980` 已完成 success：Windows 与 macOS 的 511 项测试和静态/版本/页面/敏感值检查均通过。前一个 head `1207f25` 的 macOS 端口冲突在此次未重现；这表明失败可能是间歇性的，但不证明竞争窗口已消除。
- Desktop candidate run `38929815974` 的 Windows 与 macOS 构建、runner 启动烟雾和 artifact 上传均 success。Windows artifact `12058620960` 外层 ZIP CRC 通过且 SHA-256 与 Actions artifact digest 一致（`f12745f45d0339dac9d56428916a9f505392239cfb72dd5a8ae793aa2b5491e7`）；内含 PE32+ GUI x86-64 EXE，SHA-256 `815af5c75352d7de5e452f037a3204af34edf860a505ecbfb89e86080ed4fc9a`，sidecar 校验通过。EXE 未签名，runner smoke 不等于用户 Windows 安装/升级验收。
- macOS artifact `12058277383` 外层 ZIP CRC 通过且 SHA-256 与 Actions artifact digest 一致（`45176a03cef82757a4af37719f8ed3d104575138aa68111a35ad720f17fcf9df`）；内含候选 ZIP，SHA-256 `7a527d8fa68daa1d5a6e59630a863698299493cbf29c7d3f389853178fe15127`，sidecar 值一致。`ditto` 解压后 `codesign --verify --deep --strict` 通过，app 为 arm64，bundle id `com.campusnettools.campusnetmanager`、版本 `5.5.0`，包含 62 个符号链接；签名为 adhoc，无 Team ID。该包仍是候选包，未公证或发布。

## 52462c8 双平台候选包下载回读（2026-10-17）

- PR CI run `38930343592` 和 Desktop candidate run `38930345160` 均针对 head `52462c80976b9357abe805ac01fafeff45972dad` 完成 success。此次使用 GitHub artifact 下载接口重新读取此前本机下载失败的候选 artifact。
- macOS artifact `12058786072` 外层 ZIP SHA-256 `20c5326c765aa96b605e7afb3e8bbcad325d985360766b5fafd202115f8cd3e4`，与 Actions artifact digest 一致；ZIP CRC 通过。内层候选 ZIP SHA-256 `995352b656d0ac192184352f0f51b21900badb94bfe6285802e9f65f8497aa1c`，与 sidecar 一致且 CRC 通过。`ditto` 解包后的 `CampusNetManager.app` 通过 `codesign --verify --deep --strict`，bundle id `com.campusnettools.campusnetmanager`，版本 `5.5.0`，含 62 个符号链接；签名为 adhoc，无 Team ID。
- Windows artifact `12059100129` 外层 ZIP SHA-256 `97872106757484d77a558cf0d9ce12645d7ef997bded9e688148b43f1253128b`，与 Actions artifact digest 一致；ZIP CRC 通过。内层 `CampusNetManager-windows.exe` SHA-256 `7e6ea599c57eedf18119c9e3b77b9c4ddaad16fe9a71a44d4a932343be9b94c5`，与 sidecar 一致；文件格式为 PE32+ GUI x86-64。Windows 包未签名。
- 两个平台均是 CI 构建并完成 runner 启动烟雾的候选包，不代表用户 Windows 设备安装验收、macOS Developer ID/公证、升级或正式 Release。macOS 安装版 CUA 可见“新手向导”按钮，但本轮键盘与点击交互未打开向导；Computer Use 专用运行时未启动，因此控件级功能仍未验收。

## f3fa7e0 双平台 CI 与候选包终态（2026-10-17）

- PR CI run `38931762696` 对 head `f3fa7e007fed239a02415246013d1011657568f4` 的 Windows/macOS 全套测试及静态、版本、页面和敏感值检查均 success；发布 job 按 PR 规则 skipped。
- Desktop candidate run `38931762695` 的 Windows/macOS 构建、runner 启动 smoke 与候选 artifact 上传均 success。Windows artifact `12059805531` 外层 ZIP SHA-256 `efd2bd9a6bd2a0e373823f92ea2ff9dff00f4d06ec7ab2e94fc0fc454b749738` 与 Actions digest 一致且 CRC 通过；内层 EXE SHA-256 `a12686688b7d43a031ac9f4ac6aec9b14f820ea59d657c565ead5f61b75f5de3` 与 sidecar 一致，PE32+ GUI x86-64，Authenticode security directory size 为 0（未签名）。
- macOS artifact `12059816085` 外层 ZIP SHA-256 `26509e239e3c9f4f612e607adbe14d21d3fc35e5ec0a171eb309317d64eb297f` 与 Actions digest 一致且 CRC 通过；内层 ZIP SHA-256 `f949e7ce3e7a6371b160213ba49dcaa8cc01be8767ca8574fdaee2a922036160` 与 sidecar 一致且 CRC 通过。`ditto` 解包后的 bundle `com.campusnettools.campusnetmanager` v5.5.0 通过 strict codesign，包含 62 个 symlink；签名为 adhoc、无 Team ID。
- 本次回读补齐 `f3fa7e0` 的候选包内容证据。候选与 CI runner smoke 仍不代表用户 Windows 安装、macOS Developer ID/公证、升级或正式 Release；Android/iOS 真机与商店验收也未完成。

## macOS 安装版新手向导只读验收（2026-10-17）

- 在本机安装的 v5.5.0 app 中打开“新手向导”，确认方式选择页展示直连、路由器中继和隧道三条路径；用键盘焦点与空格键进入路由器中继，并能切换至校园网上游检测。
- 执行该页的只读检测后，界面显示识别到上游无线网络、路由器品牌未知、提供管理地址及通用设置步骤。未打开管理页面、未修改路由器配置、未连接或启动隧道；日志不记录具体网络名称或地址。
- 此项证明安装版向导导航和一次本机只读检测可运行，不证明该路由器可配置成功、网络中继实际可用或认证流量双向通行。截图未保存；控件级完整功能、升级和正式分发验收仍待完成。

## 471155b 双平台 CI 与桌面候选包回读（2026-10-17）

- PR CI run `38933432185` 对 head `471155b1541b295f18022d0c9fdbd36dca3ff478` 的 Windows/macOS 测试、静态检查、版本、页面和敏感值检查均 success；release job 因 PR draft 规则 skipped。
- Desktop candidate run `38933432209` 两个平台的构建、runner 启动 smoke 和候选 artifact 上传均 success。macOS artifact `12060375383` 外层 ZIP SHA-256 `09b048b9497f2d3cf4564453624ba3637e32c82b9712be4ed664b1b8b2d3efb6` 与 GitHub digest 一致且 CRC 通过；内层 ZIP SHA-256 `8a81968aace3a0e3e634b70c18a2ff7c07c36e8abc8a40e36b3c8da13b886c3b` 与 sidecar 一致、CRC 通过，含 62 个 symlink。`ditto` 解包后的 app bundle `com.campusnettools.campusnetmanager` v5.5.0 通过 `codesign --verify --deep --strict`；签名 adhoc、无 Team ID。
- Windows artifact `12059088737` 外层 ZIP SHA-256 `b943f1f96c7b9ca9ab01e9234d8f7550acafb670ebf6c030e967aab79f57bb52` 与 GitHub digest 一致且 CRC 通过；内层 EXE SHA-256 `2ea390c5b388990f115d09d9323c99b41b353a1eceabc5ee51aad4b77236224d` 与 sidecar 一致，格式为 PE32+ GUI x86-64，Authenticode security directory size 为 0（未签名）。
- 两者仍是 PR 候选包和 Actions runner smoke，不是用户 Windows 安装验收、macOS Developer ID/公证或正式 Release；不代表升级与真机/商店验收。

## v5.6.0 桌面候选版本准备（2026-10-17）

- GitHub 当前最新正式 Release 经现场查询仍为 `v5.5.0`（2026-09-17）。本分支相对正式版包含 Android 前台服务/Keystore、iOS 系统 IKEv2 配套应用和 macOS 更新 ZIP 符号链接修复，因此按项目新增功能版本约定准备 `v5.6.0`。`APP_VERSION`、README 下载徽章和 CHANGELOG 已同步；`scripts/sync_version.py --check` 通过。
- 提交 `0e22be081d6ec20752b8a84f7014f27d470b238b` 的 PR CI run `38954069132` Windows/macOS 测试与静态、版本、页面、敏感值检查全部 success，发布 job 按 draft PR 规则 skipped。Desktop candidate run `38954069061` 两平台构建、10 秒 runner 启动 smoke 和 artifact 上传均 success。
- macOS artifact `12069981509` 外层 SHA-256 `dd64fcc65ca9d86f198f7ae94e913f94d527c568b3d4f84c63bec18e6cab844e` 与 GitHub digest 一致、CRC 通过；内层候选 ZIP SHA-256 `7f1edb33d7c5ee8b387369c9467bf3a8062ebb62c3f61ca1ba526db4d1c90807` 与 sidecar 一致、CRC 通过，含 62 个 symlink。解包 bundle `com.campusnettools.campusnetmanager` 版本 `5.6.0` 通过 strict codesign，签名 adhoc、无 Team ID。
- Windows artifact `12070110950` 外层 SHA-256 `2dee5556852d87548e2acedd1bdaf0b785721376b27a74fd204a3dc634ae128f` 与 GitHub digest 一致、CRC 通过；EXE SHA-256 `e873102ea916a635018c99ca78b8ce98e378b5823d4f6cb0c1289716c7754d62` 与 sidecar 一致，PE32+ GUI x86-64，Authenticode security directory size 为 0（未签名）。
- `v5.6.0` 目前只是候选版本准备和 runner 构建验证，不是正式 Release。仍需 Windows 用户设备安装、macOS Developer ID/公证/升级、Android/iOS 真机签名与测试及商店审核；当前没有任何商店提交或审核通过证据。

## Android 旧明文档案迁移恢复（2026-10-17）

- 代码复核发现 Android 档案迁移在“加密文件已落盘、删除旧 `profile.json` 前应用退出”后，不会再尝试删除遗留明文；旧明文档案会一直保留。
- `mobile/guard_service.py` 现在无论加密档案是否已存在，都会重试清理旧文件；清理暂时失败时仍返回可解密档案并提示用户，避免将有效档案当作空档案载入。首次迁移仍先原子写入加密文件，再清理明文。
- 新增回归检查覆盖首次迁移、加密文件已存在时重试清理，以及删除失败时档案仍可用。完整本机套件 `python3 -m unittest discover -s tests -v`：514 passed、3 skipped；相关文件 Ruff、Python 编译与 `git diff --check` 均通过。
- 此为源码、自动测试和静态检查证据；尚未在 Android 真机验证 Keystore 和文件系统行为，也不构成商店验收。

## 19cb82f 双平台桌面候选回读（2026-10-17）

- PR #1 head `19cb82f37f92e90719637922986e8c7553f65751` 的 CI run `38998935520` 中 Windows/macOS 测试、静态、版本、路由器页面和敏感值检查全部 success；发布 job 因 PR 仍为 draft 而 skipped。Desktop candidate run `38998935527` 的 Windows/macOS 构建、runner 启动 smoke 与 artifact 上传均 success。
- Windows artifact `12088595887` 的外层 SHA-256 `61a766cd2d185a32e3dd85d766c77c7dcafe9140d80ae2b7c8394a97e499292f` 与 Actions digest 一致且 ZIP CRC 通过。EXE SHA-256 `34d377f8e4fb2d37566ae642ce7e067a3f889e061bdbb4f4b41b77a9dd62346d` 与包内 sidecar 一致；文件为 PE32+ GUI x86-64，未在用户 Windows 设备安装验收。
- macOS artifact `12088406849` 的外层 SHA-256 `c270690302438e34540db868b4531727ea0ff4d5aa7b3efe62b0604db51c71b1` 与 Actions digest 一致且外层 CRC 通过。内层候选 ZIP SHA-256 `2ca6df45ac9069e55a100abe58108b9999cf561c840239e75561e9a887f49910` 与 sidecar 一致、CRC 通过；`ditto` 解包后 strict codesign 验证通过，bundle id `com.campusnettools.campusnetmanager`、版本 `5.6.0`、arm64、62 个符号链接。签名为 adhoc、无 Team ID。
- 当前 Mac 上运行的安装版窗口仍显示 v5.5.0；本轮未安装候选包。上述候选仅为 PR artifact 与 runner smoke，不代表用户安装/升级、Developer ID 公证或正式 Release。
- Android API 36 APK run `38998932605`（head `19cb82f`）已通过 APK 编译、前台服务 Manifest 校验和 KVM 权限步骤；当前正在 API 36 模拟器安装/启动，APK 与运行证据 artifact 尚未上传。该 run 仍在进行，后续只轮询此 run，不重启。

## 商店隐私数据流预审（2026-10-17）

- 新增 [`PRIVACY_DATA_INVENTORY.md`](PRIVACY_DATA_INVENTORY.md)，按桌面、Android 和 iOS 源码列出本地存储、登录凭据、联网探测、测速、更新、用户自选订阅/路由器/NAS 与 iOS IKEv2 网关的数据流，并标注商店申报前待确认事项。
- 本次源码检索未发现常见分析、广告或崩溃上报 SDK/接口；这不是对最终依赖、构建二进制或实际网络流量的完整证明。Dr.COM 登录源码将用户名和密码放入 HTTP URL 查询参数，是需要在上架前评估并向用户清楚披露的传输风险。
- PR #1 仍为 OPEN draft，head `dee232b4ddf813fb00f3376af25069f342c43676`；Android run `38998932605` 针对其前一源码 head `19cb82f`，APK 编译、Manifest 与 KVM 步骤通过，模拟器安装/启动仍在进行，artifact 尚未上传。本轮未重启该 run。

## Android 模拟器首屏黑屏修复候选（2026-10-17）

- 回读 run `38998932605` 的模拟器运行证据后发现：APK 安装、进程保持和无 `FATAL EXCEPTION` 均通过，但截图主体区域为黑屏。因此这次只能证明进程存活，不能证明主界面完成绘制；此前将该 run 记为模拟器启动成功的描述不应被解释为 UI 验收。
- 为降低首屏字体处理负担，`mobile/assets/NotoSansSC.ttf` 改为 Noto Sans SC Regular 静态字体子集，保留 SIL OFL 1.1 许可证。新字体 SHA-256 为 `36af0f6b574d759242c117bb88bf673c0e5b5c74932877d2a2031240e383dd4d`，包含 28,193 个映射字形且不含可变字体 `fvar`/`gvar` 表。此改动是待模拟器验证的修复候选，尚未证明它是黑屏根因或已解决问题。
- 新增标准库 PNG 检查器，在启动后最多重取 10 次截图；若屏幕主体采样像素仍无可见内容，模拟器 smoke 失败。新增黑屏/有色画面单测，并把模拟器截图证据保留为 artifact，失败时也会上传。
- 当前本地专项测试 12 项通过，`bash -n`、workflow YAML 解析、字体 SHA/表结构检查和 `git diff --check` 均通过。新的 Actions APK 构建、安装、首屏截图门禁及 artifact 回读仍待执行；即使通过，也只证明 API 36 模拟器显示，不代表实体手机、校园网认证流量或商店验收。

## c56b2c1 桌面 CI 与候选包回读（2026-10-17）

- PR CI run `39001312912` 对 head `c56b2c1bf77738c28e3e7521217ac17b41f106e2` 的 Windows/macOS 测试、静态、版本、路由器页面和敏感值检查全部 success；发布 job 按 draft PR 规则 skipped。Desktop candidate run `39001312928` 两平台构建、runner 启动 smoke 与 artifact 上传均 success。
- Windows artifact `12089227597` 外层 SHA-256 `b63c9e15dcff83c56e51b2f94b85145669740b24c15a3e902a1a743051769b10` 与 Actions digest 一致，ZIP CRC 通过。EXE SHA-256 `084cc8c6eefaf2e0bb1a879655ae4c559d1298de9f8888e4ad3c8f947c200cbe` 与 sidecar 一致；文件为 PE32+ GUI x86-64，Authenticode security directory size 为 0（未签名）。
- macOS artifact `12089136867` 外层 SHA-256 `b687f6363036f0cd789d322eafe765a0b2b70919ddbae3d4fc1dcb961e6b5ac0` 与 Actions digest 一致，ZIP CRC 通过。内层候选 ZIP SHA-256 `1d654ec8df61f417e2d4c2115b07be487b4cd031d4285d1ef79e8cef33debab8` 与 sidecar 一致且 CRC 通过；ditto 解包后的 bundle `com.campusnettools.campusnetmanager` v5.6.0 通过 strict codesign，arm64、62 个 symlink、adhoc 签名、无 Team ID。
- 以上仍是 draft PR 候选与 GitHub runner smoke，不代表 Windows 用户设备安装、macOS Developer ID/公证/升级或正式 Release。

## macOS 本机安装 v5.6.0 候选（2026-10-17）

- 使用项目 `.venv` 的 Python 3.13.12 / PyInstaller 6.22.2 执行 `PYTHON_BIN=.venv/bin/python ./scripts/build_macos.sh`，本机 arm64 `.app` 构建成功。
- 替换前用 `ditto` 备份 `/Applications/校园网连接管家.app` 与 `dist/macos/校园网连接管家.app` 至 `archives/installed-macos-5.5.0-before-v5.6.0-2026-10-17/` 和 `archives/dist-macos-5.5.0-before-v5.6.0-2026-10-17/`，并保存恢复说明。安装前后 `.app` 均通过 `codesign --verify --deep --strict`。
- 安装 bundle id `com.campusnettools.campusnetmanager`，版本 `5.6.0`，Mach-O arm64，包含 55 个符号链接；签名 adhoc、无 Team ID。进程从 `/Applications/校园网连接管家.app/Contents/MacOS/校园网连接管家` 启动，CUA 截图可见 v5.6.0 主界面。
- 本机完成候选构建、归档、替换、启动与可视界面检查；未完成控件逐项操作、自动升级、Developer ID 签名/公证或正式 Release。截图含本机已保存档案字段，未保存、提交或转录；界面显示的“守护/网络”文案不作为网络流量验收。
- Google Play Data safety 申报需覆盖应用及 SDK 离开设备的数据；iOS VPN App 的组织账号资格、使用前披露和隐私承诺仍待发布主体核实。数据流底稿不是最终隐私政策、Data safety 表单、Privacy Labels 或商店审核证据。

## f38d885 双平台候选与 Android 首屏门禁轮询（2026-10-17）

- PR CI run `39001968182` 对 head `f38d885936e957daf617d76e38ddde3f6650549c` 的 Windows/macOS 测试与检查均 success；发布 job 因 PR 仍为 draft 而 skipped。Desktop candidate run `39001968201` 的 Windows/macOS 构建、runner launch smoke 和 artifact 上传均 success。
- Windows artifact `12089476217` 的 Actions 外层 digest 为 `a2ff90ac4b1e8dadbee59ae491bb5f2176e87be1fa711cacc11354b39a9e2e66`，直接下载 artifact ZIP 后 SHA-256 相同且 CRC 通过。内层 EXE SHA-256 `85383eaac8ccfa21df5f01d8c4c669e8fef13eb8dc532c8c2215cdbb9f51ab97` 与 sidecar 一致，格式为 PE32+ GUI x86-64，Authenticode security directory size 为 0（未签名）。
- macOS artifact `12089397403` 的 Actions 外层 digest 为 `70711406547d7f5105de8f99550cfd35f24568b5f5be8c0290c3feda99444161`，直接下载 artifact ZIP 后 SHA-256 相同且 CRC 通过。内层候选 ZIP SHA-256 `afbede45481142ac5b8df71d6dbce1a571ed5bd1f305f1307477bba61b3b9c81` 与 sidecar 一致且 CRC 通过；`ditto` 解包后 strict codesign 验证通过，bundle id `com.campusnettools.campusnetmanager`、版本 `5.6.0`、arm64、62 个符号链接，签名 adhoc、无 Team ID。
- Android API 36 debug APK run `39001309887`（head `c56b2c1bf77738c28e3e7521217ac17b41f106e2`）的环境准备步骤均 success，但截至本次检查仍在 APK 编译步骤；Manifest、KVM、模拟器截图门禁与 artifacts 尚未运行。该 run 持续轮询，不重启。先前 `38998932605` 的模拟器截图主体黑屏，因此静态字体和非黑屏截图门禁仍是待验证修复候选。
- 以上桌面包仍为 OPEN draft PR 的候选，不代表正式 Release、Windows 用户设备安装、macOS Developer ID/公证或升级验收。Android API 36 模拟器也不代表实体手机、校园网流量或商店验收。

## 6ecbede 用户手册与双平台候选回读（2026-10-17）

- 用户手册已从“iOS 暂不支持”更新为准确描述现有系统 IKEv2 配套 App 的 CA 与 enrollment 导入步骤，并注明目前只有 Simulator 构建/安装/启动证据；真机签名、证书信任、IKEv2 双向流量、升级和 App Store 均未验收。该更改位于 `docs/用户使用手册.md`，不是 iOS 功能代码变更。
- 提交 `6ecbede6b028ac19148bf9091409355fbc8871eb` 的 PR CI run `39002308814` 中 Windows/macOS 检查均 success，发布 job 因 PR draft skipped；Desktop candidate run `39002308820` 两平台构建、runner launch smoke 和 artifact 上传均 success。
- Windows artifact `12089961124` 的 Actions 外层 digest、直接下载 ZIP SHA-256 均为 `06cab1f8e911166092dac79256f3ee5cf659c19691e7398e05030513e3cf9c5e`，CRC 通过；EXE SHA-256 `45d46f23255fd75b4f32df5d3c83c9a610527817c74297d8f6998832bcc95ce9` 与 sidecar 一致，PE32+ GUI x86-64，Authenticode security directory size 为 0（未签名）。
- macOS artifact `12089786893` 的 Actions 外层 digest、直接下载 ZIP SHA-256 均为 `101d074c72b6723e96dbb4d504b541df98dbd7d0a46eb678f80b0f7bd19fa694`，CRC 通过；内层候选 ZIP SHA-256 `b958a59e102feef5908642718533c716c4df21509230fc3a924b545ef73f2569` 与 sidecar 一致且 CRC 通过。`ditto` 解包后 strict codesign 通过，bundle id `com.campusnettools.campusnetmanager`，版本 `5.6.0`，arm64、62 个符号链接，签名 adhoc、无 Team ID。
- Android API 36 APK run `39001309887`（head `c56b2c1bf77738c28e3e7521217ac17b41f106e2`）仍在 APK 编译步骤。实时 Actions job log 在 `04:24:04Z` 显示正在将 Kivy Python 模块复制到 wheel；随后 `04:25Z` 的 job 查询仍显示编译中。Manifest、KVM、模拟器截图门禁与 artifact 步骤尚未执行；不要重启该 run，也不能据此声称黑屏修复通过。
- Windows/macOS 包为 draft PR 候选和 runner smoke，不代表用户设备安装或正式发布；本节不新增真实手机、签名商店、升级或校园网流量证据。

## 更新检查结果区分修复（2026-10-17）

- 代码审查发现更新器把网络请求异常和“当前没有更高版本”都返回为 `None`，主界面与偏好页会将检查失败误报为“已是最新”。对 v5.6.0 本机候选而言，公开 Release 版本较低时也会被错误当作与最新版本相同。
- `updater.check_for_update` 现在返回 `available`、`current` 或 `ahead` 状态；网络/响应/版本无效抛出 `UpdateCheckError`。主界面和偏好页分别呈现失败、相同版本及本机候选高于公开 Release，并在非更新结果后恢复“立即检查”按钮。
- 以当前仓库源码实时查询 GitHub 最新 Release，应用版本 `5.6.0` 得到 `ahead`，公开版本 `v5.5.0`；这仅是本轮源码功能调用的联网证据，不代表已安装应用包含该修复或已发布新版本。
- `tests.test_updater` 30 项通过（1 项 Windows-only 跳过）；完整 unittest 519 项通过、3 项跳过。CI 同款 Ruff F/E9 规则、Python 编译和 `git diff --check` 通过。测试输出另有既存 ResourceWarning，未据此推断本次代码失败。
- 更新检查 UI 的可视点击验收尚未形成证据；本机安装包需在后续构建后复核。功能修复仍需最新 PR CI 与桌面候选构建验证。

## 15ca386 更新器回归与 macOS 安装包复核（2026-10-17）

- 新增 `tests/test_update_ui_states.py`，覆盖更新检查失败、当前候选高于公开版、版本与公开版相同三种结果在主界面和偏好页的提示及按钮状态；3 项专项测试通过。初始测试夹具误读了已销毁后置空的按钮成员，修正为保留原按钮引用后检查销毁状态。
- PR CI run `39002957568` 对 head `15ca386f2b7b412a0772258737c5435a5b90ed7b` 的 Windows/macOS 全套测试、静态、版本、页面和敏感值检查均 success；发布 job 因 PR 仍为 draft 而 skipped。Desktop candidate run `39002957566` 两平台构建、runner 启动 smoke 和 artifact 上传均 success。
- macOS artifact `12090012105` 的 Actions digest 为 `9039c4f338bd17a54e5098751cb657d58e60aade728e81f42a827f57a0f3fafc`；候选包 `CampusNetManager-macOS-arm64-candidate.zip` SHA-256 `87db7bda4afbcca35015cce5690b01a8755f72697c7def91494d8f1bf78f6c9a`，sidecar 与 ZIP CRC 校验通过。`ditto` 解包后的 app 通过 strict codesign，bundle id `com.campusnettools.campusnetmanager`，版本 `5.6.0`，arm64，含 62 个符号链接，adhoc 签名且无 Team ID。
- Windows artifact `12088979506` 中 EXE sidecar 校验通过，格式为 PE32+ GUI x86-64；PE security directory size 为 0（未签名）。该包为 PR 候选和 runner smoke，不代表 Windows 用户设备安装验收。
- 使用 `.venv` / PyInstaller 6.22.2 从当前源码构建 macOS arm64 app；替换前将 `/Applications` 原安装版与 `dist/macos` 原构建各自备份到 `archives/installed-macos-v5.6.0-before-updater-ui-2026-10-17/` 与 `archives/dist-macos-v5.6.0-before-updater-ui-2026-10-17/`。新包安装到 `/Applications/校园网连接管家.app` 后 bundle id、版本与签名验证通过，安装版与 dist 主可执行文件 SHA-256 均为 `57746e0d4e8bb0d6f0668cf079f722de767a3a101abebbec8755bc5db7854b2b`；进程从安装路径运行，CUA 窗口标题显示 v5.6.0。
- 安装包构建、替换、启动已核实；更新检查控件的运行时点击及错误状态的可视呈现仍未验收。当前签名为 adhoc、无 Team ID；Developer ID、公证、用户升级和正式 Release 尚未完成。

## Android API 36 启动截图发现首屏仍停留加载态（2026-10-17）

- run `39001309887`（head `c56b2c1bf77738c28e3e7521217ac17b41f106e2`）APK 编译、前台服务 Manifest 校验、KVM、模拟器安装/启动、进程存活与截图上传步骤都显示 success。APK artifact `12089404363` 的 Actions digest 为 `0dc84e172e9dc4e342becf0f033c99fe4543fd9ee79bafe9c9b40be81bb42a9f6`；下载 APK SHA-256 为 `50cad4ac3f5bb21406bfaa7e5157e2cac45df38d3e722cc7ee46814016e29438`，ZIP 完整性通过。模拟器证据 artifact `12089693635` 的 digest 为 `66dfcf16c4e7764d12c886915678bcac01be0a0b85b2045a5dcea46a29b0c24e`；截图 SHA-256 `92db0db6f22782637d8a566ed8c2746f2f84503d008bb3f75a5f7ecf2c0943e7`，logcat SHA-256 `b0fbebbfea3ba74382763f2c5c35d24e4ce94b74482513e72d1f18649eacb25c`。
- 截图显示 UI 仍为“正在检测网络环境…”且其余大部分内容为空；旧图片门禁只要求 0.1% 采样像素非黑，报告实际 2.524% 后即通过，因此旧 run 的 launch smoke 是误绿，不能作为首屏就绪证据。logcat 有 SDL2/OpenGL 初始化和 `Start application main loop`，未见 `FATAL EXCEPTION`；另有 Kivy 图标目录复制 Permission denied 与 HIDAPI receiver 异常，尚无证据把它们认定为首屏停滞根因。
- 修复候选把纯网络状态决策提取至 `mobile/startup_status.py`，网络探测异常会产生可见失败状态；网络状态更新后发出不含凭据的 `CNM_NETWORK_STATUS_READY` 信号。模拟器脚本新增最多 30 秒的该信号门禁，必须先观察到网络检查终态，再执行截图像素门禁；APK 与 AAB 组装步骤同步复制该模块。16 项相关单测通过，全套 unittest `527 passed, 3 skipped`，CI 同款 Ruff F/E9、`py_compile`、bash 语法、工作流 YAML 解析和 `git diff --check` 通过。
- 该修复尚未由新 Actions API 36 run 验证；需确认新截图已离开加载态且状态标记出现。模拟器证据不等于实体设备、真实校园网、锁屏/切网、Keystore 或 Play 上架验收。

## macOS v5.6.0 新手向导只读复核（2026-10-17）

- 当前安装版窗口标题显示 v5.6.0。使用键盘焦点导航进入“方式 B：路由器中继”，再选择“校园网”上游；向导画面显示已检测到副路由器，但品牌未知，并呈现通用中继步骤。
- 该流程只执行应用内的路由器发现并显示说明；没有打开路由器管理页面、修改设置、保存档案或启动隧道。随后关闭向导并回到主窗口。
- 这是本机当前安装版的控件级只读界面证据，不证明 BE6500 Pro 型号识别、路由器中继配置成功、手机/电脑流量经过中继，或真实校园网双向连通。Windows 用户设备验收、macOS Developer ID/公证、升级和正式 Release 仍未完成。

## 6ae16cd 桌面候选回读与 Android 首屏修复轮询（2026-10-17）

- PR CI run `39004505005` 对 head `6ae16cd447791fe8cfe81d8213af4ebd09cd23fb` 的 Windows/macOS 全套测试、静态、版本、页面与敏感值检查均 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39004505002` 两平台构建、runner 启动 smoke 与 artifact 上传均 success。
- macOS artifact `12090850387` 外层 SHA-256 与 Actions digest 一致，为 `d30a42976a420d67dfd96eadbcdcb3419ae1552234848ee53af03ef91b4d28ac`，ZIP CRC 通过。内层候选 ZIP SHA-256 `ff6623b7bba86fdfc19e53cd2c103d41bd535362065be110bd780a34c5504f99` 与 sidecar 一致，CRC 通过；含 62 个符号链接，`ditto` 解包后 strict codesign 通过。bundle `com.campusnettools.campusnetmanager`、v5.6.0、arm64；adhoc 签名、无 Team ID。
- Windows artifact `12090346511` 外层 SHA-256 与 Actions digest 一致，为 `e11e4e692b37b70de87e25795fee74b09bae73b3e72d0805c5bc9f6f5ed9c0cc`，ZIP CRC 通过。EXE SHA-256 `626d1f5a74739adf6ed63b1295fbfb876af8794a166636f960683b105765cfe8` 与 sidecar 一致，PE32+ x86-64；Authenticode security directory size 为 0，未签名。
- Android API 36 APK run `39003633514`（head `794d69ddb936277561d6debc71c57fd22d6a28e6`）截至记录仍在 APK 编译步骤 11；Manifest、KVM、模拟器首屏状态门禁与 artifact 步骤均未开始，无 artifact。日志读取接口曾返回 Transport closed；不推断其根因，继续只轮询原 run。
- 桌面包仍是 draft PR 候选和 Actions runner smoke，不代表正式 Release 或用户 Windows/macOS 安装验收。Android 模拟器运行也不代表实体手机、真实校园网、锁屏/切网、Keystore 或 Play 验收。

## Android run 39003633514 编译日志活跃度复核（2026-10-17）

- Actions run 与 job 元数据在 `05:07Z` 仍显示 `in_progress`，当前步骤为“构建 Android API 36 debug APK”；前序环境准备全部成功，Manifest、KVM、emulator 与 artifact 步骤仍 pending。
- 通过 GitHub job-log endpoint 下载到约 31.5 MB UTF-8 文本日志，尾部时间戳到 `05:06:13Z`，内容仍在执行 Android NDK clang 编译 SDL2 组件（armeabi-v7a）。因此该编译步骤仍有日志活动；run 的 `updated_at` 未变化不等于进程停止。
- 这只是源码候选的持续编译证据；尚未通过 APK Manifest gate，也没有模拟器首屏 readiness marker、截图、APK artifact 或实体手机验收。继续轮询原 run `39003633514`，不重启。

## cdda9a0 CI 与桌面候选包回读（2026-10-17）

- PR CI run `39005194623` 对 head `cdda9a081726ae1feabfff9d1df59c7b96088c28` 的 Windows/macOS 全套测试、静态检查、版本、页面和敏感值检查均 success；发布 job 因 PR 仍为 draft 而 skipped。
- Desktop candidate run `39005194650` 的 Windows 与 macOS 构建、runner 启动 smoke 和 artifact 上传均 success。Windows artifact `12090642606` 的外层 SHA-256 为 `17eb5ffcba47846eaa6dbe340521ca442a2d57788d0ec004576cec69c2b926e9`，与 Actions digest 相同且 ZIP CRC 通过；EXE SHA-256 `2ad6b9a8573689a5043aa09dea3d1b95fdf8441df3e56d7d0a8b42328cfd2700` 与 sidecar 一致，文件为 PE32+ GUI x86-64，PE 证书表大小为 0（未签名）。此证据不含用户 Windows 设备安装。
- macOS artifact `12090717136` 外层 SHA-256 为 `3cf1a3a4e84360e409db04eadad6bd95a96394c7a5512a277d6ae912b47a3d70`，与 Actions digest 相同且 ZIP CRC 通过；内层候选 ZIP SHA-256 `e85e9b9c641c01fdc8829c73ed10cd96d4bed01266bd5d91d3d8705315f6d461` 与 sidecar 一致、CRC 通过。`ditto` 解包后 strict codesign 验证通过，bundle id `com.campusnettools.campusnetmanager`、版本 `5.6.0`，62 个符号链接；签名 adhoc、无 Team ID。
- Android run `39003633514`（head `794d69ddb936277561d6debc71c57fd22d6a28e6`）仍在 APK 编译步骤 11；其 Manifest、KVM、模拟器首屏 readiness、安装/启动及 artifact 步骤均未开始。job-log connector 此次仍返回 `Transport closed`，没有新的编译尾日志证据；不将其解释为 run 已停止，继续只轮询原 run。
- 桌面候选包和 Actions runner smoke 不是正式 Release 或用户设备安装/升级验收；macOS adhoc 包也不是公证发行包。Android run 尚无新设备或包验收结论。

## e686eb5 CI 与桌面候选回读、Android 模拟器门禁推进（2026-10-17）

- PR CI run `39005384714` 对 head `e686eb51776b6569e1e132e321f3e13168344384` 的 Windows/macOS 测试与静态、版本、页面、敏感值检查均 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39005384708` 的 Windows/macOS 构建、runner launch smoke 和 artifact 上传均 success。
- macOS artifact `12090712491` 外层 SHA-256 与 Actions digest 一致：`4cfbce577e12e0967217de58a247df590fdbb5235874979c052c3f611ec814fd`，外层 ZIP CRC 通过；内层候选 ZIP SHA-256 `a294c608253482d0c49f662bc75c9b8cbe7d0abb983199dc11a8113e8853d0aa` 与 sidecar 一致、CRC 通过。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager`、v5.6.0、arm64、62 个符号链接、adhoc 签名且无 Team ID。
- Windows artifact `12091000717` 外层 SHA-256 与 Actions digest 一致：`d53aad1fca28a75f4c9a18a8325e6e0e8a7da7a532d217913e95ab89af8fe8fe`，外层 ZIP CRC 通过；EXE SHA-256 `d991f11c35edf8094397bfd64aace31883f6096ee21ce2cae49fe222eaade802` 与 sidecar 一致，文件为 PE32+ GUI x86-64，PE 证书表大小为 0（未签名）。两项 artifact 均是 PR 候选。
- Android API 36 APK run `39003633514`（源码 head `794d69d`）已完成 APK 编译、前台服务 Manifest gate 和 KVM 权限步骤；截至本次轮询，模拟器安装并启动步骤 14 正在运行，APK 与 emulator evidence 上传仍 pending。尚无新的 readiness marker、截图、运行证据或 APK artifact 结论；继续只轮询此原 run。
- 本次只核实 Actions runner 与候选包；不能据此声称用户 Windows/macOS 安装、正式 Release、公证、Android 真机、真实校园网或商店验收完成。

## Android API 36 模拟器启动与候选 APK 回读（run 39003633514，2026-10-17）

- run `39003633514`（源码 head `794d69d`）最终 success：APK 编译、前台服务 Manifest gate、KVM 权限、API 36 模拟器安装/启动、APK artifact 上传及 emulator evidence 上传均成功。
- APK artifact `12091360109` 外层 SHA-256 与 Actions digest 一致，为 `a4a5d369e858c30a57af37092a081e84a2bf33d041a58ceb0cb870bc04b00183`，外层 ZIP CRC 通过。内含 `campusnetmanager-1.0.0-arm64-v8a_armeabi-v7a_x86_64-debug.apk`，APK SHA-256 `dfedbbcbc19584a4367f83f6a8fbbf4f0266c9147a0b4958bd5792e206fd8210`；APK ZIP CRC 通过、含 `AndroidManifest.xml` 与 arm64-v8a/armeabi-v7a/x86_64 三个 ABI。
- 模拟器证据 artifact `12091380038` 外层 SHA-256 与 Actions digest 一致，为 `17b0417c1472bf27e419b35b966de51f0c4ca1f5d832519792dc59c4722a1dd0`，ZIP CRC 通过，含截图和 logcat。logcat 有 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，未见 `FATAL EXCEPTION`、`ANR in` 或进程死亡记录。截图显示登录表单已渲染并呈现上述非校园网状态；账号/密码为空，说明页未停留在“正在检测网络环境”。
- 这是 Android API 36 x86_64 模拟器的启动/首屏状态证据；状态为模拟环境下认证服务器不可达。它不验证真实校园网络、真实手机、锁屏/切网、Keystore、VPN 双向流量、Play 签名或商店接收。

## 5db73fd 双平台 CI 与桌面候选回读（2026-10-17）

- PR CI run `39005626159` 对 head `5db73fd310dbf7b5783e589657cdb03affa262b9` 的 Windows/macOS 测试、静态、版本、页面与敏感值检查均 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39005626160` 两平台构建、runner launch smoke 和 artifact 上传成功。
- macOS artifact `12090294691` 外层 SHA-256 与 Actions digest 一致：`7d891b3c321c28277bdd3ef811641a9922c581ae847d01db48446cc00751130b`，ZIP CRC 通过；内层候选 ZIP SHA-256 `aed15794413d29f483188e6ea27860846334924a2051347749307b4143149385` 与 sidecar 一致且 CRC 通过。`ditto` 解包后 strict codesign 通过，bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64、62 个符号链接；签名 adhoc、无 Team ID。
- Windows artifact `12091196471` 外层 SHA-256 与 Actions digest 一致：`2a6af8f56ed5a35982693de8a9dd8406af4fc1181cc06a8fcc1f17bc470eb044`，ZIP CRC 通过；EXE SHA-256 `e016c33913a2441bbf2a8fa51795c377a27fa6afc394ffe1844ef14880c845a1` 与 sidecar 一致，PE32+ GUI x86-64，证书表大小为 0（未签名）。
- 这些包仍是 PR 候选；runner smoke 不证明用户设备安装/逐功能验收，macOS adhoc 签名也不是 Developer ID/公证。Android API36 模拟器 run `39003633514` 的首屏门禁已通过，但不代替实体设备与商店验收。

## 2da2013 双平台 CI 与桌面候选回读（2026-10-17）

- PR CI run `39005761943` 对 head `2da2013989f0e913959a1f34db2bb0166475f4e4` 的 Windows/macOS 测试、静态、版本、页面与敏感值检查均 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39005761862` 两平台构建、runner launch smoke 和 artifact 上传均 success。
- macOS artifact `12090623652` 外层 SHA-256 与 Actions digest 一致：`8c9017d6ab4174b5796e0f83d4fb29beebfc26fbbc1909370a444514753e1ba0`，ZIP CRC 通过；内层候选 ZIP SHA-256 `af33ac07d6cb318dca4de12224228846fb2e844653d0c0caf4384d6421587be8` 与 sidecar 一致、CRC 通过。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64、62 个符号链接，签名 adhoc、无 Team ID。
- Windows artifact `12091176787` 外层 SHA-256 与 Actions digest 一致：`53b6e64967f9239718ea70b912b632631481674452712039b90bad0aeda4f5b7`，ZIP CRC 通过；EXE SHA-256 `aee02a230b90863b449f74f97dc06585035083d4fd52bd66e63b4667edb3d534` 与 sidecar 一致，PE32+ GUI x86-64，证书表大小为 0（未签名）。
- 验证限于 PR 候选 artifact 与 Actions runner smoke；未证明用户设备安装、签名发行、公证、升级或商店发布。

## 0e8b647 双平台 CI 与桌面候选回读（2026-10-17）

- PR CI run `39005919054` 对 head `0e8b647a3bbb8a34a686ee48085a26c6585f2b78` 的 Windows/macOS 测试、静态、版本、页面与敏感值检查均 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39005919040` 两平台构建、runner launch smoke 和 artifact 上传均 success。
- macOS artifact `12090813002` 外层 SHA-256 与 Actions digest 一致：`3ef2d8b2176bedff3842517dd5a81c3ad57bfead2efa48424463014e3f8410b2`，ZIP CRC 通过；内层候选 ZIP SHA-256 `98f144fce1fff259eda1f5a081220604d9d85b3d6f6948c7a11140fd5cc75d38` 与 sidecar 一致、CRC 通过。`ditto` 解包后 strict codesign 通过，bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64、62 个符号链接，签名 adhoc、无 Team ID。
- Windows artifact `12091047374` 外层 SHA-256 与 Actions digest 一致：`54c7130e833f6b899a803043a2b9428b0a4e0085516cabcf2882a22c90ef392e`，ZIP CRC 通过；EXE SHA-256 `9b055c0f4550b43f0c3998cd63af84d010ba97471c5fa8280926cc421ad90c5b` 与 sidecar 一致，PE32+ GUI x86-64，证书表大小为 0（未签名）。首次下载出现 TLS `SSL_ERROR_SYSCALL`，重新获取下载链接后成功回读并完成校验。
- 这些是 PR 候选包与 Actions runner smoke 证据；没有用户设备安装、正式签名发行、公证、升级或商店发布证明。

## 8c16800 双平台 CI 与桌面候选回读（2026-10-17）

- PR CI run `39006051646` 对 head `8c16800cc2cd6949e64780dc5cae1752558d10a4` 的 Windows/macOS 测试、静态、版本、页面与敏感值检查均 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39006051643` 两平台构建、runner launch smoke 和 artifact 上传均 success。
- macOS artifact `12091107449` 外层 SHA-256 与 Actions digest 一致：`298a86e00cce68cd2c33cf2bbf0269633c25c072c7b8b5fd2d372b366283750e`，ZIP CRC 通过；内层候选 ZIP SHA-256 `3ea7c156e9455fc357a69904d860587a569835f12a39c935569ab8a5a88b25ed` 与 sidecar 一致、CRC 通过。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64、62 个符号链接，签名 adhoc、无 Team ID。
- Windows artifact `12091041463` 外层 SHA-256 与 Actions digest 一致：`51e242fecf1540e2689a7039037a7df704caf7a7a4cf13f6f8da231e3409304c`，ZIP CRC 通过；EXE SHA-256 `ee2b18e829eece931170f9773f73d4f379be1aeb9fac11f509e4352e4438801c` 与 sidecar 一致，PE32+ GUI x86-64，证书表大小为 0（未签名）。
- 以上仍是 PR 候选与 runner smoke；没有用户设备安装/升级、正式签名、公证、Release 或商店验收证据。

## 24ec8a1 双平台 CI 与桌面候选回读（2026-10-17）

- PR CI run `39006198867` 对 head `24ec8a1bbe9700eeda975643d8f16eb58f9879b1` 的 Windows/macOS 测试、静态、版本、页面与敏感值检查均 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39006198880` 两平台构建、runner launch smoke 和 artifact 上传均 success。
- macOS artifact `12090853397` 外层 SHA-256 与 Actions digest 一致：`973dde9d4d1a5e97c2a31bd35986b552494f1adfe1ecace0c6213c112a55a9d0`，ZIP CRC 通过；内层候选 ZIP SHA-256 `988573749696932e9b692d6f552fc11a48943cf4c9300328884b1f3c9fcc966d` 与 sidecar 一致、CRC 通过。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64、62 个符号链接，签名 adhoc、无 Team ID。
- Windows artifact `12090313725` 外层 SHA-256 与 Actions digest 一致：`6b0e7d89eee1d2d924b354800f06ecd5e1c14cf9976d5c57909e6e31607aea8a`，ZIP CRC 通过；EXE SHA-256 `803a7acddd46f4aec8dbebb6d63f5314f08228e2cb96358a6628aeac0e7f762d` 与 sidecar 一致，PE32+ GUI x86-64，证书表大小为 0（未签名）。下载初次遇到 TLS `SSL_ERROR_SYSCALL`，重新取下载地址后成功完成外层与内层检查。
- 这些仍是 PR 候选包和 runner smoke 证据；不能证明用户设备安装/升级、正式签名、公证、Release 或商店接收。

## 85f8e92 双平台 CI 与桌面候选回读（2026-10-17）

- PR CI run `39006323779` 对 head `85f8e92141e4f36bf49306597caeb818d9a6c4de` 的 Windows/macOS 测试、静态、版本、页面与敏感值检查均 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39006323774` 两平台构建、runner launch smoke 和 artifact 上传均 success。
- macOS artifact `12090798694` 外层 SHA-256 与 Actions digest 一致：`b8acf442e32d77d5b06c5b5a68fbe0e439c033237884a5d7f75f8e76db701031`，ZIP CRC 通过；内层候选 ZIP SHA-256 `abf955568cb635ad3ad1f19d4fc25c00b85c52cc1fcbea22ecfdb9cdf6d9bbe8` 与 sidecar 一致、CRC 通过。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64、62 个符号链接，签名 adhoc、无 Team ID。
- Windows artifact `12091001863` 外层 SHA-256 与 Actions digest 一致：`ada8035bec08b3115672a74782a471404ce3df08b6beac85d6c8060763857315`，ZIP CRC 通过；EXE SHA-256 `3e3ffc846a45c9333125a6ec9b87ed3e6ff7f52f8d2cfb0944f066080e4b6d92` 与 sidecar 一致，PE32+ GUI x86-64，证书表大小为 0（未签名）。
- 这些是 PR 候选包与 runner smoke 证据，不能替代用户设备安装/升级、正式签名、公证、Release 或商店验收。

## f9da306 双平台 CI 与桌面候选上传（2026-10-17）

- PR CI run `39006513269` 对 head `f9da3068eb345a880dae13358aad755ef66f1f1c` 的 Windows/macOS 全套测试、静态、版本、页面和敏感值检查均 success；发布 job 因 PR 为 draft skipped。Actions 对 `actions/checkout@v4` 与 `actions/setup-python@v5` 发出 Node.js 20 弃用警告，桌面候选 workflow 的 `actions/upload-artifact@v4` 也有相同警告。
- Desktop candidate run `39006513267` 两平台构建、runner 启动 smoke 与 artifact 上传均 success。Windows artifact `12091565156`（20,534,141 bytes）Actions digest 为 `66bf716242921530348f84891c3569f1d7e6814c0f233e4343077eaa08fa5839`；macOS artifact `12090493655`（17,992,449 bytes）Actions digest 为 `f3ebe9b32ad5ae71e9b57d6662345280507547e28aac9022e36e815f6a9e50a0`。该 digest 来自 GitHub artifact 元数据，本轮未能本机下载回读候选包内容：`gh run download` 对 Actions blob 下载返回 EOF，改用系统 Python 的 TLS 下载分别返回 EOF 与 401，达到三次下载尝试后停止。
- 因未取得本机包体，本轮不记录内层文件哈希、Windows PE/签名或 macOS bundle/code signature 回读结果。当前证据只确认 Actions 构建、runner smoke、上传步骤与 artifact 元数据成功；仍为 draft PR 候选，不代表用户设备安装、正式发布、Developer ID/公证、升级或商店验收。

## dae0f8e macOS 当前安装界面观察与 Android 构建轮询（2026-10-17）

- CUA 应用清单显示本机“校园网连接管家”进程运行中；窗口标题与界面版本为 v5.6.0，主窗口可见。截图含本机档案字段，未保存或转录。此项只证明当前安装版窗口可见，不以界面状态文字代替实际校园网或 VPN 流量验证。
- 当前可访问的无障碍树只给出标准窗口和菜单；针对可见的“新手向导”“网络控制台”按钮点击后没有观察到窗口或页面切换。因此本轮不能据此判定这些功能通过或失败，按钮级功能验收仍待完成。
- Android API 36 debug APK run `39006870412`（head `dae0f8ede3f97cd00d71cf7e1d8a9f6e514f565b`）在本次核对时仍处于步骤 11“构建 Android API 36 debug APK”；前置环境步骤均 success，Manifest、KVM、模拟器安装启动和 APK/emulator evidence 上传仍 pending。继续只轮询该 run，不重启。
- 这次没有保存或修改本机档案；当前窗口状态、Actions 编译及桌面候选包都不构成 Windows 用户设备、Android 真机、iOS 真机、商店或正式签名发布验收。

## a3dc709 双平台 CI 与桌面候选包回读（2026-10-17）

- PR CI run `39007754660` 对 head `a3dc7096e9c90286c21d0fd74bb49e18fddf566c` 的 Windows/macOS 测试、静态、版本、页面与敏感值检查均 success；正式发布 job 因 PR 仍为 draft 而 skipped。
- Desktop candidate run `39007754498` 两平台构建、10 秒 runner launch smoke 和 artifact 上传均 success。Windows artifact `12091263082` 的 SHA-256 为 `278831868f0067ad6247b20f777d23c398205e488ba3508676991744340233c6`，与 Actions digest 相同；外层 ZIP CRC 通过。EXE SHA-256 `936bd651b007513adf713773be29b1c51b99aca41811af93bc78a110617f340f` 与 sidecar 一致，文件为 PE32+ GUI x86-64；PE Security Directory 为 0，未签名。
- macOS artifact `12091228169` 的 SHA-256 为 `438de1fee4d5676541ae14a6a94d0129115e7d37ae09835cf675357c02df19a7`，与 Actions digest 相同；外层 ZIP CRC 通过。内层候选 ZIP SHA-256 `38361dcbae18c8b701fa58709f304e3cface66c89907bcd57a463b3cf0bb45c8` 与 sidecar 一致，CRC 通过；含 62 个符号链接。用 `ditto` 解包后 strict codesign 验证通过；bundle id `com.campusnettools.campusnetmanager`、版本 `5.6.0`、arm64；adhoc 签名、无 Team ID。
- CUA 键盘操作可打开偏好设置窗口并回到主窗口；更新检查按钮未观察到结果变化，因此更新服务交互仍未证实。macOS 主窗口可见及 runner smoke 不等于逐项控件验收、更新安装、公证或用户设备验收。
- Android API 36 debug APK run `39006870412`（head `dae0f8e`）在本次检查时仍停在 APK 编译步骤 11；Manifest、KVM、模拟器、APK 与运行证据上传仍未开始。仅轮询原 run，不重启。两项桌面 artifact 是 draft PR 候选，不是正式 Release、用户设备安装或商店验收。

## dae0f8e Android API 36 模拟器运行完成（2026-10-17）

- 修正前文当时状态：Android API 36 debug APK run `39006870412`（head `dae0f8ede3f97cd00d71cf7e1d8a9f6e514f565b`）最终 completed/success。APK 构建、合并 Manifest 前台服务声明、KVM 权限、API 36 模拟器安装启动、APK artifact 上传和 emulator evidence 上传步骤均 success；模拟器进程保持 10 秒并通过启动/崩溃日志门禁。
- APK artifact `12091811318`（67,968,031 bytes）在 Actions artifact 元数据中 digest 为 `8226705462e9ab061948388ff0e7d8760aecbc7e1874dc8c3cb0635336b28cc7`。本轮用 `gh api` 下载返回 EOF；改用连接器获取临时下载引用后，本机 TLS 下载返回 `SSL_ERROR_SYSCALL`。因此只确认 Actions 上传成功和元数据 digest，未取得 APK 包体做本机 CRC、Manifest、ABI 或内层哈希回读。
- Emulator evidence artifact `12091323267`（69,120 bytes）元数据 digest 为 `a7abd8afc4539024331979f94d3e3a7d4e8f7dc04f61046ac14410b0be8d5cc8`；本地证据 ZIP SHA-256 与该 digest 相符且 ZIP CRC 通过。logcat 报告 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，无 `FATAL EXCEPTION`、`ANR in` 或进程死亡记录；1080×2400 模拟器截图显示登录表单和上述状态，账号/密码框为空。该结果是 runner 上模拟器启动证据，不是校园认证服务器、实体手机或网络流量验收。
- 该 head 的 PR CI run `39008182645` Windows/macOS 检查均 success，发布 job 因 PR 为 draft skipped；Desktop candidate run `39008182648` 的双平台 build、runner smoke 和 artifact upload success。该两项桌面候选包不属于本节 Android APK 包体回读，也不构成用户设备安装或正式发布。
