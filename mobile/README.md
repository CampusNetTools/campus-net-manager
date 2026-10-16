# 校园网连接管家 · 手机版（Android）

手机直连校园网 WiFi 时的 Dr.COM 登录与前台保活工具，复用桌面端 `core/` 包的认证实现。

## 功能

- **一键登录**：填账号/密码/运营商/认证服务器（默认立达 `http://192.168.16.3/`），点「立即登录」
- **后台保活**：用户主动开启 Android sticky 前台服务，每 60 秒检测认证与外网；掉线后自动重登并复检
- **环境识别**：认证服务器不可达时显示「非校园网环境」，不误登录
- **档案保存**：Android 使用 Keystore AES-GCM 加密后的 `profile.enc`；旧版明文档案在迁移成功后删除。桌面开发回退仍写 `profile.json`

## 与桌面版的关系

| 能力 | 手机版 | 桌面版 |
|---|---|---|
| Dr.COM 登录/重登 | ✅ 同一套 core.auth | ✅ |
| 保活 | 用户启动的 Android 前台服务；通知权限与服务状态会在界面显示 | 后台守护线程 + 合盖保活 |
| 隧道共享/测速/路由器体检 | ❌ | ✅ |
| 远程查看状态 | — | Web 控制台（手机浏览器访问） |

## 构建 APK

当前配置目标 API 36，固定 python-for-android `v2026.05.09`、Python 3.11.8 和 Kivy 2.3.1；构建会在固定源码模板上补入 Android `specialUse` 前台服务所需的 subtype 说明。CI 手动工作流会打包 debug APK 并检查合并后的 Android Manifest。

源码和单元测试仍不等于 APK 构建、手机安装或后台运行验收。2026-10-16 run `38851368170` 在 Kivy 2.3.0 的 `cgl_gl.c` 编译时因 Clang 函数指针 const 限定不兼容而失败；spec 已改 pin Kivy 2.3.1。随后 run `38852810567` 又在 p4a 临时 Python venv 执行 `pip install -U pip` 时失败，日志为 `ImportError: cannot import name 'open_rich_spinner'`。根因推断是缓存的 build venv 残留混杂 pip 文件，与 p4a 对同版本问题的记录一致；已扩展固定 p4a patch，在创建临时 venv 时使用 `--clear`。修复后的 API 36 构建仍待重新运行和验证。Android 真机锁屏/切网也尚未验收。

APK run `38856748022`（head `cf794ed`）已成功编译 APK，但合并 Manifest 校验发现服务声明、`foregroundServiceType` 和 subtype property 都缺失，因此未上传 artifact。日志中的实际 Buildozer 命令没有 `--service` 参数；原因是配置键误写为 `android.services`，Buildozer 实际读取 `[app] services`。当前已修正为 `services = campusguard:services/campusguard.py:foreground:sticky:foregroundServiceType=specialUse`，并增加配置回归检查；修复后的 APK 尚待 Actions 验证。unsigned AAB run `38856949123`（head `2c83f6b`）已完成 API 36 构建、剥除临时签名和 unsigned 校验并上传 artifact `12028181480`；ZIP CRC 检查通过、47 个条目、没有 JAR 签名文件，SHA-256 为 `45b5d9579a47bc3c6f81662f8f76044300f3e1383b0115ec54dabcb245d80dc9`。该包尚未验证 Play Console 接收或设备安装。iOS run `38856309857`（head `a15e83d`）已成功完成 simulator 编译、安装、启动和 ZIP 打包；artifact `12027332700` 下载检查确认 ZIP 内含完整 `CampusNetCompanion.app/` 目录，bundle id `com.campusnettools.companion`、版本 `0.2.0 (3)`、Simulator 架构 `x86_64/arm64`、adhoc/linker 签名且无 Team ID。iOS 真机、IKEv2 连通和 App Store 发布仍未验收。
PR CI run `38879156449` 的 Windows job 因新回归测试按 Windows 默认 cp1252 解码 UTF-8 spec 而失败（`UnicodeDecodeError`）；测试现显式以 UTF-8 读取，再解析配置。修复后的 run `38879597002`（head `077a4c6`）macOS 与 Windows 测试和静态检查均通过。

本地构建（需 Linux 或 macOS + buildozer 环境；macOS 本机因同样上游问题暂无法出包，
建议用 Windows 的 WSL2/Linux 或 Docker 完成）：

```bash
mkdir -p build_mobile
cp mobile/main.py mobile/buildozer.spec build_mobile/
cp mobile/guard_service.py build_mobile/
cp -r mobile/services build_mobile/
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
- **发布状态**：手动 debug APK 工作流与 AAB 工作流已配置；unsigned AAB 构建尚待验证，signed 模式需要上述 keystore secrets；商店内测/生产发布和审核尚未完成。
- iOS 系统 IKEv2 客户端与 Mac 端 enrollment 路线见 `../ios/CampusNetCompanion/README.md`；App Store build、签名、设备验收和上架尚未完成。
