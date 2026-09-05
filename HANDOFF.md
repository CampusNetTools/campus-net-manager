# 校园网连接管家 (CampusNetManager) — 开发交接文档

> 本文件给后续接手的 AI 助手 / 开发者（WorkBuddy 等），一站式了解项目现状、如何构建、发布、测试。
> 最后更新：2026-09-06（v3.0.0）

---

## 一、项目概览

- **名称**：校园网连接管家（CampusNetManager）
- **GitHub**：`CampusNetTools/campus-net-manager`（org: CampusNetTools / 显示名 CampusAide）
- **作用**：Dr.COM 校园网自动保活 · 多设备共享上网 · 扫码一键配置 · macOS/Windows 桌面工具
- **技术栈**：Python + tkinter（GUI）+ PyInstaller 打包，macOS .app / Windows .exe
- **当前版本**：**v3.0.0**（2026-09-06，代码拆分大版本）

## 二、主项目路径（git 主仓库）

```
/Users/nanyu/Desktop/校园连接助手
```
- 2026-09-06 起以桌面目录为**唯一工作区**（用户决定），已对齐 GitHub main。改代码请在这里改。
- `/Users/nanyu/Documents/Codex/2026-08-28/hi-2/campus-net-manager` 为旧主仓库（已归档，不再更新）；/Applications 安装的 app 只是构建产物。

## 三、代码结构（v3.0.0 起）

```
keepalive_core.py   # 门面: re-export + APP_VERSION(唯一权威版本号) + 诊断/实例锁
core/               # 核心实现包
  common.py         # 标准库导入 re-export + 平台标志 + 路径/常量
  config.py         # 档案/配置/钥匙串/通知开关
  history.py        # 网络历史 + 断网时间线
  netinfo.py        # SSID/网关/物理网卡/VPN 探测
  speed.py          # 测速与质量评分
  router.py         # 路由器体检/管理页/中继指引/伪装检测
  portal.py         # captive portal 认证服务器探测
  matching.py       # 档案匹配 + 校园网环境判定
  auth.py           # Dr.COM 登录 + 联网检测 + http 工具
  sysutils.py       # 日志/系统通知/自启/caffeinate/单实例锁
  daemon.py         # KeepAliveDaemon 守护线程
app_gui.py          # App 类组装入口 (继承 Mixin)
gui/                # 界面包
  theme.py          # 深色主题常量
  profile_form.py / router_tools.py / speed_window.py / tunnel_ui.py
  preferences.py / tray.py / daemon_ctl.py / wizard.py   # 八个 Mixin
shared_proxy.py     # 隧道共享代理 (HTTP CONNECT / VPN 上游 / PAC / 扫码页)
diagnostics.py      # 诊断报告导出
lida_keepalive.py   # 立达校区专用 CLI 保活脚本
tests/              # unittest（84 项）
scripts/build_macos.sh    # macOS 构建
scripts/sync_version.py   # 版本号单源同步
scripts/split_core.py / split_gui.py   # v3.0.0 拆分脚本(留档)
```

**铁律**：跨模块调用一律 `模块.名字(...)`（如 `auth.check_auth(...)`），禁止 `from core.auth import check_auth` 后裸调——否则 mock patch 不到。测试 patch 目标 = 定义所在模块（如 `patch.object(auth, "check_auth")`）。

## 四、版本号管理（单源化，v2.9.6 起）

**唯一权威版本号**：`keepalive_core.py` → `APP_VERSION = "X.Y.Z"`

改版流程：
1. 改 `APP_VERSION`
2. `CHANGELOG.md` 顶部加 `## vX.Y.Z` 条目
3. 运行 `python scripts/sync_version.py`（自动同步 README 徽章并校验 CHANGELOG）

> CI 会对每个 push 执行 `sync_version.py --check`，不一致直接红。
> `Info.plist` 版本由构建脚本从 APP_VERSION 读取，无需手改。

## 五、构建（macOS）

```bash
cd /Users/nanyu/Desktop/校园连接助手
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
cd /Users/nanyu/Desktop/校园连接助手
env -u http_proxy -u https_proxy .venv/bin/python -m unittest discover -s tests
```
- 84 项测试，全过约 1-3 秒。若套件整体卡住超过 1 分钟，必有测试在真实网络/死循环——用 `-v` 定位。
- **改回调签名（on_status/on_env/on_alert）必须全局搜 tests/ 里的 lambda 同步改**，否则守护兜底会静默吞掉 TypeError（v2.9.6 已加隔离+告警，但测试仍应同步）。

## 七、发布 GitHub Release（CI 自动）

```bash
git tag vX.Y.Z && git push origin main vX.Y.Z
```
CI 自动：双平台跑测试 → macos-latest 构建 .app 打 zip、windows-latest 构建 exe → 附加到该 tag 的 Release。
Windows exe 不再依赖 Windows 本机打包。

## 八、环境 / 已知坑（必读）

- **http_proxy 污染**：本机有 `http_proxy=127.0.0.1:7897`（Clash）。测试/构建/urllib 一律先 `unset`，否则连本机端口报 Connection refused。测试里用 `build_opener(ProxyHandler({}))` 绕过。
- **守护兜底**：`KeepAliveDaemon.run()` 的 catch-all 会吞所有异常。v2.9.6 起连续异常会计数+堆栈+超阈值告警；界面回调异常走 `_safe_callback` 单独隔离。
- **校园网配置**：认证服务器 `192.168.16.3`（E-Portal 4.0，端口 80/801）；自服务系统 `10.11.1.154:8080`；账号密码走 macOS 钥匙串，值勿外泄。
- **档案类型字段**：`profile_type` = `"campus"`(登录保活) / `"wifi"`(只检测断网)。新建热点/家里WiFi档案用 wifi 类型，认证服务器留空置灰。
- **环境判定**：`is_campus_locked` + `best_match_profile`（SSID精确 > 网关精确 > 认证可达校园网）。用户选了「任意网络」时绝不登录。
- **VPN 上游**：`shared_proxy.py` 的 `upstream_proxy`（dict{host,port}），设备流量经 CONNECT 注入 VPN。
- **光猫/路由器**：`router_fingerprint()` 探测管理页，支持 80/8080 + 光猫识别词。

## 九、GitHub 头像（已知限制）

组织/仓库头像**无法通过 REST API 上传**（`PATCH /orgs/{org}` 只收 JSON，avatar_url 只读）。只能网页端手动上传。仓库无独立头像，继承组织头像。

## 十、当前状态（2026-09-06）

- git main 已与 GitHub 同步（v2.9.6）
- CI 已上线：push 双平台测试，tag 自动出 macOS zip + Windows exe
- 主工作区：桌面 校园连接助手（唯一）

## 十一、规范提醒（用户偏好）

- 改代码前先看需求，多版本迭代时每轮升版本 + 更新 CHANGELOG + 跑 sync_version.py。
- 涉及账号/密码/订阅一律 `[REDACTED]`，不保留真实值。
- 项目用于学生比赛 + 简历，UI/体验要 polished。
