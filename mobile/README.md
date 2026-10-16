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

手动运行 `.github/workflows/android-release-aab.yml` 可构建 API 36 AAB artifact；unsigned 模式用于检查打包结果，不能上传 Play；signed 模式会验证签名并产出可供 Play Console 上传的 bundle。此工作流不会自动发布到 Google Play。signed 模式需在 GitHub Actions secrets 配置 `ANDROID_KEYSTORE_BASE64`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD`。签名材料只保存在 GitHub 官方 secrets 与 Google Play Console，不写入仓库或聊天。当前还没有任何 AAB 构建产物；`38854446189` 是无 jobs 的 push 事件，不构成构建验证。首次手动派发被 job 级 `runner.temp` 表达式拒绝，已改为步骤内设置临时 keystore 路径，待重新派发确认。

## 已知限制

- **运行时状态**：Android 前台服务由用户在 App 内启动/停止，要求通知权限；系统省电策略、厂商后台限制和网络状态仍需真机验收。
- **凭据**：Android Keystore 实现已加入源码，但本机尚无 Android 构建工具链；最终 APK 中的加解密、升级迁移和密钥丢失恢复仍待验证。
- **发布状态**：手动 debug APK 工作流与 AAB 工作流已配置；unsigned AAB 构建尚待验证，signed 模式需要上述 keystore secrets；商店内测/生产发布和审核尚未完成。
- iOS 系统 IKEv2 客户端与 Mac 端 enrollment 路线见 `../ios/CampusNetCompanion/README.md`；App Store build、签名、设备验收和上架尚未完成。
