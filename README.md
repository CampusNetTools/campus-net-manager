# 校园网连接管家 (CampusNetManager)

[![Release](https://img.shields.io/badge/下载-v2.9.0-green)](https://github.com/CampusNetTools/campus-net-manager/releases/latest)

> Dr.COM 校园网自动保活 · 多设备共享上网 · Windows / macOS 桌面工具

## ⬇️ 下载

**Windows 桌面版（双击即用，无需安装 Python）**：👉 [Releases 页面下载 exe](https://github.com/CampusNetTools/campus-net-manager/releases/latest)

**macOS 桌面版（Apple Silicon）**：在 macOS 上执行 `./scripts/build_macos.sh`，产物为 `dist/macos/校园网连接管家.app`。

- 单文件便携版，绿色免安装，放在桌面/任意目录即可
- 首次运行在「连接档案」里填校园网账号密码即可 (CampusNet Manager)

校园网自动连接与保活桌面工具。基于 MIT 协议项目 [csaslu/LidaNetDaemon](https://github.com/csaslu/LidaNetDaemon)（Go 版，作者 Bigsk）的接口思路，Python 重写并大幅增强。

校园网（Dr.COM 等 Portal 认证系统）会随机踢掉在线设备（后台仍显示在线），本工具自动检测、掉线自动重登，并在非校园网环境自动休眠。

## 核心特性

1. **多档案自动匹配**：每个 WiFi（SSID）一套配置（账号/密码/运营商/认证服务器），自动按当前 WiFi 匹配；SSID 留空的档案作为"默认档案"兜底（有线连接、其他网络）；有线场景按网关 IP 匹配（档案含"绑定方式：无线/有线"选项卡）
2. **环境识别**：探测认证服务器是否可达——可达 = 校园网环境，正常工作；不可达 = 非校园网，守护休眠（绝不误登录）
3. **接入方式无关**：有线直连、WiFi 直连（LIDA-UNIVERSITY）、经路由器中继（NAT/桥接均可），自动工作
4. **替路由器保活**：电脑连着中继路由器时，登录请求按来源 IP 生效——路由器被踢后软件自动帮它重登，无需手动断电重启
5. **双路径联网检测**：使用多组 204/预期正文探针验证真实外网；VPN 开启时同时检查系统路径和校园网直连路径，避免认证页劫持造成“假在线”
6. **守护自愈 + 唤醒即检**：守护异常自动恢复；网络切换、电脑唤醒和自动登录成功后立即复检，并同步刷新顶部网络、环境和档案状态
7. **系统通知可配置**：掉线、恢复失败、恢复成功和新设备共享请求可分别开关；关闭窗口后守护仍可继续运行
8. **隧道共享（带访问控制）**：一键启动 HTTP 代理（8080），自动生成 PAC、手机引导页和二维码并完成启动自检；新设备首次连接仍需授权，防止开放代理被滥用
9. **移动热点引导**：一键检测/打开 Windows 移动热点设置，设备直连校园网时用热点带多设备
10. **路由器管理页直达**：中继/桥接后原 192.168.x.1 失效，自动探测（网关/ARP）新管理地址并打开浏览器
11. **新手向导 + 品牌指引**：分步引导配置；自动识别路由器品牌（华为/小米/TP-LINK/迅捷等）给出对应中继设置路径
12. **路由器只读体检**：读取网关、ARP、管理页公开标识和 UPnP 型号，评估 WISP/OpenWrt 前置条件并保存固定管理入口
13. **VPN 自动对比测速**：自动识别 VPN；开启 VPN 时自动比较经过 VPN 和直连网络，未开启时只测当前连接；低速线路按有效限时样本计算，不因固定流量未传完而误报失败
14. **多来源认证探测**：并行使用 Android/Google/Microsoft/Apple/普通 HTTP 探针，识别 HTTP、HTML 与 JavaScript 跳转；支持发现多个认证服务器并加入下拉框，已联网时也会验证已有地址的 Dr.COM/EPortal 特征
15. **网络质量诊断**：测速同时给出 TCP/TLS 校正延迟、抖动、请求成功率和质量评分，并自动显示 VPN 带来的变化
16. **隐私与稳定性报告**：macOS 密码保存到系统钥匙串，配置文件不再保存明文密码；网络历史默认关闭，用户开启后只记录连接状态并生成通俗的 7 天汇总
17. **合盖/休眠保持运行**：macOS 用 caffeinate 电源断言阻止系统/空闲睡眠，守护线程在合盖或系统空闲时继续联网保活，掉线后仍能自动重登（可在偏好设置中开关）
18. **中继路由器自动重登**：电脑连着中继路由器时按校园网环境处理，即便认证服务器暂时探测不到也会尝试重登，不再误判「非校园网」后静止休眠；并自动优先选用已填写账号的校园网档案
19. **防踢保活**：周期性刷新登录会话让本机/路由器保持最新，校园网名额满时第 3 台设备登录被挤掉的是别人而非本设备

VPN 开启时，主界面会分别判断 VPN/系统路径和校园网物理出口：两条都通显示“VPN 与校园网在线”；仅物理出口正常显示“校园网在线（VPN异常）”，不会再误报“假在线”或反复重登校园网。

> 路由器体检不会登录管理后台或自动刷写固件。刷机无法保证“零影响”；必须先确认精确型号与硬件版本、官方适配镜像、SHA256、配置备份和恢复方式，最后仍需人工确认。
此外支持认证服务器自动探测与历史下拉、安全配置导出/导入、日志自动清理、一键脱敏诊断和开机自启。

## 使用

### 桌面 App（推荐）

桌面上双击「**校园网连接管家.exe**」，配套 `config.json`（与 exe 同目录）。

- **换路由器 / 换账号 / 换 WiFi**：打开 App → 在"连接档案"中修改或新建档案（绑定对应 WiFi 的 SSID）→ 保存 → 重启守护
- **立达专属档案**：下拉框内置 `立达校园网 (LIDA-UNIVERSITY)`，认证服务器预设为 `http://192.168.16.3/`；只需填写自己的账号、密码并选择运营商
- **新建档案**：点「＋ 新建」→ 填档案名称、绑定 WiFi (SSID)（留空=默认档案）、账号、密码、运营商、认证服务器 → 保存
- **查看状态**：状态灯（守护 / 网络 / 环境）+ 日志面板
- **Windows 配置文件/日志**：跟随 exe 所在目录
- **macOS App 配置文件/日志**：`~/Library/Application Support/CampusNetManager/`（密码单独保存在系统钥匙串，不会写入配置文件或 `.app` 包内）

### config.json 结构

```json
{
  "profiles": [
    {
      "name": "立达校园网",
      "preset": "lida-campus",
      "ssid": "LIDA-UNIVERSITY",
      "username": "",
      "password": "",
      "login_type": "cmcc",
      "auth_url": "http://192.168.16.3/",
      "interval": 60
    },
    {
      "name": "默认档案(其他网络)",
      "ssid": "",
      "username": "",
      "password": "",
      "login_type": "cmcc",
      "auth_url": "http://192.168.16.3/",
      "interval": 60
    }
  ],
  "active_profile": "立达校园网WiFi"
}
```

- `ssid`：绑定 WiFi 名；**留空 = 默认档案**（当前 WiFi 无精确匹配时使用）
- `login_type`：`cmcc`（移动）/ `unicom`（联通）/ `teacher`（教师）
- `auth_url`：认证服务器地址，不同学校不同，默认 `http://192.168.16.3/`

### 命令行版

- 手动运行：`pythonw app_gui.py`
- 测试单次检测：`python -c "import keepalive_core as c; ..."`

## 打包

### Windows

```bash
pyinstaller --onefile --noconsole --name CampusNetManager app_gui.py
```

注意：打包后配置/日志跟随 **exe 所在目录**（`sys.executable` 定位），部署时把 `config.json` 与 exe 放一起。

### macOS（Apple Silicon）

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-dev.txt
PYTHON_BIN="$(pwd)/.venv/bin/python" ./scripts/build_macos.sh
```

构建生成已 ad-hoc 签名的 `.app`。它可在本机启动，但没有 Apple Developer 证书和公证；分发给其他 Mac 前，仍需完成正式签名与公证。

## 注意

- 校园网一个账号通常限 2 台设备：手机等设备请连中继路由器（NAT 后不占名额），避免超限互顶
- 路由器（中继）的会话由路由器自己管理，本工具管不到；被踢需重启路由器或到自助系统注销
- macOS 密码保存在系统钥匙串；导出的配置默认不包含密码

## License

MIT（详见 LICENSE，保留原作者 Bigsk 版权声明）
