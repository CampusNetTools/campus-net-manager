# 校园网连接管家 (CampusNetManager)

[![Release](https://img.shields.io/badge/下载-v2.0.0-green)](https://github.com/CampusNetTools/campus-net-manager/releases/latest)

> Dr.COM 校园网自动保活 · 多设备共享上网 · 免安装 Windows 桌面工具

## ⬇️ 下载

**桌面版（Windows，双击即用，无需安装 Python）**：👉 [Releases 页面下载 exe](https://github.com/CampusNetTools/campus-net-manager/releases/latest)

- 单文件便携版，绿色免安装，放在桌面/任意目录即可
- 首次运行在「连接档案」里填校园网账号密码即可 (CampusNet Manager)

校园网自动连接与保活桌面工具。基于 MIT 协议项目 [csaslu/LidaNetDaemon](https://github.com/csaslu/LidaNetDaemon)（Go 版，作者 Bigsk）的接口思路，Python 重写并大幅增强。

校园网（Dr.COM 等 Portal 认证系统）会随机踢掉在线设备（后台仍显示在线），本工具自动检测、掉线自动重登，并在非校园网环境自动休眠。

## 核心特性

1. **多档案自动匹配**：每个 WiFi（SSID）一套配置（账号/密码/运营商/认证服务器），自动按当前 WiFi 匹配；SSID 留空的档案作为"默认档案"兜底（有线连接、其他网络）；有线场景按网关 IP 匹配（档案含"绑定方式：无线/有线"选项卡）
2. **环境识别**：探测认证服务器是否可达——可达 = 校园网环境，正常工作；不可达 = 非校园网，守护休眠（绝不误登录）
3. **接入方式无关**：有线直连、WiFi 直连（LIDA-UNIVERSITY）、经路由器中继（NAT/桥接均可），自动工作
4. **替路由器保活**：电脑连着中继路由器时，登录请求按来源 IP 生效——路由器被踢后软件自动帮它重登，无需手动断电重启
5. **双重检测**：认证页标题（`注销页`=在线）+ 真实外网连通（百度/QQ）——避免"登录页能开但外网被拦"的假在线
6. **守护自愈 + 唤醒即检**：守护异常自动恢复（看门狗兜底）；等待分段化，网络切换/电脑唤醒后立即检测，不等满间隔
7. **系统托盘常驻**：关窗口最小化到托盘，守护继续；掉线/重登/失败弹托盘通知
8. **隧道共享（带访问控制）**：一键开启 HTTP 代理（8080），手机/平板 Wi-Fi 手动代理即可借本机网络上网（不占额外校园网名额）；新设备首次连接需授权（白名单持久化），防开放代理被滥用
9. **移动热点引导**：一键检测/打开 Windows 移动热点设置，设备直连校园网时用热点带多设备
10. **路由器管理页直达**：中继/桥接后原 192.168.x.1 失效，自动探测（网关/ARP）新管理地址并打开浏览器
11. **新手向导 + 品牌指引**：分步引导配置；自动识别路由器品牌（华为/小米/TP-LINK/迅捷等）给出对应中继设置路径
12. **认证服务器自动探测 + 历史下拉**；密码掩码；配置导出/导入；日志自动清理（超 2MB 截断）；一键诊断导出（脱敏）；开机自启开关（软件内）

## 使用

### 桌面 App（推荐）

桌面上双击「**校园网连接管家.exe**」，配套 `config.json`（与 exe 同目录）。

- **换路由器 / 换账号 / 换 WiFi**：打开 App → 在"连接档案"中修改或新建档案（绑定对应 WiFi 的 SSID）→ 保存 → 重启守护
- **新建档案**：点「＋ 新建」→ 填档案名称、绑定 WiFi (SSID)（留空=默认档案）、账号、密码、运营商、认证服务器 → 保存
- **查看状态**：状态灯（守护 / 网络 / 环境）+ 日志面板
- **配置文件/日志**：跟随 exe 所在目录

### config.json 结构

```json
{
  "profiles": [
    {
      "name": "立达校园网WiFi",
      "ssid": "LIDA-UNIVERSITY",
      "username": "24012752",
      "password": "****",
      "login_type": "cmcc",
      "auth_url": "http://192.168.16.3/",
      "interval": 60
    },
    {
      "name": "默认档案(其他网络)",
      "ssid": "",
      "username": "24012752",
      "password": "****",
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

```bash
pyinstaller --onefile --noconsole --name CampusNetManager app_gui.py
```

注意：打包后配置/日志跟随 **exe 所在目录**（`sys.executable` 定位），部署时把 `config.json` 与 exe 放一起。

## 注意

- 校园网一个账号通常限 2 台设备：手机等设备请连中继路由器（NAT 后不占名额），避免超限互顶
- 路由器（中继）的会话由路由器自己管理，本工具管不到；被踢需重启路由器或到自助系统注销
- 密码明文保存在 `config.json`，请勿外传

## License

MIT（详见 LICENSE，保留原作者 Bigsk 版权声明）
