# 校园网连接管家 (CampusNetManager) — 开发交接文档

> 本文件给后续接手的 AI 助手 / 开发者（WorkBuddy 等），一站式了解项目现状、如何构建、发布、测试。
> 最后更新：2026-09-11（v5.1.0）

---

## 一、项目概览

- **名称**：校园网连接管家（CampusNetManager）
- **GitHub**：`CampusNetTools/campus-net-manager`（org: CampusNetTools / 显示名 CampusAide）
- **作用**：Dr.COM 校园网自动保活 · 多设备共享上网 · 扫码一键配置 · 路由器后台工作台 · macOS/Windows 桌面工具
- **技术栈**：Python 3.11 + tkinter（GUI）+ PyInstaller 打包，macOS .app / Windows .exe
- **当前版本**：**v5.1.0**（2026-09-11，路由器后台工作台融合）

## 二、主项目路径（按平台）

**Windows（当前主力开发机）**
```
C:/Users/lugua/projects/lida-net-keepalive      # 源码工作区（git 主仓库）
C:/Users/lugua/Desktop/校园网连接管家.exe        # 交付 exe（构建后复制到这里并重启）
C:/Users/lugua/Desktop/config.json               # 运行配置（与 exe 同目录，不进版本库）
C:/Users/lugua/Desktop/keepalive.log             # 运行日志（同上）
```

**macOS（另一台机器，用户名 nanyu）**
```
/Users/nanyu/Desktop/校园连接助手
```
- 两台机器都对齐 GitHub main；**改代码前先 `git pull`**，两边可能并行改（v5.1.0 发布时 Mac 侧也并行上传过资产）。
- `/Users/nanyu/Documents/Codex/2026-08-28/hi-2/campus-net-manager` 为旧主仓库（已归档）。

## 三、代码结构（v5.1.0）

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
  profile_form.py / router_tools.py / router_proxy.py / router_console_ui.py
  speed_window.py / tunnel_ui.py / preferences.py / tray.py / daemon_ctl.py / wizard.py
  update_ui.py      # 自动更新弹窗/下载/自替换
  console_ui.py     # 网络控制台开关+地址/二维码窗口
shared_proxy.py     # 隧道共享代理 (HTTP CONNECT / VPN 上游 / PAC / 扫码页)
updater.py          # 自动更新核心: 版本比较/Release检查/下载/自替换脚本
web_console.py      # 局域网 Web 控制台 HTTP 服务, 口令鉴权 (端口 8081)
mobile/             # 手机版 (Kivy, Android)
diagnostics.py      # 诊断报告导出
CampusNetManager.spec  # PyInstaller 打包配置 (onefile, console=False, icon.ico)
tests/              # unittest（260 项, 2 skipped）
scripts/build_macos.sh    # macOS 构建
scripts/sync_version.py   # 版本号单源同步
```

**铁律**：跨模块调用一律 `模块.名字(...)`（如 `auth.check_auth(...)`），禁止 `from core.auth import check_auth` 后裸调——否则 mock patch 不到。测试 patch 目标 = 定义所在模块（如 `patch.object(auth, "check_auth")`）。

**新增窗口的接法（v5.1.0 起）**：写一个 `XxxMixin` 放在 `gui/`，在 `app_gui.py` 顶部 `from gui.xxx import XxxMixin`，把它加进 `class App(...)` 的基类列表，按钮用 `self._fwin_open_legacy("key", self.show_xxx_window)` 接进功能导航（`tests/test_main_grid_order.py` 会数 `_fwin_open_legacy` 出现次数，加按钮要同步改期望值）。

## 四、版本号管理（单源化）

**唯一权威版本号**：`keepalive_core.py` → `APP_VERSION = "X.Y.Z"`

改版流程：
1. 改 `APP_VERSION`
2. `CHANGELOG.md` 顶部加 `## vX.Y.Z` 条目
3. 运行 `python scripts/sync_version.py`（自动同步 README 徽章并校验 CHANGELOG）

> CI 会对每个 push 执行 `sync_version.py --check`，不一致直接红。
> `Info.plist` 版本由构建脚本从 APP_VERSION 读取，无需手改。

## 五、构建

**Windows（当前主力，实测可用）**
```bash
cd /c/Users/lugua/projects/lida-net-keepalive
uv run --with pyinstaller --with pystray --with pillow --with qrcode \
   python -m PyInstaller CampusNetManager.spec --noconfirm
# 产物 dist/CampusNetManager.exe（约 19.6 MB），然后覆盖部署到桌面并重启：
#   1) 停掉同名进程（按精确文件名匹配，见第八节「杀进程自伤」坑）
#   2) Copy-Item dist/CampusNetManager.exe → 桌面\校园网连接管家.exe
#   3) Start-Process 桌面 exe
```
- 验证部署：`ls` 比对字节数，运行后窗口标题应显示 `校园网连接管家 vX.Y.Z`。

**macOS**
```bash
cd /Users/nanyu/Desktop/校园连接助手
unset http_proxy https_proxy   # 必须! 否则构建/测试走系统代理
export PYTHON_BIN="$PWD/.venv/bin/python"
bash scripts/build_macos.sh    # 产物 dist/macos/校园网连接管家.app
cd dist/macos && zip -rq "校园网连接管家-macOS-arm64-${VER}.zip" "校园网连接管家.app"
```

## 六、测试

```bash
# Windows
cd /c/Users/lugua/projects/lida-net-keepalive && python -m pytest tests/ -q
# macOS
cd /Users/nanyu/Desktop/校园连接助手 && env -u http_proxy -u https_proxy .venv/bin/python -m unittest discover -s tests
```
- **260 项通过 / 2 skipped**（约 18 秒）。若套件整体卡住超 1 分钟，必有测试在真实网络/死循环——用 `-v` 定位。
- **测试里禁止写死绝对日期**：`tests/test_timeline_stealth.py` 曾写死 `2026-09-04` 配合 `days=7` 窗口，到期后必假失败（v5.1.0 已改相对日期）。
- **改回调签名（on_status/on_env/on_alert）必须全局搜 tests/ 里的 lambda 同步改**，否则守护兜底会静默吞掉 TypeError。

## 七、发布 GitHub Release

```bash
# 1) 版本号 + CHANGELOG + sync_version.py（见第四节）
# 2) 提交并打 tag
git add -A && git commit -m "vX.Y.Z: ..." && git push origin main
git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
```
CI 会跑双平台测试；Windows 包也可本机交叉打（见第五节）。

**手工上传资产（无 gh CLI 时，实测可用；务必照做）**
```bash
TOKEN=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill | grep '^password=' | cut -d= -f2)
printf 'Authorization: token %s\nAccept: application/vnd.github+json\nUser-Agent: rel\n' "$TOKEN" \
    > "C:/Users/lugua/AppData/Local/Temp/ghhdr.txt"

# 创建 release
curl -s -X POST -H @"C:/Users/lugua/AppData/Local/Temp/ghhdr.txt" \
  "https://api.github.com/repos/CampusNetTools/campus-net-manager/releases" \
  -d '{"tag_name":"vX.Y.Z","name":"vX.Y.Z","body":"...","draft":false}'

# 上传资产：必须裸二进制（multipart 会把信封当文件存！）
curl -s -X POST -H @"C:/Users/lugua/AppData/Local/Temp/ghhdr.txt" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @"C:/Users/lugua/projects/lida-net-keepalive/dist/CampusNetManager.exe" \
  "https://uploads.github.com/repos/CampusNetTools/campus-net-manager/releases/<REL_ID>/assets?name=CampusNetManager-vX.Y.Z-win64.exe"
```
**上传后必须验真**：① API 看 asset `size` 是否等于本地字节数；② 下载回来比对，URL 要加缓存破坏参数 `?cb=$RANDOM`（CDN 按资产名缓存，删掉同名坏资产重传后 GET 旧 URL 仍返回坏字节）。

## 八、路由器后台工作台（v5.1.0 新增）

部署在小米路由器 BE6500Pro（RD08，`192.168.31.1`）上的监控工作台，桌面端把它融合进管家（无需 SSH）。

**路由器侧接口（uhttpd 监听 8088）**
- `GET  http://192.168.31.1:8088/cgi-bin/status.sh` → JSON：
  `relay{ssid,signal,bssid,ip}` / `ap{ssid,channel,up}` / `auth` / `net` /
  `proxy{proc,p7890,p7891,panel,nodes}` / `vpn{xl2tpd,ipsec,udp500}` / `ssh` / `console` /
  `sys{model,rom,uptime,load,mem_used,mem_total}` / `guard{ota_auto,mlo_support,mlo_enable}` / `log`
- `POST .../cgi-bin/action.sh` → 执行操作，需令牌（默认 `12345678`）
- 自愈守护：`/etc/crontabs/patches/campus-keeper.sh`（重启代理/VPN/重连中继/重登校园网）。**自启必须走 crontab**——`rc.local` 会被固件清空。

**Windows 端实现要点（`gui/router_console_ui.py`）**
- `RouterConsoleMixin.show_router_console_window()`：`threading` + `urllib` 拉取（不阻塞 Tk），回主线程用 `self.after(0, ...)` 刷 UI。
- 配置存 `config.json` 的 `router_console{host,port,token}`，窗口内可改并保存。
- **窗口尺寸自适应**：取 `winfo_reqwidth()/reqheight()` 后夹进屏幕并居中——不要写死像素，高分屏缩放下会裁切。注意窗口未 map 时 `winfo_width()` 返回 `1` 是假象，离屏测试要让它先映射。
- `tk.Text` 必须显式 `width=1` 交给 grid 伸展，否则默认 80 字符宽会把窗口撑很宽。

## 九、环境 / 已知坑（必读）

- **杀进程「自伤」坑（会中断 Agent 会话）**：不要用「路径含 `Desktop`」过滤杀进程——Hermes 后端本身就在 `C:/Users/lugua/Desktop/Hermes Agent CN Desktop/` 下，会把自己杀掉。按**精确文件名**匹配（`$_.Name -eq 应用名`）；中文名先写进 UTF-8 文件再 `Get-Content -Encoding UTF8` 读出（PowerShell 脚本里内联中文会 `UnexpectedToken` 解析失败）。
- **Win11 终端闪窗（v5.1.0 修）**：所有 `subprocess` 调 `curl`/`netsh` 等必须带 `CREATE_NO_WINDOW`（Windows 下 `_NO_WINDOW` 常量）。Win11 默认终端是 Windows Terminal，未隐藏时每次探测都会弹一个终端框闪一下。已修 `core/auth.py`、`core/portal.py`；新增外部命令调用请沿用。
- **http_proxy 污染**：macOS 侧有 `http_proxy=127.0.0.1:7897`（Clash）。测试/构建/urllib 一律先 `unset`，否则连本机端口报 Connection refused。测试里用 `build_opener(ProxyHandler({}))` 绕过。
- **编码**：`netsh`/`reg`/`tasklist` 输出可能是 GBK，`_run_decode` 用「UTF-8 优先、GBK 兜底」智能解码。
- **守护兜底**：`KeepAliveDaemon.run()` 的 catch-all 会吞所有异常（v2.9.6 起连续异常会计数+告警）。
- **校园网配置**：认证服务器 `192.168.16.3`（E-Portal 4.0，端口 80/801）；自服务系统 `10.11.1.154:8080`；账号密码走系统钥匙串，值勿外泄。
- **档案类型字段**：`profile_type` = `"campus"`(登录保活) / `"wifi"`(只检测断网)。
- **环境判定**：`is_campus_locked` + `best_match_profile`（SSID精确 > 网关精确 > 认证可达校园网）。用户选了「任意网络」时绝不登录。
- **frozen 打包后**：配置/日志路径用 `sys.executable` 所在目录，不要用 `__file__`。

## 十、当前状态（2026-09-11，v5.1.0）

- git main = `c96241b`，tag `v5.1.0` 已推；Release v5.1.0 已发布，资产 `CampusNetManager-v5.1.0-win64.exe`（19,594,527 字节，已下载回验 SHA256 一致）。
- 桌面 exe 已更新为 v5.1.0 并在运行；路由器后台工作台已可用（点「路由器」区的「路由器后台工作台」按钮）。
- **待办 / 待确认**：
  1. Release 里有重复 Windows 包（Mac 侧并行上传的 `CampusNetManager_v5.1.0_win64.exe`，20,586,873 字节，命名用 `_` 与主包不一致）——是否删除待用户定；macOS arm64 zip 保留。
  2. 工作台窗口在高分屏实际观感待用户确认（建议再点开看一眼）。
  3. 两台机器并行改同一仓库时，注意先 pull 再改，避免互相覆盖。

## 十一、规范提醒（用户偏好）

- 改代码前先看需求，多版本迭代时每轮升版本 + 更新 CHANGELOG + 跑 sync_version.py。
- 涉及账号/密码/订阅一律 `[REDACTED]`，不保留真实值。
- 项目用于学生比赛 + 简历，UI/体验要 polished。
- 本仓库**不保留个人档案**（`config.json` 已在 `.gitignore`，只提交 `config.example.json`）。
