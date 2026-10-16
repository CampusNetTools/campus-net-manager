# 校园网连接管家 · 手机版（Android）

手机直连校园网 WiFi 时的 Dr.COM 登录与前台保活工具，复用桌面端 `core/` 包的认证实现。

## 功能

- **一键登录**：填账号/密码/运营商/认证服务器（默认立达 `http://192.168.16.3/`），点「立即登录」
- **后台保活**：用户主动开启 Android sticky 前台服务，每 60 秒检测认证与外网；掉线后自动重登并复检
- **环境识别**：认证服务器不可达时显示「非校园网环境」，不误登录
- **档案保存**：Android 使用 Keystore AES-GCM 加密后的 `profile.enc`；旧版明文档案在迁移成功后删除。桌面开发回退仍写 `profile.json`
- **中文界面**：APK 随包包含 Noto Sans SC 与 SIL OFL 许可证，避免 Kivy 默认字体缺少中文字形

字体来自 Google Fonts `Noto Sans SC`，按 SIL Open Font License 1.1 原样分发；许可证位于 `assets/OFL-NotoSansSC.txt`，字体 SHA-256 为 `a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da`。

## 与桌面版的关系

| 能力 | 手机版 | 桌面版 |
|---|---|---|
| Dr.COM 登录/重登 | ✅ 同一套 core.auth | ✅ |
| 保活 | 用户启动的 Android 前台服务；通知权限与服务状态会在界面显示 | 后台守护线程 + 合盖保活 |
| 隧道共享/测速/路由器体检 | ❌ | ✅ |
| 远程查看状态 | — | Web 控制台（手机浏览器访问） |

## 构建 APK

当前配置目标 API 36，固定 python-for-android `v2026.05.09`、Python 3.11.8 和 Kivy 2.3.1；构建会在固定源码模板上补入 Android `specialUse` 前台服务所需的 subtype 说明。CI 对相关分支推送和手动触发均打包 debug APK，检查合并 Manifest，并在 API 36 x86_64 模拟器安装/启动应用、检查进程与 fatal log、上传 APK 和运行证据。

源码和单元测试仍不等于真实手机或后台运行验收。2026-10-16 早期 run `38851368170` 在 Kivy 2.3.0 的 `cgl_gl.c` 编译时因 Clang 函数指针 const 限定不兼容而失败；spec 已改 pin Kivy 2.3.1。随后 run `38852810567` 又在 p4a 临时 Python venv 执行 `pip install -U pip` 时失败，日志为 `ImportError: cannot import name 'open_rich_spinner'`。根因推断是缓存的 build venv 残留混杂 pip 文件，与 p4a 对同版本问题的记录一致；固定 p4a patch 已在创建 venv 时使用 `--clear`。Android run `38915018182`（head `7e10c11`）现成功完成 API 36 debug APK 构建、服务 Manifest 校验、KVM 权限、模拟器安装启动与进程存活检查。artifact `12053800638` 中 APK SHA-256 为 `0e81f30e2420ee1d199dd665030a79b9321d76e20efd9c3b46c1f120f758baae`；APK ZIP CRC 通过。emulator evidence artifact `12053406639` CRC 通过，日志无 `FATAL EXCEPTION`，截图显示 UI 已启动但中文字体缺失；该观察触发了本次字体打包修复。真实 Android 手机的锁屏、切网、Keystore 和校园网登录仍未验收。

APK run `38856748022`（head `cf794ed`）曾成功编译 APK，但合并 Manifest 缺少服务声明。日志中的 Buildozer 命令未带 `--service`，根因是配置键误写为 `android.services`；现已修正为 Buildozer 读取的 `[app] services` 并加入回归测试。修复后的 run `38879167090`（head `7934fb1`）成功构建 API 36 debug APK，`aapt` Manifest 校验通过：服务类 `ServiceCampusguard`、`foregroundServiceType=specialUse`、subtype property 与 `0x400` flag 均符合工作流检查。artifact `12037616953` 下载后 ZIP CRC 检查通过，含 arm64-v8a 与 armeabi-v7a；APK SHA-256 为 `0a49e56c35b734843ef2e0f3dcc2e0142afcd8252c44efab1aa637059f1822df`。该证据不代表手机安装、锁屏/切网运行、Play Console 接收或商店发布。unsigned AAB run `38856949123`（head `2c83f6b`）已完成 API 36 构建、剥除临时签名和 unsigned 校验并上传 artifact `12028181480`；ZIP CRC 检查通过、47 个条目、没有 JAR 签名文件，SHA-256 为 `45b5d9579a47bc3c6f81662f8f76044300f3e1383b0115ec54dabcb245d80dc9`。iOS run `38856309857`（head `a15e83d`）已成功完成 simulator 编译、安装、启动和 ZIP 打包；artifact `12027332700` 下载检查确认 ZIP 内含完整 `CampusNetCompanion.app/` 目录，bundle id `com.campusnettools.companion`、版本 `0.2.0 (3)`、Simulator 架构 `x86_64/arm64`、adhoc/linker 签名且无 Team ID。iOS 真机、IKEv2 连通和 App Store 发布仍未验收。
PR CI run `38879156449` 的 Windows job 因新回归测试按 Windows 默认 cp1252 解码 UTF-8 spec 而失败（`UnicodeDecodeError`）；测试现显式以 UTF-8 读取，再解析配置。修复后的 run `38879597002`（head `077a4c6`）macOS 与 Windows 测试和静态检查均通过。

Android run `38919046038`（head `f84145e`）构建、Manifest gate、KVM、API 36 模拟器安装/启动步骤和 artifact 上传均成功；PR CI `38919056780` 与桌面候选 `38919056811` 成功。回读 APK artifact `12055816564` 后发现 `assets/private.tar` 未包含 `assets/NotoSansSC.ttf`，所以此前字体改动没有进入 APK。模拟器证据 artifact `12055746790` 的截图停留在 Kivy `Loading...`，不能算界面显示验收。原因是 workflow 组装打包目录漏拷贝 `mobile/assets`。workflow 现复制该目录，并在 APK 校验中检查字体条目和 SHA-256；需要新 Android run 验证。该 run 的模拟器进程检查只证明进程存活，不证明主界面已绘制或真实手机行为。

本地构建（需 Linux 或 macOS + buildozer 环境；macOS 本机因同样上游问题暂无法出包，
建议用 Windows 的 WSL2/Linux 或 Docker 完成）：

```bash
mkdir -p build_mobile
cp mobile/main.py mobile/buildozer.spec build_mobile/
cp mobile/guard_service.py build_mobile/
cp -r mobile/services build_mobile/
cp -r mobile/assets build_mobile/
cp -r mobile/java build_mobile/
cp -r core build_mobile/
cd build_mobile
buildozer android debug   # 产物在 bin/*.apk
```

### 签名 AAB

手动运行 `.github/workflows/android-release-aab.yml` 可构建 API 36 AAB artifact；unsigned 模式用 runner 上的一次性临时密钥满足 Gradle release 构建，随后移除签名块并校验 bundle 未签名，因此不能上传 Play；signed 模式会验证真实上传密钥并产出可供 Play Console 上传的 bundle。此工作流不会自动发布到 Google Play。signed 模式需在 GitHub Actions secrets 配置 `ANDROID_KEYSTORE_BASE64`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD`。签名材料只保存在 GitHub 官方 secrets 与 Google Play Console，不写入仓库或聊天。`38854446189` 是无 jobs 的 push 事件，不构成构建验证。unsigned run `38854980739` 证实 Buildozer release 仍要求 keystore；新临时签名再剥离实现待构建验证。

## 已知限制

- **运行时状态**：Android 前台服务由用户在 App 内启动/停止，要求通知权限；系统省电策略、厂商后台限制和网络状态仍需真机验收。
- **凭据**：Android Keystore 实现已加入源码，但本机尚无 Android 构建工具链；最终 APK 中的加解密、升级迁移和密钥丢失恢复仍待验证。
- **发布状态**：API 36 unsigned debug APK run `38915018182` 已通过模拟器安装/启动检查并上传 artifact `12053800638`；它是 debug APK，不是 Play 可发布签名包。unsigned API 36 AAB run `38856949123` 已构建并通过 ZIP/未签名检查。二者均不代表真机验收或 Play 接收。signed 模式需要上述 keystore secrets；商店内测/生产发布和审核尚未完成。
- iOS 系统 IKEv2 客户端与 Mac 端 enrollment 路线见 `../ios/CampusNetCompanion/README.md`；App Store build、签名、设备验收和上架尚未完成。
