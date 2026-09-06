# 校园网连接管家 · 手机版（Android）

手机直连校园网 WiFi 时的 Dr.COM 登录与前台保活工具，复用桌面端 `core/` 包的认证实现。

## 功能

- **一键登录**：填账号/密码/运营商/认证服务器（默认立达 `http://192.168.16.3/`），点「立即登录」
- **前台保活**：App 打开期间每 60 秒检测认证与外网，掉线自动重登
- **环境识别**：认证服务器不可达时显示「非校园网环境」，不误登录
- **档案保存**：配置存应用私有目录（`profile.json`）

## 与桌面版的关系

| 能力 | 手机版 | 桌面版 |
|---|---|---|
| Dr.COM 登录/重登 | ✅ 同一套 core.auth | ✅ |
| 保活 | 前台有效（锁屏/切后台会被系统挂起） | 后台守护线程 + 合盖保活 |
| 隧道共享/测速/路由器体检 | ❌ | ✅ |
| 远程查看状态 | — | Web 控制台（手机浏览器访问） |

## 构建 APK

> ✅ **CI 构建可用**（2026-09-06 验证）：`buildozer.spec` 里 `p4a.branch = v2024.01.21`
> （python-for-android 旧稳定版）。master/v2026.05.09 卡在 Python 3.14 迁移
> （纯 Python 依赖的 Android wheel 装不上：`charset_normalizer ... is not a supported wheel`），
> 不要用默认 master。触发：Actions 页 → 「手机版 APK」 → Run workflow（约 18 分钟，
> 产物在 Actions 运行页 Artifacts 下载，debug 签名可直接安装）。

本地构建（需 Linux 或 macOS + buildozer 环境；macOS 本机因同样上游问题暂无法出包，
建议用 Windows 的 WSL2/Linux 或 Docker 完成）：

```bash
mkdir -p build_mobile
cp mobile/main.py mobile/buildozer.spec build_mobile/
cp -r core build_mobile/
cd build_mobile
buildozer android debug   # 产物在 bin/*.apk
```

## 已知限制

- **后台保活**：需要 Android 前台服务（foreground service）支持，当前版本 App 在前台时保活生效。请在系统设置里对本 App 关闭电池优化以延长前台/后台存活时间。
- iOS 不支持（需要 Apple 开发者签名，暂不投入）。
