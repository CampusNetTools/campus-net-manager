# 校园网连接管家 (CampusNetManager) — 开发交接文档

> 本文件给后续接手的 AI 助手 / 开发者（WorkBuddy 等），一站式了解项目现状、如何构建、发布、测试。
> 最后更新：2026-09-05（v2.9.5）

---

## 一、项目概览

- **名称**：校园网连接管家（CampusNetManager）
- **GitHub**：`CampusNetTools/campus-net-manager`（org: CampusNetTools / 显示名 CampusAide）
- **作用**：Dr.COM 校园网自动保活 · 多设备共享上网 · 扫码一键配置 · macOS/Windows 桌面工具
- **技术栈**：Python + tkinter（GUI）+ PyInstaller 打包，macOS .app / Windows .exe
- **当前版本**：**v2.9.5**（2026-09-05 发布为 GitHub Latest）

## 二、主项目路径（git 主仓库）

```
/Users/nanyu/Documents/Codex/2026-08-28/hi-2/campus-net-manager
```
- 这是**唯一**有 git remote（能 push GitHub）的目录。改代码请在这里改。
- 其他位置的副本（桌面/Applications 安装的 app）只是构建产物，改了不会提交。

## 三、核心模块（都在主项目根目录）

| 文件 | 作用 |
|---|---|
| `app_gui.py` | tkinter GUI，主界面 / 档案表单 / 设置 |
| `keepalive_core.py` | 保活核心：环境判定、登录/重登、防踢、档案匹配、APP_VERSION |
| `shared_proxy.py` | 隧道共享代理：HTTP CONNECT、VPN 上游、PAC、扫码配置页 |
| `diagnostics.py` | 诊断报告 |
| `lida_keepalive.py` | 立达校区专用保活脚本 |
| `tests/` | unittest 测试（75+ 项） |
| `scripts/build_macos.sh` | macOS 构建脚本 |
| `assets/CampusNetManager.icns` | 应用图标 |
| `icon.ico` | Windows 图标 |

## 四、版本号管理（重要！改版必须三处同步）

1. `keepalive_core.py` → `APP_VERSION = "X.Y.Z"`
2. `CHANGELOG.md` → 顶部加 `## vX.Y.Z` 条目
3. `README.md` → 徽章 `下载-vX.Y.Z`

> ⚠️ 教训：之前只改 GUI 漏改 APP_VERSION，构建出的 app 版本号仍显示旧版。
> `Info.plist` 的 CFBundleShortVersionString 由构建脚本从 APP_VERSION 读取，所以 APP_VERSION 改了即可。

## 五、构建（macOS）

```bash
cd /Users/nanyu/Documents/Codex/2026-08-28/hi-2/campus-net-manager
unset http_proxy https_proxy   # 必须! 否则构建/测试走系统代理
export PYTHON_BIN="$PWD/.venv/bin/python"
bash scripts/build_macos.sh    # 产物在 dist/macos/校园网连接管家.app
```

- 构建后**打 zip**（含 .app）：
  ```bash
  cd dist/macos && zip -rq "校园网连接管家-macOS-arm64-${VER}.zip" "校园网连接管家.app"
  ```

## 六、测试

```bash
cd /Users/nanyu/Documents/Codex/2026-08-28/hi-2/campus-net-manager
unset http_proxy https_proxy   # 关键! 否则测试连代理卡死
.venv/bin/python -m unittest discover -s tests
```

## 七、发布 GitHub Release

```bash
gh release create vX.Y.Z -R CampusNetTools/campus-net-manager \
  --title "校园网连接管家 vX.Y.Z" --notes-file /tmp/release.md \
  dist/macos/校园网连接管家-macOS-arm64-vX.Y.Z.zip
```

## 八、环境 / 已知坑（必读）

- **http_proxy 污染**：本机有 `http_proxy=127.0.0.1:7897`（Clash）。测试/构建/urllib 一律先 `unset`，否则连本机端口报 Connection refused。测试里用 `build_opener(ProxyHandler({}))` 绕过。
- **校园网配置**：认证服务器 `192.168.16.3`（E-Portal 4.0，端口 80/801）；自服务系统 `10.11.1.154:8080`；账号密码走 macOS 钥匙串，值勿外泄。
- **档案类型字段**：`profile_type` = `"campus"`(登录保活) / `"wifi"`(只检测断网)。新建热点/家里WiFi档案用 wifi 类型，认证服务器留空置灰。
- **环境判定**：`is_campus_locked` + `best_match_profile`（SSID精确 > 网关精确 > 认证可达校园网）。用户选了「任意网络」时绝不登录。
- **VPN 上游**：`shared_proxy.py` 的 `upstream_proxy`（dict{host,port}），设备流量经 CONNECT 注入 VPN。
- **光猫/路由器**：`router_fingerprint()` 探测管理页，支持 80/8080 + 光猫识别词。

## 九、GitHub 头像（已知限制）

组织/仓库头像**无法通过 REST API 上传**（`PATCH /orgs/{org}` 只收 JSON，avatar_url 只读）。只能网页端手动上传。仓库无独立头像，继承组织头像。

## 十、当前状态（2026-09-05）

- git main 已与 GitHub 同步（最新 v2.9.5）
- GitHub Release 最新 = v2.9.5（已发布）
- 电脑上只保留 /Applications/校园网连接管家.app（v2.9.5，从 GitHub 下载安装）
- 主项目源码在 Documents/Codex/.../campus-net-manager

## 十一、规范提醒（用户偏好）

- 改代码前先看需求，多版本迭代时每轮升版本 + 更新 CHANGELOG/README。
- 涉及账号/密码/订阅一律 `[REDACTED]`，不保留真实值。
- 项目用于学生比赛 + 简历，UI/体验要 polished。
