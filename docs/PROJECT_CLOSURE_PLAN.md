# 校园网连接管家全端闭环基线

更新时间：2026-10-18

## 最近一次核验快照（2026-10-18，HEAD 8165cd2）

- 当前分支 `codex/full-project-closure`、本地 HEAD 与 `origin` 均为 `8165cd23573484b809a030bb7de684fedb1e3046`，工作树干净；PR #1 为 OPEN draft，head 对齐。该 head 的 PR CI run `39096133148` 和 Desktop candidate run `39096133096` 均 completed/success；未发现仍活跃的 run。公开 Release 最新为 `v5.5.0`，`v5.6.0` 尚未公开。
- 本机 `python3 -m unittest discover -s tests`：553 tests、3 skipped，全部通过；`scripts/sync_version.py --check` 通过。
- 桌面候选 `/Users/nanyu/Desktop/CampusNetManager-macOS-arm64-v5.6.0.zip`：SHA-256 `ad7f66820d8f42ccf4e52ec4b5f796e0b5d1306cd86a6d4c0029f93df15bb60f`，ZIP CRC 通过；解包后 bundle `com.campusnettools.campusnetmanager`、版本 5.6.0、Mach-O arm64，55 个 symlink，`codesign --verify --deep --strict` 通过。签名为 adhoc、无 Team ID、未公证，仍是本机候选包。`/Applications/校园网连接管家.app` 当前运行，bundle strict codesign 与版本检查通过；控件逐项验收和升级尚未完成。
- 直下载状态：GitHub 最新正式 Release 仍为 v5.5.0，仅有旧 macOS/Windows 资产；没有 v5.6.0 公开下载链接。PR 仍为 draft，当前未打 release tag。
- iPhone：本轮 `idevicepair validate` 返回 `No device found`，`cfgutil list` 未列出设备。此前 `cfgutil install-profile` 返回 ConfigurationUtilityKit error 625（需要设备端交互），因此不能认定 IKEv2 profile 已安装。此轮仅确认 strongSwan `charon` 进程存在；未验证当前 IKE SA、服务器外网可达性或重启恢复，未观察手机双向流量。
- Android：`adb devices` 没有已连接设备。既有 API 36 模拟器构建/安装/启动记录只适用于其对应源码 head，不等同本轮 Android 真机验收。Windows 实体设备未接入，用户端安装/升级与逐功能检查尚缺。
- 本快照覆盖并更新本文更早的状态描述；此前按日期记录的证据仍保留为历史，不因本快照自动升级其证据范围。

本轮开始核验时 HEAD、origin 与 PR #1 head 均为 `16d2fa99f5c3d61313d0f11c630917bccc9c9b61`（`codex/full-project-closure`）；PR 为 OPEN draft，工作树干净。Windows/macOS 与 Android 候选包对应的源码 head 为其祖先 `b4f67c3a52486ad1db97e742096c6dd1a1c3f28a`；从该提交到本轮开始时没有非文档文件变化。
可恢复标签：`codex/full-project-closure-baseline-2026-10-16`。Android 前台保活改动前检查点：`c03bfd26817b14eb4aabefabf4fc8678d6f2db38`。

## 目标

按平台完成现有功能开发、自动检测、构建、免费直接下载分发和真实设备验收。用户不要求应用商店上架或付费；接受平台安装所必需的免费签名。源码、测试、CI、候选包、安装运行、真机和校园网络分别记录，不能互相替代。

## 平台交付矩阵

| 平台 | 当前证据 | 尚需验收 |
|---|---|---|
| Windows 桌面 | v5.6.0 候选在 run `39090548425` 构建和 runner launch smoke 成功；EXE sidecar/hash 与 Actions artifact digest、CRC 一致，PE32+ GUI x64；Authenticode 未签名 | Windows 用户设备下载安装、逐功能和升级；直下载 Release 及回读。告知 SmartScreen 可能提示 |
| macOS 桌面 | 本机 `/Applications/校园网连接管家.app` v5.6.0 可运行；adhoc strict codesign 通过。run `39090548425` 的 ZIP 保留 62 symlinks，`ditto` 解包后 strict codesign 通过，arm64、无 Team ID | 控件逐项、用户设备升级和公开直下载资产回读；adhoc/未公证包可能有 Gatekeeper 提示 |
| Android | run `39090546301` 在 API 36 runner 模拟器安装启动成功；APK 有项目自有免费稳定签名，v2/v3 验签与 SHA-256 指纹匹配，截图显示 ready 登录页 | Android 真机下载安装、登录、锁屏/切网、Keystore 与后台行为；校园网络真实流量 |
| iOS | 有 iOS Simulator build/install/launch 和 8 项 enrollment XCTest 通过记录；源码已有完整系统 IKEv2 `.mobileconfig` 备用路线，无需安装 iOS App/Xcode；本轮 profile 单测 5/5 通过；iPhone 经 USB 枚举并由 libimobiledevice 验证配对，iOS 26.6.2 | 用户选择长期方案为系统 profile；需网关在线并安全生成含单设备凭据的文件，在 iPhone Settings 安装，随后验 VPN 与双向流量。当前 `charon` VICI socket 不存在，网关私有状态需管理员授权；Computer Use UI runtime 缺失。原生 companion App 控件路线仍需 Xcode/签名，不作为当前长期方案 |

## 当前状态摘要（2026-10-18）

- PR CI run `39090548424` 的 Windows/macOS 测试和静态检查成功；发布步骤按 draft 规则跳过。Desktop candidate run `39090548425` 的 Windows/macOS build、runner launch smoke、artifact 上传成功。公开 GitHub Release 最新仍为 v5.5.0；v5.6.0 尚未公开发布。
- macOS artifact `12122109587`：外层 SHA-256/Actions digest `2b43a51a4e06a0ad022bb533246250b254ace4c55b8adfb7940dc0ae10042e9d`，CRC 通过；内层 ZIP SHA-256 `9e8787fe7b1651aae9273d137357e6ae6df389b946f8b5b961755aaf0a0d296b` 与 sidecar 一致，CRC 通过，含 62 个 symlink。`ditto` 解包后 `codesign --verify --deep --strict` 通过，bundle `com.campusnettools.campusnetmanager`、v5.6.0、arm64、adhoc、无 Team ID。
- Windows artifact `12122089755`：外层 SHA-256/Actions digest `db3b55089fae7c0c3396a6ba749081cdf29cd09c5612d25a15dc14a57d17fa4d`，CRC 通过；EXE SHA-256 `b04a0c41837377dff6e73ee5af01d3f1726d67537af28fb457a47fcd647720aa` 与 sidecar 一致，PE32+ GUI x64，Authenticode certificate table size 为 0。均为候选包，不是用户设备安装验收。
- Android run `39090546301`（head `b4f67c3`）completed/success。API 36 APK build、前台服务 Manifest gate、免费签名指纹检查、APK 准备、KVM 与模拟器安装/启动步骤均 success。APK artifact `12122867765` 外层 digest/CRC 通过，SHA-256 `aa18ac9202dcf5eaf639c5a9e6b7d48adb0696b4e12c1c1d37121bbf46db044b`；内层 `CampusNetManager-Android-5.6.0.apk` SHA-256 `b38cc6742afc6a5aff285bb92bfa349b0d83789ca2582a5096a7550c403082cc` 与 sidecar 一致，APK ZIP CRC 通过，含 arm64-v8a、armeabi-v7a、x86_64。Actions `apksigner` 日志显示 v2/v3 均验证有效，项目证书 SHA-256 指纹 `a6a3451d09b6ec3b34f12ee07193233b812a04acd2ba711ab56dd466bb6aa613` 匹配。
- Android emulator evidence artifact `12122269908` 外层 digest/CRC 通过。logcat SHA-256 `3a5b27a44ecf950e304421869d09f9d8b91a993fe347b3be2832220d91c0be59`；出现 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，未检出 FATAL EXCEPTION、ANR、进程死亡或 Force finishing。截图 SHA-256 `c0552197ccf315adb01f4b8aa19f6ca3983384db250904787c74a315e0e8b798`，显示非加载态登录页、账号密码为空及 HTTP 明文凭据风险提示。模拟器不代表实体 Android 手机或真实校园网登录。
- 本机 `adb devices -l` 无连接 Android 设备；`xcode-select -p` 为 Command Line Tools，`xcrun simctl` 不可用。iPhone 已通过 USB 在 IOUSB 树出现并由 libimobiledevice 成功验证配对、读取产品类型与 iOS 版本；Computer Use runtime 仍报 app missing，尚无屏幕控件/配置安装证据。Windows 用户设备也尚未接入。
- 本机 macOS app accessibility 窗口标题为 v5.6.0，进程可以置前运行；Computer Use 控件读取/点击接口仍报运行时错误，故不把应用窗口标题等同于逐功能验收。
- 仍待：Android 真机锁屏/切网/Keystore；iPhone 的系统 `.mobileconfig` 安装、VPN 授权与 IKEv2 双向流量；Windows 用户设备安装/逐功能；macOS 控件逐项与升级；将经确认的桌面资产发布为免费直下载并回读。不得把模拟器、runner smoke 或候选包称为真机或正式 Release。

## macOS 本地桌面包与 iOS 长期免 Xcode 路线（2026-10-18）

- 用户本轮要求先处理 macOS 与 iOS，并明确不要 Xcode/短期个人签名，希望零成本且能长期使用；允许用浏览器或桌面包替代。
- macOS 将本机 `/Applications/校园网连接管家.app` v5.6.0 用 `ditto` 打包到桌面：`/Users/nanyu/Desktop/CampusNetManager-macOS-arm64-v5.6.0.zip`，SHA-256 `ad7f66820d8f42ccf4e52ec4b5f796e0b5d1306cd86a6d4c0029f93df15bb60f`；对应校验文件为同名 `.zip.sha256`。外层 ZIP CRC 通过；解包后 55 个符号链接与源 app 一致，`codesign --verify --deep --strict` 通过。包是 adhoc 签名、无 Team ID、未公证的本地候选，不是公开 Release；从互联网下载时 Gatekeeper 可能要求用户手动允许。
- iOS 的免费个人签名 profile 会在 7 天后到期并要求重装，不符合用户的长期要求。当前采用项目已有的完整 IKEv2 `.mobileconfig` 作为无 Xcode 替代：Safari/本地传输到 iPhone 后由 Settings 安装，VPN 由系统管理；这不提供 Companion App 的连接/状态 UI，也不是 PWA 对 `NEVPNManager` 的控制。
- 配置文件含单设备 EAP 用户名和密码，必须在授权网关 Mac 本地生成、经 AirDrop/USB 私下传递，安装后删除，不能公开托管。本仓库网关安装脚本创建的 CA 有效期 3650 天、服务器证书有效期 825 天，需在到期前续期；因此方案长期但非永久。
- 本轮 `python3 -m unittest tests.test_ikev2_profile -v` 5/5 通过，证明 profile 结构生成逻辑；没有在 iPhone 安装或连 VPN。`swanctl --stats` 未找到 `/var/run/charon.vici`，且私有状态目录不能在无管理员授权时读取；`adb devices -l` 为空、USB 名称列表未识别 iPhone；真机与网关网络验收未完成。

## iPhone USB 配对核验更正（2026-10-18）

- 用户提醒 iPhone 已通过 USB 连接。补查 IOUSB device tree 后确认 iPhone 已枚举；安装免费的 Homebrew `libimobiledevice` 1.4.0_2（不安装 Xcode），`idevicepair validate` 成功，读取到 ProductType `iPhone18,1`、iOS `26.6.2`。未在文档记录设备序列号或 UDID。
- `adb devices` 为空只反映 Android 设备；不能据此判断 iPhone。Computer Use app runtime 仍不可用，所以未能读取 iPhone 屏幕或操作 Settings。
- iOS run `39094409561`（head `0093f9b`）已成功：8 项 enrollment XCTest、unsigned Simulator build、模拟器安装/启动、完整 `.app` ZIP 与 artifact 上传均通过；artifact `12123794529` 上传 digest `08e855525edfe721d8801b9147db6dd7522098ae10c12a258c9625695feb4002`。这是 GitHub macOS runner 的模拟器检查，不是 iPhone 安装或系统 VPN 实测。
- 网关已安装 strongSwan，PF 配置中已有项目 anchor；但当前仍无 `/var/run/charon.vici`，且 CA 私有文件因 root 权限不可读。尝试通过 macOS 管理员授权服务启动脚本返回 `Operation not permitted (126)`；未生成/安装 `.mobileconfig`，未验证 VPN 流量。需要解决本机管理员授权/自动化权限后再继续。

## 初始核验基线（2026-10-16，历史记录）

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
- APK artifact `12091811318`（67,968,031 bytes）Actions digest 与后续通过 GitHub connector + Node fetch 取回文件的外层 SHA-256 一致：`8226705462e9ab061948388ff0e7d8760aecbc7e1874dc8c3cb0635336b28cc7`，外层 ZIP CRC 通过。内含 APK SHA-256 `376e11f42ec94b613ed3b90b55c7b918d39ab16dd380fbc94a742233c1d4490c`，APK ZIP CRC 通过，共 56 entries，含 `AndroidManifest.xml` 及 `arm64-v8a`、`armeabi-v7a`、`x86_64` 三个 ABI。run 的 Manifest gate 对合并 APK 的前台服务声明检查 success；本机未安装 aapt，未独立解码 Manifest 属性。
- Emulator evidence artifact `12091323267`（69,120 bytes）元数据 digest 为 `a7abd8afc4539024331979f94d3e3a7d4e8f7dc04f61046ac14410b0be8d5cc8`；本地证据 ZIP SHA-256 与该 digest 相符且 ZIP CRC 通过。logcat 报告 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，无 `FATAL EXCEPTION`、`ANR in` 或进程死亡记录；1080×2400 模拟器截图显示登录表单和上述状态，账号/密码框为空。该结果是 runner 上模拟器启动证据，不是校园认证服务器、实体手机或网络流量验收。
- 后续独立下载原始 APK artifact `12091811318` 验证 Actions 外层 digest、SHA-256 与 ZIP CRC 一致；APK 自身 SHA-256 为 `376e11f42ec94b613ed3b90b55c7b918d39ab16dd380fbc94a742233c1d4490c`，ZIP CRC 通过，含三个 ABI。该 run 的 logcat 同时出现 `hidapi` 初始化错误，内容为 Android 要求动态 receiver 指明 `RECEIVER_EXPORTED` 或 `RECEIVER_NOT_EXPORTED`；错误之后应用仍输出网络状态 ready marker，截图也已渲染登录界面，因此它没有阻断本次首屏启动，但 HID/USB 接收器能力未验收。
- 该 head 的 PR CI run `39008182645` Windows/macOS 检查均 success，发布 job 因 PR 为 draft skipped；Desktop candidate run `39008182648` 的双平台 build、runner smoke 和 artifact upload success。该两项桌面候选包不属于本节 Android APK 包体回读，也不构成用户设备安装或正式发布。

## c251e32 双平台 CI 与桌面候选包回读（2026-10-17）

- PR CI run `39008571202` 对 head `c251e32a7cf62549c4fa7614a6637e4f9cc3f573` 的 Windows/macOS 全套检查均 success，发布 job 因 PR 为 draft skipped。Desktop candidate run `39008571404` Windows/macOS build、runner launch smoke 与 artifact upload 均 success。
- macOS artifact `12091827800`（17,995,078 bytes）外层 SHA-256 与 Actions digest 一致：`d40cf6384f61790f82a3adc8dc70afb84ed274ab4de4b5c4b629c0207801bdb7`，ZIP CRC 通过。内层候选 ZIP SHA-256 `79c0bee4bd288fba945d7fb586c9a791c984817f92c8bdc244b672071624af97` 与 sidecar 匹配，ZIP CRC 通过；ditto 解包后 strict codesign 通过，app bundle id `com.campusnettools.campusnetmanager`、版本 `5.6.0`、arm64、62 个 symlink、adhoc 签名、无 Team ID。
- Windows artifact `12091698073`（20,534,303 bytes）外层 SHA-256 与 Actions digest 一致：`1bd0f323dfb30d0662d9821c7e6d96cbd03234014c4e338af0ac8e46b6a8a6c3`，ZIP CRC 通过。EXE SHA-256 `f5c0a67a90699b2d47766535a314cf8ac6788e2a80b91177bd8cf704a22557ec` 与 sidecar 匹配，文件为 PE32+ GUI x86-64；PE Security Directory offset/size 均为 0，未签名。
- 两份为 draft PR 候选，构建和 runner smoke 不证明真实 Windows 用户设备安装、macOS Developer ID/公证、升级或正式 release。Android APK 的后续本机回读结果见上一节。

## iOS IKEv2 enrollment 校验与 XCTest 自动检测（2026-10-17）

- 加强 Swift enrollment 导入校验：IPv4/IPv6 使用系统地址解析器检查，DNS 标签限制为 ASCII 字母/数字/连字符；拒绝畸形地址、带 scope 的 IPv6、含空白主机名和无效 DNS 标签。Mac 侧 profile generator 使用同一主机名边界，避免导出后被 iOS App 拒绝。
- 新增 `CampusNetCompanionTests` XCTest target，覆盖生成格式、IPv6、畸形 IPv4/IPv6、无效服务器标识、空凭据及未知版本；iOS Simulator workflow 在安装启动 app 前执行 `xcodebuild test`。
- 本机运行受影响的 Python profile 测试 `5 passed`；Swift 源码/测试语法解析、XcodeGen 项目 YAML、workflow YAML 与 `git diff --check` 均通过。本机 Swift 6.3.3 与 macOS 27 SDK 所需 Swift 6.4 不匹配，故本机未能 typecheck；对应 source head `80928747` 的 Actions run `39009254452` 在匹配 Xcode runner 上执行 XCTest：6 tests、0 failures，Simulator build、install、launch、package 和 artifact upload 全部 success。
- iOS Simulator artifact `12092731306`（5,156,008 bytes）SHA-256 与 Actions digest 一致：`b0c4ee1487a575f6dfbf60d8a37662f97ca7c7f9c94236ceb450c37ae1b18f2e`，外层 ZIP CRC 通过；内层 `CampusNetCompanion-Simulator.app.zip` 有 54 项且 CRC 通过。bundle id `com.campusnettools.companion`，版本 `0.2.0 (3)`，主二进制为 x86_64/arm64 universal。主二进制显示 adhoc linker signature；整个 app bundle 未做分发签名、没有 Team ID，strict bundle signature verify 不通过（`CODE_SIGNING_ALLOWED=NO`）。
- 新增 XCTest 只覆盖 enrollment 配置解析边界；Simulator install/launch 与 artifact 不证明真机凭据存储、系统 VPN 授权、IKEv2 建连或双向流量。真机签名、App Store 资格和发布仍未验收。

## Dr.COM 登录客户端凭据额外暴露面收敛（2026-10-17）

- `core/auth.py` 的 macOS/Windows 物理网卡请求原先把完整 URL 作为 curl 进程参数，其中 Dr.COM 登录查询串包含账号和密码。现在通过 curl 标准输入配置传递 URL，命令行不再携带登录查询串；Python HTTP 路径的登录 `Referer` 收敛到认证服务器根地址，避免重复传播凭据。
- Dr.COM 原有 GET/HTTP 登录格式保持不变。HTTP 明文传输、门户服务器/中间设备访问日志及真实学校门户兼容仍未解决或验证，详见 `docs/PRIVACY_DATA_INVENTORY.md`。
- 新增两个传输回归测试：curl 的进程参数与 stdin 边界、Python 请求 Referer。使用本机 curl 对 loopback HTTP server 做了一次往返，服务端收到原始 GET 查询参数且根地址 Referer 正确；未连接校园网门户。
- 本轮完整 unittest：`531 passed, 3 skipped`；项目 CI 同款 Ruff F/E9 检查、Python 编译和 `git diff --check` 通过。此为源码/本机测试证据，不代表远端 CI、真实校园网络、设备或商店验收。

## Dr.COM HTTP 登录风险的界面披露（2026-10-17）

- 桌面连接档案的校园网表单和 Android 登录页现在在认证地址附近提示：当前 Dr.COM 登录通过 HTTP 发送账号和密码，校园网络可见，建议只在可信校园网登录。README、Android README 与用户手册同步说明。
- 新增 3 项文案回归检查。完整 unittest 为 `534 passed, 3 skipped`；Ruff F/E9、Python 编译与 `git diff --check` 通过。
- 本地 UI 控件级渲染/小屏适配以及用户确认未完成；HTTP 明文传输风险仍存在。当前 Android run `39010565663` 对前一提交仍处于 API 36 APK 编译步骤，未重启；本次 UI 改动提交后的构建与模拟器验证待新 Actions run。

## fd22a47 登录风险披露提交的 CI 与桌面候选回读（2026-10-17）

- PR CI run `39010893823` 对提交 `fd22a47ec2ad8de2b61f9b72d593766f5cf5119b` 的 Windows/macOS 检查均 completed/success；Desktop candidate run `39010893890` 两平台构建、runner launch smoke 和 artifact 上传均 success。发布仍受 PR draft 规则约束。
- macOS artifact `12092399515` 的 Actions digest 与下载 ZIP SHA-256 均为 `c9147225818293fb49e8a67424189b02e86c9cd1e5512d5efad5692c985365fc`，ZIP CRC 通过。内层候选 ZIP SHA-256 `d5671f8b9b4c75d4f5c469063e98786f969eda8b818b18e0b12cd1172e96a6dd` 与 sidecar 一致、CRC 通过；ditto 解包后 bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64、62 个 symlink，strict codesign 通过，签名 adhoc、无 Team ID。
- Windows artifact `12092439261` 的 Actions digest 为 `e8cb846e6fc790a0d26797e461e42e3052d0bdb357d7dc7ab244df0ec45bbdeb`。本机 artifact 下载遭 GitHub API EOF 和 `SSL_ERROR_SYSCALL`；达到重试上限后停止，未独立回读 Windows ZIP/sidecar/EXE。不得据此推断产物损坏或已通过本机哈希复核。
- Android run `39010565663`（head `20f58f5`）和新 UI 提示提交 run `39010889130`（head `fd22a47`）在最近检查时仍处于 API 36 APK 编译步骤 11。两者仅轮询，不重启；新 head 的 APK、Manifest、模拟器首屏与运行 artifact 尚待终态验证。
- 桌面候选包与 runner smoke 不代表 Windows 用户设备安装、macOS Developer ID/公证、升级或正式 Release；Android API36 runner 也不代表实体手机、锁屏/切网、Keystore 或商店验收。

## 5655974 登录风险文档提交的 CI 与桌面候选回读（2026-10-17）

- PR CI run `39011120295` 对 head `5655974ea4c89f8a8efe2e069f7eb84ceda96260` 的 Windows/macOS 全套测试、静态检查、版本、页面与敏感值检查均 success；release job 按 draft PR 规则 skipped。Desktop candidate run `39011120308` 两平台构建、runner 启动 smoke 与 artifact 上传均 success。
- macOS artifact `12092662448`（17,994,953 bytes）Actions digest 为 `19254d1369d1ed6b6c9cdd7c1cb586ea04c6029bdd1b910a723429dcd061c11a`。下载出的候选 ZIP SHA-256 `de1ef14109bd1d9306d19afb971975676e5e42b9ef6982bd7c62ef3435dc52c3` 与 sidecar 一致，ZIP CRC 通过；含 62 个符号链接。用 `ditto` 解包后 strict codesign 通过，bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64；adhoc 签名、无 Team ID。
- Windows artifact `12092778275`（20,535,286 bytes）Actions digest 为 `a04c318f493c21430af597327d67a12d2bf89617db433144bf56ef831a644420`。下载出的 EXE SHA-256 `2089a865cd14b93836b8f493ba3f5bfac1f5a530022d8b9dd6c7d124da12e22d` 与 sidecar 一致；文件为 PE32+ GUI x86-64，PE Security Directory offset/size 均为 0，未签名。
- Android API 36 APK run `39010565663`（head `20f58f5`）与 `39010889130`（head `fd22a47`）最近仍为 in progress、停在 APK 编译步骤 11；后者日志尾部显示 NDK 正在编译 OpenSSL x86_64。前者 job log 下载返回 Transport closed，原因未确认。只轮询原 run，不重启；Manifest、模拟器、artifact 均待后续步骤完成。
- 桌面候选与 runner smoke 不证明 Windows 用户设备安装、macOS Developer ID/公证、升级或正式 Release；Android runner 也不代表实体手机、锁屏/切网、Keystore 或商店验收。

## de0d5ef 桌面候选回读与本机运行界面观察（2026-10-17）

- PR CI run `39011344762` 对 head `de0d5ef557b55cb5cfd5977da38b7d6aa2970e9a` 的 Windows/macOS 全套检查 success；Desktop candidate run `39011344664` 两平台构建、runner 启动 smoke 和上传 success。
- Windows artifact `12093340150`（20,535,406 bytes）Actions digest 与下载的 artifact ZIP SHA-256 均为 `d16a0c6a4871be05bfa92c2e24f1c25812d7f800f5243875a1663470338734d1`，外层 ZIP CRC 通过；EXE SHA-256 `a7aa4606638066531c21d69467978bf08aecf1b62749266a868c19edfb0224a4` 与 sidecar 一致，文件为 PE32+ GUI x86-64，Security Directory offset/size 均为 0，未签名。
- macOS artifact `12092782296`（17,995,218 bytes）Actions digest 与下载的 artifact ZIP SHA-256 均为 `69996739b50dfe0ace2ab860d4570fe6d3190353feb30d9de336f6d0e287fbba`，外层 ZIP CRC 通过；候选 ZIP SHA-256 `3176d4897518e014c60283a994c3ab5f1ade02846044b9f127bc403e08a34d1b` 与 sidecar 一致、CRC 通过，含 62 个符号链接。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64；adhoc 签名、无 Team ID。
- 本机已安装应用窗口标题显示 v5.6.0；主页显示“守护：运行中”和“VPN 与校园网在线”。这是界面状态观察，不等于隧道双向流量或网络可达性验收；未读取或记录账号字段，也未修改配置或停止服务。当前自动化未获得应用画布内部控件的可访问树，不能据此判定各功能按钮通过。
- 截至 2026-10-17 06:53 UTC，Android APK runs `39010565663`（head `20f58f5`）和 `39010889130`（head `fd22a47`）仍为 in progress，尚无终态或 artifact；两次 Actions job log 获取均返回 `Transport closed`，不据此推断构建失败或停滞。只轮询原 run，不重启。
- Desktop packages 是 draft PR 候选与 runner smoke，不证明用户设备安装、Developer ID/公证、升级或正式 Release。Android runner 也不代表实体手机、锁屏/切网、Keystore 或商店验收。

## 8b421b8 桌面候选回读与设备可用性复核（2026-10-17）

- PR CI run `39011643663` 的 Windows/macOS 全套检查均 success，release job 按 draft 规则 skipped；Desktop candidate run `39011643691` 两个平台构建、runner 启动 smoke 与 artifact 上传均 success。
- Windows artifact `12093415365`（20,533,119 bytes）Actions digest 与下载 artifact ZIP SHA-256 一致：`466eb98634700e67538a801648fd9678f7b1674fcaf24a851c481fcdb04b8330`，外层 ZIP CRC 通过；EXE SHA-256 `9389af9d1ced427c7d58e1a3e20b6275a77a72e092debf61cb3e21365ac6d88a` 与 sidecar 一致，PE32+ GUI x86-64，Security Directory offset/size 均为 0，未签名。
- macOS artifact `12092428899`（17,994,384 bytes）Actions digest 与下载 artifact ZIP SHA-256 一致：`11fe05dd1192b09633f6260824cbf06397858230e76881a61a29ac019f5f26a2`，外层 ZIP CRC 通过；内层候选 ZIP SHA-256 `acd14ff07ee6ef3e66fe5a52c87d5ee6761139ddef39c8d932e498f977644d09` 与 sidecar 一致、CRC 通过，含 62 个符号链接。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64，adhoc 签名、无 Team ID。
- 本机检查仍无 Android `adb`、完整 Xcode、`simctl` 或 iOS provisioning profile。iPhone 镜像恢复连接后显示找不到设备，要求设备在 Mac 附近、开机、近期解锁并启用蓝牙/Wi-Fi；没有加载到手机应用界面，也没有进行真机测试。
- Android APK runs `39010565663`（head `20f58f5`）和 `39010889130`（head `fd22a47`）的 job 当前仍在 API 36 APK 编译步骤 11；job metadata 为 in progress，日志下载返回 `Transport closed`，尚无 Manifest/emulator/artifact 终态证据。只轮询原 run，不重启。
- 以上桌面包仍是 draft PR 候选；CI/runner smoke、macOS 本机界面状态和包签名结构均不替代 Windows 用户安装、Android/iPhone 真机验收、Developer ID/公证、升级或正式商店发布。

## b25d5aa 双平台 CI 与桌面候选包回读（2026-10-17）

- PR CI run `39011806988` 对 head `b25d5aa0e1c9d75d5ac5bb8c649d880b834f890c` 的 Windows/macOS 检查全部 success，release job 按 draft 规则 skipped。Desktop candidate run `39011806984` 两平台构建、runner 启动 smoke 与 artifact 上传 success。
- Windows artifact `12093685060`（20,535,393 bytes）Actions digest 与下载 artifact ZIP SHA-256 一致：`2b989156074abb3b409e248799f6a9bd51f7e1778bfc0d8058650c4f1e30f44a`，ZIP CRC 通过；EXE SHA-256 `73f2b77ab7a711d3f73f19109829171cc1241d2b7d21651af78c0a5bd4bf3537` 与 sidecar 一致，文件为 PE32+ GUI x86-64，Security Directory offset/size 均为 0，未签名。
- macOS artifact `12092673211`（17,995,704 bytes）Actions digest 与下载 artifact ZIP SHA-256 一致：`2b49256e9bca73c50fc0bc3ad5e0655fce8475cb108e535d442606dd19e1ae36`，外层 ZIP CRC 通过；候选 ZIP SHA-256 `3f05da560967d4f218760a0d54f8be0760bbaa352a677d8de8595bfe23fdbb62` 与 sidecar 一致、CRC 通过，含 62 个符号链接。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64，adhoc 签名、无 Team ID。
- 两份均为 PR draft 候选。它们不证明用户设备安装/升级、Windows Authenticode、macOS Developer ID/公证或正式 Release；对应真实手机和商店验收仍待完成。

## 53c9291 双平台 CI 与桌面候选回读（2026-10-17）

- PR CI run `39012018972` 对 head `53c9291ad4e68a870cb1e57fba621add59618ea9` 的 Windows/macOS 全套检查均 success，release job 按 draft 规则 skipped。Desktop candidate run `39012019038` 两平台构建、runner 启动 smoke 与 artifact 上传均 success。
- Windows artifact `12093296138`（20,533,014 bytes）Actions digest 与下载 artifact ZIP SHA-256 一致：`0da3afad34f8f57406115c94312619c0df24c60cc2204e43e61aecc051c4d63e`，ZIP CRC 通过；EXE SHA-256 `38be0832c6c18ee8ad9864303598e0fe0661a9164cfb2e0fca7c675f3a6028df` 与 sidecar 一致，文件为 PE32+ GUI x86-64，Security Directory offset/size 均为 0，未签名。
- macOS artifact `12093455787`（17,995,260 bytes）Actions digest 与下载 artifact ZIP SHA-256 一致：`2f5add5f38fbe170faa27597c2ac40b12d298b23b2300632908b588b8d4eda70`，外层 ZIP CRC 通过；候选 ZIP SHA-256 `7fb69f44f22549a557a708451ea88fa62d271897f932289c01d8d46632cb557e` 与 sidecar 一致、CRC 通过，含 62 个符号链接。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64，adhoc 签名、无 Team ID。
- Android APK runs `39010565663`（head `20f58f5`）和 `39010889130`（head `fd22a47`）查询时仍为 in progress，活动步骤为 API 36 APK 编译；Actions job log 工具返回 `Transport closed`，GitHub CLI 查询返回 API `EOF`。这些下载错误不代表构建失败，未重启原 run。
- Android/iPhone 真机、签名商店、Windows 用户设备安装、macOS Developer ID/公证和正式 Release 仍待验收；以上两项桌面产物仍是 PR 候选包与 runner smoke 证据。

## 47fb1a4 双平台 CI 与桌面候选回读、Android 进入模拟器阶段（2026-10-17）

- PR CI run `39012174284` 对 head `47fb1a4d792d69518f769169bdac874396f5d5d4` 的 Windows/macOS 全套检查均 success，release job 因 PR 为 draft skipped。Desktop candidate run `39012174407` 两平台构建、runner 启动 smoke 与 artifact 上传均 success。
- Windows artifact `12093580736`（20,535,332 bytes）Actions digest 与下载 artifact ZIP SHA-256 一致：`7cd477327fe82229a32397062f5ab2b1151c67ebc7fad5c52470c2a3a0bea5d5`，ZIP CRC 通过；EXE SHA-256 `abc477639c5760f631be911e4e88a77969da787bbc9de7f49a6c4232d4f645ac` 与 sidecar 一致，PE32+ GUI x86-64，Security Directory offset/size 均为 0，未签名。
- macOS artifact `12093755258`（17,995,586 bytes）Actions digest 与下载 artifact ZIP SHA-256 一致：`3f42c28102d8debd53361fdd8346c5921643152efd5be58b0f78330a7e889418`，外层 ZIP CRC 通过；候选 ZIP SHA-256 `537c3848c5a0f92a38cff47344e4d2334d4d3a4f7610d8c1d0de2cc43476823d` 与 sidecar 一致、CRC 通过，含 62 个符号链接。`ditto` 解包后 strict codesign 通过；bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64，adhoc 签名、无 Team ID。
- Android run `39010565663`（head `20f58f5`）已成功完成 API36 APK build、前台服务 Manifest 校验与 KVM 权限步骤，当前进入模拟器安装/启动步骤 14，尚无 APK/运行证据 artifact；步骤日志仍不可下载。另一个 run `39010889130`（head `fd22a47`）仍在 APK 编译步骤 11。Actions metadata 将两者标为 in progress；日志工具返回 `Transport closed`、CLI 查询提示 in progress 时日志暂不可用。只轮询原 run，不重启。
- 桌面候选与 runner smoke 不证明真实 Windows 安装、macOS Developer ID/公证、升级或正式 Release；Android 模拟器也不代表实体手机、校园网连接或商店验收。

## 392aa61 双平台 CI 与桌面候选 artifact 回读（2026-10-17）

- PR CI run `39012528736` 对 head `392aa614ac9a7647064f30ea93ae338a1b3efb11` 的 Windows/macOS 测试、静态、版本、页面与敏感值检查均 success；Release job 因 PR 仍为 draft skipped。Desktop candidate run `39012528746` 两平台 build、runner launch smoke 与 artifact 上传均 success。
- Windows artifact `12092718962`（20,535,565 bytes）下载 SHA-256 与 Actions digest 一致：`b0e8ff1dcfc268c454c803acca2846ea39c7146cdb6b66b4e68ee27a5f4ad916`，ZIP CRC 通过。EXE SHA-256 `872934a0573d69f20a63587a4f7e91471c78e605a1176d52f0d4bc53d75b3645` 与 sidecar 相符；PE32+ GUI x86-64，PE Security Directory offset/size 均为 0，未签名。
- macOS artifact `12093059485`（17,993,841 bytes）下载 SHA-256 与 Actions digest 一致：`16acfcedcea766ebfa182bc85cdb8452d2e1fa7ec258487b0ea72695d3d17fb0`，外层 ZIP CRC 通过。内层候选 ZIP SHA-256 `aeebc646b3a7ca493adbc5029add69a644e63bff7d3f363a17b62f58ca9e87eb` 与 sidecar 相符；ZIP CRC 通过，554 项、62 个 symlink。用 `ditto` 解包后 strict codesign 通过；bundle id `com.campusnettools.campusnetmanager`、v5.6.0、arm64；adhoc 签名、无 Team ID。
- 该提交只改文档。候选包及 CI runner smoke 不证明用户设备安装、逐功能验收、Windows Authenticode、macOS Developer ID/公证、升级或正式 Release。

## fd22a47 Android API36 模拟器验证登录风险提示（2026-10-17）

- Android run `39010889130`（head `fd22a47ec2ad8de2b61f9b72d593766f5cf5119b`）completed/success；APK build、合并 Manifest gate、KVM、API36 模拟器安装启动与 APK/evidence artifact 上传均 success。
- APK artifact `12093492574`（67,968,669 bytes）下载 SHA-256 与 Actions digest 一致：`2fb780e4ea518bcba222b01bdfd00bbe23c5faf8f6a098f536fec68daac3ee77`，外层 ZIP CRC 通过。内含 APK SHA-256 `0d54f4d66ff9c07465bacaf428cf8571523b4395929d2a6d1915449d74803933`，APK ZIP CRC 通过，共 56 项，含 `arm64-v8a`、`armeabi-v7a` 与 `x86_64` ABI。
- Emulator evidence artifact `12093412586`（97,249 bytes）下载 SHA-256 与 Actions digest 一致：`d1d00393dc70cb3e49eb587f601d6616145a850843222b2e1ec272c020873828`，ZIP CRC 通过。logcat 有 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，无 `FATAL EXCEPTION`/`ANR in`；smoke 脚本确认状态就绪后应用进程仍在运行。1080×2400 截图显示登录页中的 HTTP 明文账号/密码风险提示和空凭据框。
- 该 run 证明登录页风险提示已进入此次模拟器包并渲染；模拟器不连学校认证服务器，因此不证明 HTTP 门户兼容、真机网络/锁屏切网/Keystore 或 Play 验收。当前分支 PR #1 仍为 open draft；后续 desktop-only 文档提交的 CI 与候选包流程另行跟踪。

## 20f58f5 Android API36 模拟器运行完成（2026-10-17）

- 修正前文当时状态：run `39010565663`（head `20f58f54f4789fd8d633bb812d32e054489ef25c`）最终 completed/success。APK 构建、合并 Manifest 前台服务声明校验、KVM 权限、API36 模拟器安装启动、APK artifact 上传与模拟器证据上传步骤均 success。
- APK artifact `12092969670`（67,967,582 bytes）Actions digest 和下载 ZIP SHA-256 相同：`047ce25d7e919d5f0cb8e6385562ee3285acbc921a8413d6213b07f5166fac09`；外层 ZIP CRC 通过。内含 APK SHA-256 `bc1d57d56779f610cadba8b03e51bd305dd7c3052712dbf8540a5cdf97ef11fb`，APK ZIP CRC 通过，共 56 项，包含 `arm64-v8a`、`armeabi-v7a` 与 `x86_64` ABI。Manifest 由该 run 的 gate 验证；本机未独立解码合并 Manifest。
- Emulator evidence artifact `12092934772`（70,125 bytes）Actions digest 与下载 ZIP SHA-256 相同：`88db6102172bbc4599bde86cf16bf81c172177085e83edfbf2a39adb01d6fb46`；外层 ZIP CRC 通过。logcat 有 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，未发现 `FATAL EXCEPTION`、`ANR in` 或 app process death 记录；截图显示登录页、该环境状态和空账号/密码框。run 的模拟器步骤成功，但不证明校园网认证、真实手机锁屏/切网、Keystore 或网络流量。
- 同分支另一个 Android run `39010889130`（head `fd22a47ec2ad8de2b61f9b72d593766f5cf5119b`）查询时仍在 API36 APK 编译步骤 11；仅轮询原 run，不重启。`39010565663` 验证的是较早 head，不包含 `fd22a47` 的登录风险提示改动。

## 32c9a9e iOS enrollment XCTest 与 Simulator 包回读（2026-10-17）

- iOS Actions run `39013104364` 对 head `32c9a9ebb7d3041d3e15f2f086b0a4123731b3e0` completed/success。XcodeGen、工程生成、IKEv2 enrollment XCTest（6 tests、0 failures）、unsigned Simulator build、模拟器安装/启动、打包和上传均 success。
- artifact `12093464420`（5,156,249 bytes）SHA-256 与 Actions digest 一致：`efb55215d65a18c5cfb83b78ebaa67a33ef208cb98302e6dd262be7df862b54d`；外层 ZIP CRC 通过。内层 `CampusNetCompanion-Simulator.app.zip` SHA-256 为 `fcf580d68acd1dab2e881c3179b611e3f6c1b82bd5bc430adbdbb1e9ac4a04aa`，ZIP CRC 通过且保留完整 `CampusNetCompanion.app/` 目录。bundle id `com.campusnettools.companion`，版本 `0.2.0 (3)`，平台为 `iPhoneSimulator`，可执行文件含 x86_64/arm64。主二进制为 adhoc linker 签名；应用 bundle 无 Team ID、未做分发签名，工作流明确 `CODE_SIGNING_ALLOWED=NO`。
- XCTest 只验证 enrollment JSON 解码边界；模拟器包和运行不证明真实 iPhone 的 Keychain 生命周期、系统 VPN 授权、IKEv2 建连、双向流量、升级或 App Store 验收。
- 同 head Android APK run `39013104353` 仍在 API 36 debug APK 编译步骤；job `117339606809` 最近可读日志显示 NDK 正在编译 OpenSSL x86_64。Manifest、KVM、模拟器和 APK artifact 尚未产生终态证据；只轮询该 run，不重启。

## 3da21dc 双平台 CI 与桌面候选包回读（2026-10-17）

- PR CI run `39013871865` 对 head `3da21dc6c51797b3df5ad74c2b86a3a0736c5e6e` 的 Windows/macOS 测试及静态检查均 success；发布 job 因 PR 仍为 draft skipped。Desktop candidate run `39013871883` 的两平台构建、runner launch smoke 与 artifact upload 均 success。
- Windows artifact `12093857713`（20,533,986 bytes）Actions digest 与下载 ZIP SHA-256 一致：`0cbc197b3e5f1ad5004c5ff716fad0ee10c6f92c34a742d02d6e899fa6c7ed15`，ZIP CRC 通过；EXE SHA-256 `91c3a8032d8b6296af3ee351db8db57590ef9745327d0eac07e7f94fe11abdce` 与 sidecar 一致。PE 为 x86-64 PE32+，Authenticode Security Directory 为 `(0, 0)`，未签名。
- macOS artifact `12093817948`（17,994,722 bytes）Actions digest 与下载 ZIP SHA-256 一致：`905df5c8080c86d5b5aa934cad51935215c389e779a25e7bef53b20bcc40008d`，外层 ZIP CRC 通过；内层候选 ZIP SHA-256 `dbfb81a5266de47f90771fc258e4d27eb189668575485160a0c3d35030c5677c` 与 sidecar 一致，内层 ZIP CRC 通过，含 554 个条目和 62 个 symlink。使用 `ditto` 解包后 strict codesign 验证通过；bundle `com.campusnettools.campusnetmanager`，版本 5.6.0，arm64，adhoc 签名、无 Team ID。
- 两份都是 PR draft 候选包；runner launch smoke、包结构和签名检查不代表用户设备安装/升级、macOS Developer ID/公证或正式 Release。

## 6e542a2 当前 head 的 CI 与桌面候选回读（2026-10-17）

- PR CI run `39014042412` 对 head `6e542a2c4299fd7d1062dfb52e2dc2ffbad7748a` Windows/macOS 检查均 completed/success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39014042411` 的 Windows/macOS build、runner launch smoke、artifact upload 均 success。
- Windows artifact `12093927810`（20,535,518 bytes）Actions digest 与下载 ZIP SHA-256 一致：`019879e5bf75de5180596ee45318424d773a1da819dc3e1da4ee2ab58f832f2e`，外层 CRC 通过；EXE SHA-256 `3a8de9c029348323c28383cb374e39c77da8d34c507afdf02869dd7962826de9` 与 sidecar 一致。PE 为 x86-64 PE32+，Authenticode Security Directory 为 `(0, 0)`，未签名。
- macOS artifact `12094326845`（17,995,805 bytes）Actions digest 与下载 ZIP SHA-256 一致：`043ced6dd286ca087e6e7ac055450faabb444021c618d7997acfe195d7505608`，外层 CRC 通过；内层候选 ZIP SHA-256 `bf6197840149675483df331ddfb7ebf8acd1bf656c649294429839878fb5aa55` 与 sidecar 一致，CRC 通过。ditto 解包后 strict codesign 通过；app bundle 含 62 个 symlink，bundle `com.campusnettools.campusnetmanager` v5.6.0 arm64、adhoc、无 Team ID。
- 当前 Android run `39013104353`（head `32c9a9e`）仍在 API36 APK build step，job log 暂不可读；iOS run `39013866613`（head `3da21dc`）仍在 enrollment XCTest step，日志资源暂不可读。两者状态仍为 in_progress，只轮询原 run，不重启。
- 本次 Windows/macOS 包为 PR draft 候选与 runner smoke，不证明用户设备安装、Windows Authenticode、macOS Developer ID/公证、升级或正式 Release。

## e5158ce 当前 head 的 CI 与桌面候选回读（2026-10-17）

- PR CI run `39014217925` 对 head `e5158ce242d91895896480604dd04b5c35517af2` 的 Windows/macOS 全套检查均 success，Release job 因 PR 仍为 draft skipped。Desktop candidate run `39014217930` 两个平台的构建、runner 10 秒启动 smoke 与 artifact 上传均 success。
- Windows artifact `12094057852` Actions digest 与下载 ZIP SHA-256 一致：`bf4a1d36324177c824f7959a3e5e0cb05b6286c72202ad2a080afa8cea4e13df`，ZIP CRC 通过。EXE SHA-256 `2c8a3f64ca5d3e5166c0d56c6d6367063c266dbd83fe88ed9d5648152df416e3` 与 sidecar 一致；PE32+ GUI x86-64，Authenticode Security Directory 为 `(0, 0)`，未签名。
- macOS artifact `12093842212` Actions digest 与下载 ZIP SHA-256 一致：`cf9457c8036c1953be8da978caaa7fc652e96dd2aed99ca8d87dd3d4997252e6`，外层 ZIP CRC 通过。内层候选 ZIP SHA-256 `874bdf5f3a5c4811b3827510f025b4d85ebe934d7cf61d0d5dcefe50f7f2e03c` 与 sidecar 一致、CRC 通过，含 554 项和 62 个 symlink；`ditto` 解包后 strict codesign 通过，bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64、adhoc 签名、无 Team ID。
- 当时 Android run `39013104353` 处于 API 36 APK 编译、iOS run `39013866613` 处于 Simulator 安装/启动；job log 下载暂不可用。最终终态和 artifact 回读见下方 `8aff737` 小节。
- 本次桌面候选仍不证明用户设备安装、逐功能验收、Windows Authenticode、macOS Developer ID/公证、升级或正式 Release。为避免文档记录触发重复桌面打包，桌面候选 workflow 对纯 Markdown/docs 变更加 `paths-ignore`；PR CI 仍会运行。

## 8aff737 移动端模拟器与双平台候选验证（2026-10-17）

- PR CI run `39014451233` 对 head `8aff73741aa1e79caa9019edd62da455c1b2ecc6` 的 Windows/macOS 全套测试、静态、版本、页面和敏感值检查均 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39014451234` 两个平台构建、runner 10 秒启动 smoke 与 artifact upload 均 success。
- Windows artifact `12093754357` 外层 SHA-256 与 Actions digest 一致：`031788f06b59e75146b7dbdc92a57f6ced770f4b9f12cb097c3b90403c0124f1`，ZIP CRC 通过；EXE SHA-256 `26baf03598a4e63d553260232857a19f3a036a100965407b53dca4ffc5304396` 与 sidecar 一致，PE32+ GUI x86-64，Authenticode Security Directory 为 `(0, 0)`，未签名。
- macOS artifact `12094192956` 外层 SHA-256 与 Actions digest 一致：`b4fc0404ae01c82c2d8e7cd535ef5770116a427bb6c1f40076fe42606cb2edb2`，ZIP CRC 通过；内层候选 ZIP SHA-256 `4917757ae2da87362808e7626b0d76fc24a1ee18e46204fd55a87226575e48e8` 与 sidecar 一致，CRC 通过；ditto 解包 strict codesign 通过，bundle `com.campusnettools.campusnetmanager` v5.6.0，adhoc、无 Team ID。
- Android API36 run `39013104353`（head `32c9a9e`）所有 job steps success：APK 构建、合并 Manifest 前台服务声明 gate、KVM、模拟器安装/启动及两个 artifact 上传。APK artifact `12094193141` 的 Actions digest 与下载 ZIP SHA-256 均为 `95d144d27f30086eb10c8720544e83f450f321cfb518c28a1b2a9992d770b9cf`，CRC 通过；APK SHA-256 `e2ccedef3557945d487af409eabcaf8200c255faa3469e61e19216c5d7aac3c5`，ZIP CRC 通过，含 arm64-v8a、armeabi-v7a、x86_64 三 ABI。模拟器证据 artifact `12093809255` 的 digest/下载 SHA-256 一致，为 `7a9a877580b7028134ce5b9d685cb469e1710eb7f82a027928377947db5f3fea`，CRC 通过；logcat 有 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，未见 FATAL、ANR 或进程死亡标记；1080×2400 截图显示登录页和 HTTP 凭据风险提示，账号/密码为空。
- iOS Simulator run `39013866613`（head `3da21dc`）的 XcodeGen、IKEv2 enrollment XCTest、Simulator build/install/launch、保留 `.app` 目录结构的打包与上传步骤均 success。artifact `12093918720` 的 Actions digest 与下载 SHA-256 一致：`2ce2b111fc1a038d508ea5adbe1f86f7ea08849b3721e9d59fb39ddaab3efd71`；外层和内层 ZIP CRC 均通过，内层 app ZIP SHA-256 `2b705554adb91cacc7d5b6130aff4d97127009febb6e0d6af4b15d218ac5fa29`。bundle `com.campusnettools.companion`，版本 `0.2.0 (3)`，平台 iPhoneSimulator，二进制 x86_64/arm64；主二进制为 adhoc/linker 签名，无 Team ID，整个 app bundle 未签名。
- 上述 Android/iOS 均为 runner 模拟器结果，Android 截图也显示未连校园认证服务器；不代表实体手机、真实校园网双向流量、签名分发、Play 或 App Store 验收。

## bacc98b 桌面候选变更探测门禁（2026-10-17）

- 为应对 PR 长期保持 open 时文档-only提交仍反复构建桌面包，在 paths-ignore 之外增加 `detect-candidate-changes` job：checkout PR head 的最后一个 commit，Markdown/docs-only 时跳过两个打包 job；workflow_dispatch 强制运行。局部 Git fixture 覆盖 docs、README、mobile 源码、手动派发四种分支；YAML 解析和 `git diff --check` 通过。
- bacc98b 的 detector job 与 Windows/macOS 桌面候选 job 全部 success，证明改动工作流的 commit 正常执行候选构建。PR CI run `39014815582` 两平台全部检查 success，release job 因 draft skipped。Desktop candidate run `39014815613` 两平台构建、runner smoke 与上传 success。
- Windows artifact `12093799835` 外层 SHA-256 与 Actions digest 一致：`515ada688b32e05bf5f55fda843e2bb1fc21ec6060ba5ecff493fee3d090244c`，CRC 通过；EXE SHA-256 `b62f21cf19abc5c455577d039116e289e6d92bf7e21226a4edfa60d4ba16b96f` 与 sidecar 一致，PE32+ GUI x86-64，Authenticode Security Directory 为 `(0, 0)`，未签名。macOS artifact `12094556435` 外层 SHA-256 与 digest 一致：`ec025794dd9506c2db7fc8d152ec5a20ee5a23bfcf745bd5822a1b9adcff29a7`，CRC 通过；内层候选 ZIP SHA-256 `e8e1457fd924933ebd523fe98c2411847f519a26086957cfc414fa5f4f10811b` 与 sidecar 一致、CRC 通过，ditto 解包 strict codesign 通过，bundle v5.6.0 adhoc、无 Team ID。
- bacc98b 是 workflow-only commit，detector 选择继续打包。随后文档-only提交 `fb34427c9e44d80c8143206fb4b61a40b330fbcc` 的 Desktop candidate run `39014969255` 中 detector success、两个平台打包 job skipped；同 head 的 PR CI run `39014969246` Windows/macOS检查 success，release job因 draft skipped。这验证文档-only同步不会重复打包，同时保留 PR CI。候选与 runner smoke不代表 Windows用户安装、Developer ID/公证、升级或正式Release。

## 927c142 iOS enrollment 大小边界修复与跨平台 CI（2026-10-17）

- enrollment JSON 文件导入此前先将整个文件读入内存，再进行字段校验。`IKEv2Enrollment.decode(_:)` 现在拒绝超过 64 KiB 的数据；FileImporter 通过 `FileHandle` 分块读取，超过上限即停止继续读取并显示明确错误。README 记录该限制。
- iOS Simulator run `39015990577` 对 head `927c142f1eb88013b02b5ebe42a8e8a57e7ac2c1` completed/success。XcodeGen、工程生成、enrollment XCTest、unsigned Simulator build、模拟器安装/启动和 artifact 上传均 success；8 项 XCTest 全部通过（0 failures），包括恰好 64 KiB 接受和超过上限拒绝。
- artifact `12095062191`（5,162,667 bytes）的 Actions digest 与外层 ZIP SHA-256 一致：`a0a78aedd68c57a759df29b135436cea2085c9cb66e82348eea9f80acad50742`；外层 ZIP CRC 通过。内层 `CampusNetCompanion-Simulator.app.zip` SHA-256 为 `3c94533bd5f0a9b24e2b6d616470ef3b298111e75e838dd8a05d42b39a74cf90`，CRC 通过并含完整 `.app` 目录。bundle id `com.campusnettools.companion`，版本 `0.2.0 (3)`，Simulator 二进制 x86_64/arm64，adhoc/linker 签名，无 Team ID。
- 同 head 的 PR CI run `39015993367` Windows/macOS 测试与静态检查均 success，发布 job 因 PR 为 draft skipped。Desktop candidate run `39015993366` 两平台构建、runner launch smoke 与 artifact 上传均 success；本节未回读这轮桌面 artifact 内容。
- Actions 证据仅覆盖自动测试和模拟器。iPhone 真机安装、VPN 授权、Keychain 生命周期、IKEv2 双向流量、签名分发及 App Store 仍待验；以上结果不代表真机或商店验收。

## 58d0e3d 文档证据提交检查终态（2026-10-17）

- PR CI run `39025924271` 对文档 head `58d0e3d7af9e26b76500d8ba6184df6f3c702aba` 的 Windows/macOS 测试、静态、版本、页面和敏感值检查均 completed/success；发布 job 因 PR 为 draft skipped。
- Desktop candidate run `39025924223` 的变更检测 success；提交只修改闭环 Markdown 文档，因此两个平台打包和 runner smoke jobs skipped。
- 本次结果不改变 `927c142` 的 iOS 功能与模拟器证据；PR #1 仍 open draft，真机、签名商店和正式桌面发布仍待验。


## f9c6d73 登录 HTTPS 保留与构建状态（2026-10-17）

**已核实**
- 提交 `f9c6d73147a62530b1edffa28c294610a26e19e2` 保留校园登录档案显式配置的 HTTPS，拒绝未知 scheme 和 URL userinfo，并阻止认证请求跟随 HTTPS→HTTP 降级跳转；裸主机和 HTTP 默认 Dr.COM 行为保持兼容。校园门户真实 HTTPS 兼容性仍待实网验证。
- 本地全套 unittest 538 passed/3 skipped；repo CI Ruff F/E9、compileall、版本检查、`git diff --check` 均通过。
- PR CI run `39033219351` Windows/macOS 测试、静态、版本、页面及敏感值检查 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39033219343` detector、Windows/macOS build、runner launch smoke 和 artifact upload success。
- Windows artifact `12100139992` 的 Actions digest 为 `33642a5a62cbec37e4e3b9686979f9f80ce8cab831cbd069952c50bb2f5fcd07`；macOS artifact `12101361339` digest 为 `2fe072316b2285e3d056535484f3ac77105a250871a9116eade8138d209933b2`。本机读取下载 blob 时 `curl` 返回 `SSL_ERROR_SYSCALL`；没有取得 ZIP 包体，因此没有包内哈希、签名或内容回读证据。
- Android API36 APK run `39033215828` 环境准备步骤 1–10 success；最近轮询仍在 APK 构建步骤 11。Manifest/KVM/模拟器/产物上传步骤尚未开始，继续只轮询此 run，不重启。

**结论 / 边界**
- HTTPS 配置在代码路径中得到保留并禁止认证重定向降级；不推断学校认证网关支持 HTTPS。CI 和 runner smoke 不能替代终端用户设备、真实校园网络、签名商店或正式发布验收。

**待验证**
- Android 真机锁屏/切网/Keystore 与 signed Play；iPhone 真机签名、VPN/Keychain、IKEv2 双向流量与 App Store；Windows 用户设备安装逐功能；macOS Developer ID、公证、升级、逐功能和正式 Release 回读。

## d232b5d iOS Simulator enrollment run artifact 回读（2026-10-17 13:02 UTC）

- iOS Simulator run `39034330011`（head `d232b5d58a56a630579b4d02699bb6e9c7227d7e`）completed/success：XcodeGen、工程生成、IKEv2 enrollment XCTest、unsigned Simulator build、模拟器安装/启动、完整 `.app` 目录打包和 artifact 上传均 success。8 项 XCTest 全部通过（0 failures），覆盖配置 JSON 校验和 64 KiB 边界。
- artifact `12102031309` 大小 5,162,680 bytes，GitHub Actions digest 为 `9ed4202daf1c72b316d37377641bf8d87d8b74256b0f57a6a11cd83971b23adf`；本机经认证 API 下载回读后 SHA-256 相同，外层 ZIP CRC 通过。内层 `CampusNetCompanion-Simulator.app.zip` SHA-256 为 `06f279604f6820d9944170169e647eae9496a3b0f768a1cc8e1e51a0136d2718`，ZIP CRC 通过并保留 `CampusNetCompanion.app/` 目录结构。
- bundle id `com.campusnettools.companion`，版本 `0.2.0 (3)`，主二进制为 Simulator x86_64/arm64 universal Mach-O，adhoc/linker 签名、无 Team ID。运行记录仅证明 iOS 模拟器安装启动，不代表真机签名、Keychain/VPN 授权、IKEv2 双向流量、升级或 App Store 验收。
- Android API 36 APK 原 run `39033215828`（head `f9c6d73`）本次复核仍处于 API 36 debug APK 编译 step 11；前置步骤 1–10 success，Manifest、KVM、模拟器与 artifact steps pending。Actions 仍不提供该活跃 job 的日志；只轮询原 run，不重启。

## f9c6d73 Android API 36 APK 与 Emulator artifact 回读（2026-10-17 13:07 UTC）

- Android API36 APK run `39033215828`（head `f9c6d73147a62530b1edffa28c294610a26e19e2`）completed/success。debug APK 编译、合并 Manifest 前台服务校验、runner KVM 权限、API36 x86_64 模拟器安装/启动、APK 和运行证据 artifact 上传均 success。Manifest gate 检查 special-use 权限、`ServiceCampusguard`、`foregroundServiceType`、subtype 属性及 `0x400` 标志。
- APK artifact `12101487836`（67,968,574 bytes）Actions digest 与认证 API 下载 SHA-256 一致：`3a19aaccca4db9c748ff9baa3ba474c02c08bd657e467f7dd20e7e9ace3ce91e`；外层 ZIP CRC 通过。内含 debug APK `campusnetmanager-1.0.0-arm64-v8a_armeabi-v7a_x86_64-debug.apk`，SHA-256 `70b17ad2bd373fe30df52c584ac0d85de2d2e31bca43a74f6ee796c505d9a3b4`，APK ZIP CRC 通过，含 arm64-v8a、armeabi-v7a 和 x86_64 三种 ABI。
- Emulator evidence artifact `12101129184`（108,544 bytes）Actions digest 与认证 API 下载 SHA-256 一致：`b4e7ecbfcf30fa67096d5c2a9fc9668cdb7c784aa0baf0b4a29c89c5381e2e2e`；ZIP CRC 通过。logcat 出现 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，未检出 `FATAL EXCEPTION`、`ANR in` 或 app process death 标记。截图显示登录页和环境状态，已退出加载态，账号/密码为空；HTTP 默认地址旁显示凭据明文风险提示。模拟器未连接真实校园网。
- 该结果证明此 head 的 debug APK 构建、指定 API36 模拟器启动和首屏可见状态；不证明 Android 实体手机锁屏/切网/Keystore、校园网认证流量、signed AAB、Play Console 接收或商店发布。

## f9c6d73 Windows/macOS 桌面候选包回读（2026-10-17）

- Desktop candidate run `39033219343` 对 head `f9c6d73147a62530b1edffa28c294610a26e19e2` 的 detector、Windows/macOS 构建、runner launch smoke 和 artifact upload 均 success；PR CI run `39033219351` Windows/macOS 检查 success，publish job 因 draft skipped。
- Windows artifact `12100139992` 外层 Actions digest 与本机 API 下载 SHA-256 一致：`33642a5a62cbec37e4e3b9686979f9f80ce8cab831cbd069952c50bb2f5fcd07`，ZIP CRC 通过。内层 EXE SHA-256 `1bbed74f60f0b47f81aa982b28e1ba94d02c2cc82f75a18f59c7f72bcdc18dfb` 与 sidecar 一致；PE 为 GUI x86-64 PE32+，Authenticode Security Directory `(0, 0)`，未签名。
- macOS artifact `12101361339` 外层 Actions digest 与本机 API 下载 SHA-256 一致：`2fe072316b2285e3d056535484f3ac77105a250871a9116eade8138d209933b2`，ZIP CRC 通过。内层候选 ZIP SHA-256 `777d66d51c5d2bee43db9b5d41be23a34b605fb45209a2afcff81563bf5e8de1` 与 sidecar 一致，CRC 通过；`ditto` 解包后包含 62 个 symlink，strict codesign 验证通过。bundle `com.campusnettools.campusnetmanager` v5.6.0，arm64，adhoc 签名、无 Team ID。
- 两者均为 OPEN draft PR 的候选包和 CI runner smoke；不证明 Windows 用户设备安装/签名、macOS Developer ID/公证/升级，也不是正式 Release。

## macOS v5.6.0 安装版主窗口只读目视检查（2026-10-17）

- 通过本机桌面控制读取已安装 app 的主窗口：窗口标题显示 v5.6.0，主界面、档案表单和功能导航均已绘制；界面当前显示守护已运行。
- 本次只观察窗口和截图，没有点击登录、检测、更新、隧道、路由器或守护控件，也未保存包含档案信息的截图。macOS 原生可访问树只暴露窗口和菜单，未暴露主界面的各个 Tk 控件，因此这不是控件逐项操作验收。
- 该结果补充已安装进程/版本的目视证据，不证明表单值正确、校园网认证或流量有效，也不证明升级、Developer ID/公证、用户 Windows 安装或正式 Release。

## 23c57fe 主窗口目视记录 CI 终态（2026-10-17）

- PR CI run `39036271674` 对 `23c57fef94f4ea6e83287cf6c9a48db61b448f33` 的 Windows/macOS 全套测试、静态检查、版本、页面和敏感值检查均 success；发布 job 因 PR #1 为 OPEN draft skipped。
- Desktop candidate run `39036271681` 检测步骤 success；提交只涉及闭环 Markdown 记录，Windows/macOS 构建和 runner smoke jobs skipped。
- 该终态仅验证文档提交的 CI 状态；不扩展前述本机 v5.6.0 主窗口目视检查的证据范围。

## 3da4e8f Android 模拟器与桌面候选验证（2026-10-17）

- PR CI run `39036789695` 对 head `3da4e8f5e6175933c69a2cab819d62c01c04d0e6` 的 Windows/macOS 测试与静态检查均 success；Release job 因 PR #1 仍为 OPEN draft skipped。Desktop candidate run `39036789701` 的 Windows/macOS build、runner launch smoke 和 artifact upload 均 success。
- Windows artifact `12102407484` 外层 SHA-256 与 Actions digest 一致：`1167f24beab9c2610805ab084271a323b133ba31da16e7b2553dd69477c56877`，ZIP CRC 通过；内层 EXE SHA-256 `167018fc3df5300dec0ecf0aaf00ffccc03998ede6be6783f25b73b384e586d0` 与 sidecar 一致，PE32+ GUI x86-64，Authenticode Security Directory `(0, 0)`，未签名。
- macOS artifact `12102945195` 外层 SHA-256 与 Actions digest 一致：`d5f98db02595e1567a9352c03a4bd60bb4abc55aa353be22f2d483d08639dbc0`，ZIP CRC 通过；内层候选 ZIP SHA-256 `19a23ca174b0d18c6836c6b5050cd33615ea0e00e767dc0c9c292e3b6894c108` 与 sidecar 一致，CRC 通过且保留 62 个 symlink。`ditto` 解包后的 strict codesign 通过，bundle `com.campusnettools.campusnetmanager` v5.6.0、arm64、adhoc、无 Team ID。
- Android API 36 run `39036786196` 的 APK 编译、合并 Manifest 前台服务声明 gate、KVM 权限、模拟器安装/启动及两个 artifact 上传均 success。APK artifact `12103416570`（67,968,009 bytes）外层 digest/下载 SHA-256 一致：`95765de9e4d9e9cb80700ede3abf3de438f4a3d2089733aad01b4fe19f4a32aa`，CRC 通过；内含 APK `campusnetmanager-1.0.0-arm64-v8a_armeabi-v7a_x86_64-debug.apk`（68,210,411 bytes），SHA-256 `ae0816a44abefb613f7ec71e6e263b92f9a4cf2698faf80a0691f1fa969f72b7`，APK CRC 通过并含 arm64-v8a、armeabi-v7a、x86_64 三个 ABI。
- 模拟器证据 artifact `12102928334`（108,165 bytes）外层 digest/下载 SHA-256 一致：`528e5b0daaa12f951325a490663d852a6da6b01f2ef49606bc5ff1ea21db85d2`，CRC 通过。logcat 输出 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，未检出 `FATAL EXCEPTION`、`ANR in` 或应用进程死亡标记；截图显示已退出加载态的登录页、HTTP 凭据风险提示和空账号/密码字段。logcat 还记录 Kivy logo 目录复制因权限被拒绝、HIDAPI receiver 未指定导出标志以及 `Unknown <android> provider`；随后主循环和网络状态更新均继续。它们在本次首屏 smoke 中未阻断启动，但相关图标目录和 HID/外设能力尚未单独验收，不能记作已修复。
- 以上均是 PR 候选、runner smoke 和 API 36 模拟器证据；不证明实体 Android 设备锁屏/切网/Keystore、校园网认证流量、signed Play、用户 Windows 安装、macOS Developer ID/公证/升级或正式 Release。

## ea843cf 文档证据提交检查终态（2026-10-17）

- PR CI run `39038840087` 对 `ea843cf71ed25664154ca42e2bf6dfa8569d8d4f` 的 Windows/macOS 测试、静态、版本、路由器页面和敏感值检查均 success；Release job 因 PR #1 仍为 OPEN draft skipped。
- Desktop candidate run `39038840089` 的变更检测 success；该提交只更新闭环 Markdown 文档，因此 Windows/macOS 打包和 runner smoke jobs skipped。
- 此 CI 终态仅确认文档提交检查通过，不扩展 `3da4e8f` 模拟器和候选包证据的范围，也不构成真实设备、商店或正式 Release 验收。

## Android 档案持久化失败时阻止启动后台保活（2026-10-17）

- 源码检查发现 `mobile/main.py` 的 `_save_profile()` 只记录异常、不返回成功状态；Android 开启前台保活时即使 Keystore 加密/档案持久化失败，仍继续请求通知权限并启动服务。若应用目录已有旧档案，服务可能继续读取旧凭据。
- `_save_profile()` 现明确返回布尔结果；Android 启动保活前要求本次档案写入成功，否则显示“档案保存失败，后台保活未开启”并立即退出，不调用服务启动流程。桌面手动登录/现有前台守护路径保持当前行为。
- 新增 `tests/test_mobile_guard_save_gate.py` 两项源码门禁，检查保存失败分支先于通知权限/服务启动返回，以及保存成功/失败均返回明确结果。新专项 2 项与线程安全专项 1 项通过；全套 unittest `540 passed, 3 skipped`；`py_compile` 与 `git diff --check` 通过。当前机器未安装 Ruff，F/E9 规则须由后续 PR CI 确认。
- 这是源码与本机自动测试证据；尚未证明 Android Keystore 故障注入、实体手机上的旧档案隔离，或 Play 审核结果。

## 1b56c24 候选包回读文档检查终态（2026-10-17）

- PR CI run `39035668964` 对 head `1b56c24ca91a62e3a9e72a4db44df25e7a7d2b5c` 的 Windows/macOS 全套测试、静态、版本、路由器工作台页面和敏感值检查均 success；发布 job 因 PR #1 仍为 OPEN draft skipped。
- Desktop candidate run `39035668921` detector success；本次只改闭环 Markdown 文档，Windows/macOS 打包和 runner smoke jobs 按检测规则 skipped。
- 上述 checks 验证文档提交未破坏 CI；不改变 `f9c6d73` 候选包与 runner smoke 的证据范围，也不构成用户设备安装或正式发布验证。

## Android Kivy writable-home 修复候选（2026-10-17）

- 前一 API36 模拟器 logcat 报告 Kivy 2.3.1 在 p4a 解包源码目录 `ANDROID_APP_PATH/.kivy/icon` 复制图标时 permission denied。Kivy 2.3.1 初始化源码确认：未设置 `KIVY_HOME` 时 Android 默认将 `ANDROID_APP_PATH` 当 home 并在其下创建 `.kivy`；该路径与本次 logcat 中的不可写目标一致。
- `mobile/main.py` 现在在首次导入 Kivy 前，如果 Android 提供 `ANDROID_APP_PATH` 且未由部署环境显式设置 `KIVY_HOME`，将 Kivy home 设为其父级 app-private `files/.kivy`；桌面环境和用户/打包器预设的 `KIVY_HOME` 不变。参考 [Kivy 2.3.1 初始化源码](https://raw.githubusercontent.com/kivy/kivy/2.3.1/kivy/__init__.py)。
- 新增 `tests/test_mobile_kivy_home.py` 4 项回归；专项 4 项通过，全套 unittest `544 passed, 3 skipped`；Ruff F/E9、版本一致性、路由器页面检查、敏感值扫描、Android emulator smoke bash 语法和 `git diff --check` 通过。本地 standalone pyflakes 命令仍输出项目 star-import 架构的既有诊断，须以 CI 中过滤后的未定义名 gate 为准。
- 以上仅证明源码逻辑与本机测试。尚未通过新的 APK/API36 模拟器 logcat 证明 permission denied 消失，不能视为 Android 运行期修复验收；HIDAPI receiver 错误与 `<android>` provider 警告仍未定位，也不能归因于 Kivy home 路径。

## 6cb2e62 Android API 36 Kivy home 复核（2026-10-17）

- Android APK run `39039536750` 对 head `6cb2e627b4bbaedd9a1090c78bb1f36d2da5b23a` completed/success：APK 编译、special-use Manifest gate、KVM、API36 模拟器安装/启动及 APK/运行证据上传均通过。
- APK artifact `12104281708` 的 Actions digest 为 `77fdd751fcce92f3f26cb8557abf7c8a6be9fb8c5323cbdbdffee76d757789ab`；下载 APK SHA-256 `dd3d4ccbc87227bc1e1442dc6e7ca1a4ee66bd463686aef4348f30da35fe816c`，ZIP CRC 通过。Emulator evidence artifact `12104406070` 的 digest 为 `7fd3643834b381bb4568e1562974f0660a77e98c89c28c84a422f444b14ab1d2`；解包后 logcat SHA-256 `80b0fb8374610c6034bbf23418791fb9ddfa93e123a661d82b61a310014de8cb`，截图 SHA-256 `3c5a4582fe36c7f2a3c125ea821daad0466f86db251276559e47a59f39dbb8b8`。
- 截图显示 Android 登录表单及 `非校园网环境（认证服务器不可达）`，没有停留在加载页，账号/密码为空；logcat 有 ready marker，未见 `FATAL EXCEPTION`、ANR 或 app 进程死亡标记。该结果是 runner API36 模拟器 smoke，不代表真实校园网或实体手机验收。
- 重要反证：logcat 目标路径已从 `files/app/.kivy/icon` 变为 `files/.kivy/icon`，但 Kivy 2.3.1 仍对目标图标文件报 `Permission denied`。因此仅移动 `KIVY_HOME` 不足以消除 warning；同一 logcat 仍有 HIDAPI receiver flag 异常和 `Unknown <android> provider` warning，根因尚未确证。
- 后续源码候选现于首次导入 Kivy 前预建默认 Kivy home 下的可选空 `icon` 目录，让 Kivy 跳过非必需的 logo copytree；保留用户显式 `KIVY_HOME`。Windows 回归测试改为显式用 `posixpath` 模拟 Android 路径。当前本机 5 项专项测试、Ruff F/E9、`py_compile` 和 diff check 通过；这些新改动等待新 Actions/API36 模拟器验证。

## ffc69a0 Android Kivy icon 目录预建复验（2026-10-17）

- Android API 36 debug APK run `39042050230` 对 head `ffc69a0955d26dc8bab7e21de20c0b58097180f0` completed/success；API 36 APK 编译、前台服务 Manifest gate、runner KVM 权限、模拟器安装/启动、APK 上传和模拟器证据上传步骤均 success。
- APK artifact `12104024211` 的 Actions digest 为 `4422e9b55ac88ad576b074ebfe839659f88c71897115ea835c13856022fa9f7d`；本机下载 ZIP SHA-256 一致且 CRC 通过。APK SHA-256 `efdc98de8055a12a96acd8e57de0955d53c4a5458a4e0eae81befa034ebcf3d8`，APK ZIP CRC 通过，含 `AndroidManifest.xml` 与 arm64-v8a、armeabi-v7a、x86_64 三个 ABI。
- 模拟器证据 artifact `12103854645` 的 Actions digest、本机下载 SHA-256 一致：`013763b8d08843a8ec6e66e8f0da547b09a9c7a1d8bf2e3e2c272d3dd2e1992a`，ZIP CRC 通过。解包 logcat SHA-256 `efb6a2d37749241d554b5f31e38ac9e643a61bd639badf8f2d99c638eada215d`；截图 SHA-256 `1902a615fe658e99d0532343d9e2305db4ce6459685839ddbe02ded88f2a633d`。logcat 有 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，未发现 `FATAL EXCEPTION`、`ANR in` 或应用进程死亡记录。截图显示登录表单和状态提示已渲染、非加载态、账号与密码为空。
- 复验 logcat 不再出现前次 `Error when copying logo directory` / `Permission denied`，支持“首次导入 Kivy 前预建默认空 icon 目录”消除该可选图标复制警告的 Android API 36 模拟器证据。该结论只限本次 runner 镜像和启动路径，不代表所有设备/环境均无权限问题。
- 同一 logcat 仍记录 HIDAPI 动态广播接收器未指定 `RECEIVER_EXPORTED`/`RECEIVER_NOT_EXPORTED` 的异常，以及 `Unknown <android> provider` warning；两者根因及 HID/USB 功能均未验证。模拟器 smoke 不证明实体手机、Keystore、锁屏/切网后台能力、校园网络流量或 Play 接收与上架。
- PR CI run `39042053877` Windows/macOS 检查 success、发布因 draft skipped；Desktop candidate run `39042053873` 两平台构建、runner launch smoke 和 artifact upload success。该桌面候选状态不扩展本节 Android 运行证据范围。

## 用户修订直下载目标与 2026-10-17 本机验收（后续范围见 2026-10-18 补充）

- 用户明确不要求 App Store / Play 商店上架；分发目标为用户可直接下载并安装使用。公开最新 GitHub Release 当时为 v5.5.0，含 macOS 与 Windows 资产；未见公开 Android/iOS 安装包。PR #1 当时 OPEN draft，HEAD `4f4e16ac942a4cc16c8d13a734e260767b756e7a`。
- 本机 `python3 -m unittest discover -s tests -v`：545 passed、3 skipped。裸命令 `python3 -m unittest discover -v` 未递归 `tests/`，报告 0 tests，不能作为测试结果。
- `/Applications/校园网连接管家.app` 目视标题为 v5.6.0；bundle id `com.campusnettools.campusnetmanager`，本机进程在运行；`codesign --verify --deep --strict` 通过。这是本机 bundle 完整性和运行证据，不是 Developer ID / 公证或其他用户安装验收。
- 已检查主窗口和一个只读路由器中继说明窗口，后者已关闭；没有操作校园网登录、检测、守护、VPN、热点、路由器设置或任何会传输凭据/改变网络的控件。主界面的 Kivy 控件没有出现在 macOS 辅助功能树中，因此没有完成逐控件验收。
- 当前 Mac 未安装 `adb`，仅有 Command Line Tools、没有完整 Xcode 的 `simctl`。iPhone 镜像当时显示影序手机协作台，未切换或操作该手机；不能据此宣称校园助手已在 iPhone 真机验收。
- 当时对是否允许系统安装必需的免费本地/开发签名尚未确认；此状态由 2026-10-18 的用户补充取代。不索取密码、验证码或私钥。
- 当时记录的待办由下方 2026-10-18 最新范围与状态摘要更新。任何模拟器、Actions runner、候选包或应用自己的在线日志都不能替代实体设备验收。

## 2026-10-18 用户补充：免费签名可用，以可运行优先

- 用户确认：只要最终用户能使用且不产生费用即可；“保证运行”优先。允许 Android/iOS/macOS 为安装运行所需的免费平台本地/开发签名；仍不做 Play/App Store 上架，也不购买付费开发者身份或签名证书。
- Android 免费 debug 包签名可用于 sideload，但系统仍可能要求用户允许安装来源；必须用实际 APK 和实体手机验证。
- Windows 当前候选 EXE 无 Authenticode 签名；macOS 候选仅 adhoc 签名。用户可被引导手动确认来源/绕过首次运行警告，但无法承诺和付费可信签名相同的无警告体验。当前 Mac 唯一 codesign identity 为其他产品 `Smart Media Backup Developer`，不可用于本产品。
- Apple 官方说明：免费 Personal Team 可经 Xcode 为有限个人设备签名测试，最多 3 台设备，provisioning profile 7 天过期，需定期重新签名安装；这不是面向所有 iPhone 用户的免续签公开直下载渠道。[Apple Developer account overview](https://developer.apple.com/help/account/basics/about-your-developer-account) 与 [Apple distribution overview](https://developer.apple.com/documentation/technologyoverviews/distribution) 。当前 Mac 没有完整 Xcode/`simctl` 和本项目 profile。为准备 Android 真机连接，本轮用 Homebrew 免费安装 Android Platform Tools 37.0.1；`adb` 在最小环境中调用后无输出并以 exit -9 结束，原因未知，且没有检测到 USB 手机。iPhone 镜像此前正在运行影序应用，因此 iPhone 真机操作必须等设备可用，且 Apple 账号由用户在本机自行登录，不向 Codex 提供凭据。
- 最新公开 Release 是 v5.5.0；v5.6.0 仍是 PR draft 候选。Android API 36 模拟器包、桌面候选包均未发布成当前公开下载资产；iOS 仍只有 Simulator `.app` 包，不能安装到 iPhone。下一步是在设备/工具可用时完成真机验收；发布直下载包之前必须逐一说明其平台签名级别和安装警告。
- 验收工具现况：`adb` 不存在；`xcode-select -p` 为 `/Library/Developer/CommandLineTools`；Codex Computer Use 报 runtime app missing。shell 只能确认已安装 macOS app 进程、窗口标题、版本、bundle id 和 strict adhoc 签名，不等同于 UI 控件逐项验收。

## f8230eb 直下载范围文档提交 CI 终态

- PR CI run `39046430189` 对提交 `f8230ebf52b9d21ca46833a57b04ebf673e4c290` 的 Windows/macOS 测试与版本检查均 success；release jobs 因 PR #1 仍为 OPEN draft skipped。
- Desktop candidate run `39046430201` 变更检测 success；该提交仅更新闭环文档，Windows/macOS build 与 runner launch smoke jobs skipped。
- 这些检查只验证该文档提交的 CI 状态，不扩大本机 GUI 操作、真实手机/Windows 设备或当前公开下载包的验收证据。


## 2026-10-18 工具与本机验收状态刷新

- 本机全套 unittest `545 passed, 3 skipped`；提交 `964b88b` 的 PR CI run `39048160885` Windows/macOS 全套测试、ruff、版本、路由器页面和敏感值检查均 success；Desktop candidate run `39048161051` detector success，docs-only 构建/runner smoke 按规则 skipped。
- `/Applications/校园网连接管家.app` 正在运行，System Events 可读到单一窗口标题 `校园网连接管家 v5.6.0`；bundle `com.campusnettools.campusnetmanager`，strict adhoc codesign 验证通过。窗口当前非前台，Computer Use runtime app missing；因此本轮没有完成主界面逐控件操作。
- 免费安装 Android Platform Tools 37.0.1；其 `adb` 二进制 codesign 验证通过，但最小环境调用 `adb version` 无 stdout/stderr 且子进程 exit -9，原因未知；未识别 USB Android/iOS 设备。当前只具有此前 runner API36 emulator 的启动证据。
- 本轮未执行登录、隧道、守护、路由器、热点或网络设置操作。下一步实体设备需可用并连接；iPhone 需完整 Xcode 和用户自行完成的免费 Personal Team 设置。

## 2026-10-18 Android 免费直下载发布链与版本同步

- 用户确认的分发边界：不做 Play/App Store 上架、不购买付费签名或开发者身份；免费平台签名可以使用，优先保证普通用户能下载并安装运行。
- 修复 Android 版本漂移：`mobile/buildozer.spec` 从旧 `1.0.0` 同步到 `APP_VERSION=5.6.0`；`scripts/sync_version.py --check` 现在同时校验 Android spec 与 README 的候选 badge，并新增 7 个版本同步回归。提交 `56457937f32dc8001a5449a1581cf22914913fec` 已推送，PR CI `39048995767` 和桌面候选 detector/build `39048995811` success；Android API 36 APK run `39048992242` 后续已完成 APK 编译、Manifest、KVM、模拟器安装/启动及 artifact 上传，成功只适用于该旧提交，不证明其后加入的 stable signing gate。
- 为未来 `v*` GitHub Release 增加 Android reusable workflow：依赖双平台 CI 与桌面 Release job；执行当前 API 36 APK 构建、Manifest/版本检查、模拟器网络状态就绪/截图 smoke，之后发布 APK 与 SHA-256 校验文件。PR/普通手动候选仍只上传 Actions artifact，不会创建公开 Release；手动 workflow_dispatch 可显式开启同一稳定签名以验候选安装/更新；该链不接入应用商店。
- 已在本机生成免费项目 APK 签名证书和 PKCS#12 keystore，往返解码校验通过；Actions repository secrets `ANDROID_KEYSTORE_BASE64`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD` 已配置，私钥/口令仅交给 GitHub Secrets，没有写入工作树。标签发布步骤会用同一证书重签 APK 并用 `apksigner verify` 检查，从而支持同签名覆盖更新；PR 候选 APK 继续使用临时 runner debug 签名。当前证书 SHA-256 公钥指纹：`a6a3451d09b6ec3b34f12ee07193233b812a04acd2ba711ab56dd466bb6aa613`。
- 新发布链目前只有源码与本地静态回归证据（18 项 Android 专项测试通过、ci/mobile YAML 可解析、diff check 通过）；还需 CI 实际运行 tag/reusable workflow 与 `apksigner` gate，并在 Android 实体设备验证安装、覆盖升级、锁屏/切网和 Keystore。此处不代表任何 Release 已发布或设备验收完成。

## 2026-10-18 Android APK 校验误报修复

- Android APK runs `39049513521`、`39049528799`、`39049629732`、`39049713532` 均完成 API 36 debug APK 编译，但在字体文件清单校验处失败。`39049713532` 的日志确认 tar 清单实际含 `assets/NotoSansSC.ttf`；`set -o pipefail` 下 `tar -tf archive | grep -q` 会因 grep 提前关闭管道而使 tar 报 stdout write error，导致误报字体缺失，不能据此判定 APK 内容有问题。
- 修复将 tar 清单先写入临时文件，再从普通文件 grep；新增回归断言避免恢复会触发 SIGPIPE 的管道写法。Android 专项 11 项通过，全套 unittest 553 passed/3 skipped，两个 workflow YAML 可解析；合成归档的修复后清单检查和 `git diff --check` 通过。
- 修复提交 `c45b970c39b18f36a3aac6e4e64c9869e388b5f7` 已推送。Android run `39087643194` 截至本次记录仍在 API 36 APK 编译步骤，字体/Manifest gate、稳定签名指纹、模拟器安装/运行/日志和 APK artifact 回读待后续轮询；同 head PR CI `39087646271` 与 Desktop candidate `39087646286` 已 success。公开 GitHub Release 仍为 `v5.5.0`；v5.6.0 还没有公开下载资产。

## 2026-10-18 macOS v5.6.0 安装版界面验收

- `/Applications/校园网连接管家.app` 窗口显示 v5.6.0；主界面检测结果显示守护仍运行、当前网络在线。通过新手向导进入“方式 B：路由器中继”并选择校园网后，向导只读识别为未知品牌，给出网关 `192.168.31.1` 与通用中继步骤。未打开管理地址、修改连接档案或网络配置，也未启停守护、代理或热点。
- 在应用中手动检查更新，界面返回“当前版本 v5.6.0 高于最新公开版 v5.5.0（可能是预览版本）”。现场 `gh release view` 也确认 latest 为 `v5.5.0`；因此当前安装的是尚未公开发布的候选源码版本，GitHub 仍没有 v5.6.0 下载包。
- 这些是本机 macOS 安装版的有限 GUI 和当前网络状态证据；不能推广到其他电脑、Windows、真实路由器型号、设备逐项功能或升级安装。Computer Use 运行时连续不可用时，改用本机截图和鼠标事件完成上述低风险操作；截图不提交、不上传，避免包含本地连接档案内容。

## c45b970 桌面候选包下载回读

- Desktop candidate run `39087646286` 对提交 `c45b970c39b18f36a3aac6e4e64c9869e388b5f7` 完成 Windows/macOS build、runner launch smoke 与 artifact 上传。Actions artifact digest：macOS `b9e5cb91a07a050ca580854c4fde360bc1e307174130b62aae364d137baa7582`，Windows `2e0f2bc18f807dd1e6a6754505c5bf877915816856e8801c15d64d34743f4430`。
- 下载后的 macOS 候选 ZIP SHA-256 与 sidecar 一致：`ae5c2bf57bf5e5794446d5a3b9d6c77cf594a2e8a0a10aee4a640242161dc565`；ZIP CRC 通过。`ditto` 解包保留 62 个 symlink，`CampusNetManager.app` strict codesign 验证通过，bundle `com.campusnettools.campusnetmanager`、版本 `5.6.0`、arm64、adhoc、无 Team ID。
- Windows EXE SHA-256 与 sidecar 一致：`8f4d016a2c78ec4c7a9752a47e4a01909ef077d807900e1db89632fd01233cd0`；PE32+ GUI x86-64，Authenticode security directory offset/size 均为 0，未签名。
- 这是 CI runner smoke 和 PR 候选 artifact 回读，不是 Windows 用户设备安装/运行证据、macOS 候选 artifact 本身安装运行证据、升级验收或公开 Release。macOS 本机运行证据来自已安装的 v5.6.0 应用，不能与此次下载的候选包混为一谈。

## cd322b0 CI 端口冲突回归

- 文档提交 `cd322b095f4928439d25305a885194c76d9fb606` 的 PR CI run `39087973787` 中 Windows 全套测试成功，macOS 全套测试有 2 项在 `SharedProxy.start()` 绑定端口时 `OSError: [Errno 48] Address already in use`。两项都先探测临时端口、关闭套接字，再启动服务器，留下并行测试可抢占的时间窗；不是新文档引入的内容错误。
- 已将 `tests/test_tunnel_default_no_key.py` 两组代理测试改为直接 bind port 0，再读取服务实际分配端口。目标测试连续 5 轮（每轮 10 项）通过；本地全套 unittest 553 passed/3 skipped。后续提交的 PR CI 仍需验证 macOS runner 修复。

## e38b71e 桌面候选回读、Android debug 验收及免费签名候选

- `e38b71e4c4a8563e4be3b6cb62e8441449d7b051` 的 PR CI run `39088234772` Windows/macOS 全套测试、静态检查、版本和页面检查 success；发布 job 因 PR 为 draft skipped。Desktop candidate run `39088234779` 两平台 build、runner launch smoke 和 artifact upload success。
- Windows artifact `12122085599` Actions digest 为 `73ce78f26c18661c91a3602f6f0cdabe1e8f6204cb023b92f9c1a102726244d9`；下载 EXE SHA-256 `782246c4ba5c22143a01e06134239ac7fc82e0f82f0f8fee952473617a296445` 与 sidecar 相符，类型为 PE32+ GUI x86-64，未签 Authenticode。macOS artifact `12120659867` Actions digest 为 `401df44f8bc4a10b2e26ab3828bfe7f743c427fb08a7efd9c0deac28b53b713e`；候选 ZIP SHA-256 `92d4cf2ca7915fbd132e13df518482f40b6eed515a19a116c54f16c8a9cfa4fc` 与 sidecar 相符，ZIP CRC 通过；ditto 解包后 strict codesign 通过，62 个 symlink，bundle `com.campusnettools.campusnetmanager` v5.6.0 arm64，adhoc、无 Team ID。两包仍是 PR 候选和 runner smoke，不是 Windows 用户设备安装或公开下载 Release。
- Android run `39087643194`（head `c45b970c39b18f36a3aac6e4e64c9869e388b5f7`）completed/success：API 36 debug APK、前台服务 Manifest gate、KVM、模拟器安装/启动与两份 artifact 上传全部 success。普通 push 触发未请求稳定密钥签名，签名步骤 skipped；Release 上传也 skipped。APK SHA-256 `fd178af3a66c7d6dcc462fb85b7c3aaaa250ba0e087db07aca638893b7ce4033`；下载包 CRC 通过，包含 arm64-v8a、armeabi-v7a、x86_64。模拟器 logcat 有 `CNM_NETWORK_STATUS_READY: 非校园网环境（认证服务器不可达）`，未见 FATAL/ANR/进程死亡；截图显示登录界面且账号、密码为空。这是 debug APK/runner 模拟器证据，不是真机或 Release。
- 按用户“免费且能运行”的标准，以 `workflow_dispatch` 在最新源代码 head `e38b71e` 开启免费稳定项目签名候选 run `39088722413`（`sign_for_direct_download=true`）；本记录时仍在 APK build 阶段，后续只轮询该 run，核对免费证书验签、模拟器安装/启动和 artifact 回读，不重启。该候选不创建 GitHub Release或商店提交。
- 本机 Homebrew 的 Android Platform Tools 37.0.1 安装记录存在但 `adb` 文件缺失；从 Google 官方同版本 ZIP 提取 `platform-tools/adb` 修复。ZIP SHA-256 `ee39ad5967e95c2a07f04dbcbde96b1a0c916ba376096db5d2f498b7727a5d1d` 与 Homebrew cask 预期值一致；ADB 1.0.41 / platform-tools 37.0.1 可运行，但 `adb devices -l` 无已连接设备。当前 Mac 只有 Command Line Tools，`simctl` 不可用；Android/iPhone/Windows 实体设备验收仍待设备接入和对应操作系统工具。目标仍是免费直下载/安装运行，不做商店上架或付费签名。

## Android 免费签名候选的校验器误报修复

- 手动签名 run `39088722413`（head `e38b71e4c4a8563e4be3b6cb62e8441449d7b051`）成功构建 API 36 APK、Manifest gate 通过；项目 PKCS#12 密钥签名成功，`apksigner verify` 报告 v2/v3 有效，证书 SHA-256 指纹也与项目免费直下载证书匹配（`a6a3451d09b6ec3b34f12ee07193233b812a04acd2ba711ab56dd466bb6aa613`）。失败点是 workflow grep 固定期待旧版 `Signer #1 certificate SHA-256 digest:` 标签；当前 Build Tools 输出 `V3.0 Signer: certificate SHA-256 digest:`，导致正确签名被误判。失败发生在签名 gate 后、APK/模拟器 artifact 上传前，因此该 run 没有产出包体 artifact，模拟器步骤 skipped。
- `.github/workflows/mobile.yml` 改为仅比较 `apksigner` 已验证证书输出中的固定指纹，不依赖标签措辞；受信任的 `codex/full-project-closure` push 也执行同一免费稳定签名步骤。这样 push 生成的 APK 候选可直接用于覆盖更新，仍只上传 Actions artifact；GitHub Release 资产仍仅在 `v*` 标签创建，不做商店上架。
- `tests/test_p4a_special_use_patch.py` 增加 push 触发签名和格式无关指纹校验的回归断言。修复后的专项测试及下一条 push Actions run 待验证；必须检查签名摘要、模拟器安装/启动和 APK artifact，不能把源代码修复视作验证完成。

## 2026-10-18 iPhone USB 配对、IKEv2 网关与待安装配置

- 更正此前记录：iPhone 已通过 USB 在本机枚举，`idevicepair validate` 返回成功；`ideviceinfo` 可读取 ProductType `iPhone18,1`、iOS `26.6.2`。不记录设备 UDID。Android ADB 的设备列表与 iPhone USB 连接无关。
- 已通过本机管理员授权启动项目 strongSwan `charon`，服务进程仍在；同一授权会话中创建了该 iPhone 的 system IKEv2 `.mobileconfig`、CA profile 和 companion enrollment JSON。文件保存在权限受限的项目网关目录，未复制到仓库、公开网页或 GitHub。创建时 `swanctl` 已读到 `campusnet-ikev2` 配置；当时 IKE SA 数为 0，因此不能说手机已连 VPN。
- 普通账户读取网关私有 profile 目录与 VICI socket 被权限拒绝；本轮用非交互 `sudo -n` 复核状态因需管理员认证而未执行。当前未观察到 iPhone 上已安装该 profile、VPN 授权、IKE SA 或双向流量的证据。
- Mac 没有完整 Xcode、Apple Configurator 或 `cfgutil`；Computer Use runtime 返回 “app missing”，因此无法操作 Finder、App Store 或 iPhone Settings。Apple 官方说明 Configurator 可免费从 App Store 获取、可连接 USB 设备并提供 `cfgutil`；未监督设备添加 profile 时仍需按屏幕提示确认。已在 Mac 打开 Apple Configurator 的 App Store 页面，等待安装该免费工具后再尝试 USB 安装；不使用 Xcode 或 7 天个人签名方案。
- 本机 macOS 下载包 `/Users/nanyu/Desktop/CampusNetManager-macOS-arm64-v5.6.0.zip` 的 SHA-256 为 `ad7f66820d8f42ccf4e52ec4b5f796e0b5d1306cd86a6d4c0029f93df15bb60f`，sidecar 核验一致。此包仍是 adhoc、未公证的本机直下载包；用户首次打开可能看到 macOS 安全提示，不能描述为 Developer ID/公证发布。
- 参考：Apple Configurator 免费与 USB/`cfgutil` 说明见 [Apple Platform Deployment](https://support.apple.com/guide/deployment/dep6f70f6647/1/web/1.0)；非监督设备安装 profile 操作见 [Add or remove configuration profiles](https://support.apple.com/guide/apple-configurator-mac/add-or-remove-configuration-profiles-cadb67fcd4f/mac)。

## 2026-10-18 Apple Configurator USB 安装请求状态

- 用户安装了 Apple Configurator 2.21。直接使用应用 bundle 内的 `cfgutil` 可运行，无需安装 Xcode 或额外的 CLI 链接。
- 重新确认 iPhone USB 配对成功，strongSwan `charon` 进程运行，Mac 当前地址仍与生成 profile 中的网关地址一致，UDP 500/4500 有监听。
- `cfgutil install-profile` 已向这台连接的 iPhone 提交受限目录中的 IKEv2 配置，但命令返回 `ConfigurationUtilityKit.error` code 625，含义为需要用户在设备上交互确认。因此**不能将其记录成 profile 已安装**；等待 iPhone 屏幕确认或用户在“设置 → 通用 → VPN 与设备管理”完成安装。未观察到 IKE SA 或双向流量证据。
- 安装请求输出含设备标识，已从共享记录中排除；输出文件权限为 root-only。profile 内容和 EAP 凭据从未写入仓库、共享记忆或公开位置。
- 提交 `82d22c0` 的 PR CI `39095498098` success；Desktop candidate `39095498093` success，因仅文档变更而跳过平台打包。PR #1 仍为 OPEN draft。
