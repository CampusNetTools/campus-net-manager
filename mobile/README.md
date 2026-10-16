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

当前配置目标 API 36，固定 python-for-android `v2026.05.09` 与 Python 3.11.8；构建会在固定源码模板上补入 Android `specialUse` 前台服务所需的 subtype 说明。CI 手动工作流会打包 debug APK 并检查合并后的 Android Manifest。

源码和单元测试仍不等于 APK 构建、手机安装或后台运行验收。当前没有 API 36 构建或真机验证结果；必须以 GitHub Actions 成功产物、Manifest 读取结果和 Android 真机锁屏/切网测试为准。

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

## 已知限制

- **运行时状态**：Android 前台服务由用户在 App 内启动/停止，要求通知权限；系统省电策略、厂商后台限制和网络状态仍需真机验收。
- **凭据**：Android Keystore 实现已加入源码，但本机尚无 Android 构建工具链；最终 APK 中的加解密、升级迁移和密钥丢失恢复仍待验证。
- **发布状态**：当前只有手动 debug APK 工作流；签名 AAB、商店内测/生产发布和审核尚未完成。
- iOS 原型与路线见 `../ios/`；App Store build、签名、设备验收和上架尚未完成。
