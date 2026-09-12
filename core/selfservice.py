# -*- coding: utf-8 -*-
"""校园网用户自助服务系统客户端 (Dr.COM Self-Service)。

职责:
  1. 登录自助服务系统, 维护会话 (Cookie/Token)。
  2. 拉取当前账号的"在线设备/会话"列表。
  3. 对指定设备执行"解除绑定 / 强制下线"。

背景:
  校园网单账号有设备数上限(通常 2 台)。当第 N+1 台设备登录时, 认证服务器
  按"会话新鲜度"淘汰最旧的一台。用户希望:
    - 看清当前账号下到底有哪些设备在线;
    - 点一下就能把占用名额的其他设备踢下线(而不是去浏览器里手动操作);
    - 固定某一台(路由器/本机)一直在线, 不被挤掉。

  其中"固定某台一直在线"并不靠自助系统 —— 靠守护的会话刷新(见 daemon.py
  的 kick_guard): 只要被保护设备的会话不断刷新成"最新", 新设备登录时被
  挤掉的就是别人。本模块只负责"看清 + 踢人"。

协议说明 (Dr.COM 自助服务, 需实测校准):
  Dr.COM 自助服务系统通常是挂在校内某个地址的 Web 应用, 常见入口
  `http://<auth-host>:8080/Self/` 或 `/selfservice/`。不同学校部署的
  路径 / 参数名 / 返回格式差异很大, 因此本模块把端点与字段名都做成
  可覆盖的常量, 并内置"宽松解析 + 明确报错", 便于在设备联网后按实际
  响应微调, 而不是写死一种假设。
"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import config  # noqa: F401
from core import auth  # noqa: F401

__all__ = ['SelfServiceError', 'SelfServiceClient', 'fetch_online_devices',
           'kick_device', 'discover_selfservice_url', 'list_devices']

# ---------------------------------------------------------------------------
# 可覆盖的端点与字段 (实测后按学校实际部署微调这些常量即可)
# ---------------------------------------------------------------------------
# 自助服务基础地址: 由认证地址推导, 默认同主机 8080 端口 /Self/。
SELF_PORT = "8080"
SELF_PATH = "/Self/"

# 常见登录端点 (按顺序尝试, 命中一个即可)
LOGIN_ENDPOINTS = [
    "/Self/login.jsp",
    "/Self/login",
    "/Self/sso/login",
    "/selfservice/login.jsp",
    "/SelfService/login.jsp",
]

# 常见"在线设备/会话"端点 (GET, 需登录态)
DEVICE_ENDPOINTS = [
    "/Self/userOnlineList",
    "/Self/onlineList",
    "/Self/getOnlineList",
    "/Self/session/list",
    "/Self/user/online",
    "/selfservice/onlineList",
]

# 常见"踢下线/解除绑定"端点 (POST/GET, 参数名各异)
KICK_ENDPOINTS = [
    "/Self/kickOffline",
    "/Self/offline",
    "/Self/logoutUser",
    "/Self/unbind",
    "/Self/forceOffline",
    "/selfservice/offline",
]

# 登录表单字段名 (Dr.COM 常见) —— 用户名带运营商后缀, 与认证登录一致
LOGIN_USER_FIELD = "userId"
LOGIN_PASS_FIELD = "password"
LOGIN_USER_ALT = "userName"
LOGIN_PASS_ALT = "passwd"

# 会话标识字段名 (踢下线时用来定位"哪台设备")
KICK_SESSION_FIELDS = ["sessionId", "session", "onlineId", "id", "uid", "acct_session_id"]


class SelfServiceError(Exception):
    """自助服务操作失败。message 面向用户, 可直接展示。"""


class SelfServiceClient:
    """自助服务会话客户端。

    一次实例 = 一次登录会话。登录后复用同一 http.cookiejar 维护 Cookie,
    直到显式 logout 或对象销毁。所有请求强制直连(不走系统代理), 与认证
    模块一致 —— 校园网自助服务是内网地址, 走代理反而连不上。
    """

    def __init__(self, base_url, username, password, login_type="cmcc",
                 timeout=8):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.login_type = login_type
        self.timeout = timeout
        self._opener = self._build_opener()
        self._logged_in = False

    # ---- 内部 ----
    @staticmethod
    def _build_opener():
        import http.cookiejar
        jar = http.cookiejar.CookieJar()
        handler = urllib.request.HTTPCookieProcessor(jar)
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({}), handler)

    def _request(self, url, data=None, method=None, timeout=None):
        """统一请求: 返回 (status, bytes)。失败抛 SelfServiceError。"""
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/137.0.0.0 Safari/537.36"),
                "Referer": self.base_url + "/",
            })
        if method:
            req.get_method = lambda: method
        try:
            with self._opener.open(req, timeout=timeout or self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            raise SelfServiceError("请求自助服务失败: %s" % e)

    def _full_username(self):
        suffix = common.SUFFIX.get(self.login_type, "@cmcc")
        return self.username + suffix

    # ---- 登录 ----
    def login(self):
        """登录自助服务系统。成功返回 True。"""
        uname = self._full_username()
        for path in LOGIN_ENDPOINTS:
            url = self.base_url + path
            # 两种字段名组合都试
            for uf, pf in ((LOGIN_USER_FIELD, LOGIN_PASS_FIELD),
                           (LOGIN_USER_ALT, LOGIN_PASS_ALT)):
                try:
                    status, body = self._request(
                        url, {uf: uname, pf: self.password})
                except SelfServiceError:
                    continue
                text = auth.decode_gbk(body)
                if self._is_logged_in(status, text):
                    self._logged_in = True
                    return True
        return False

    @staticmethod
    def _is_logged_in(status, text):
        """判定登录是否成功 (宽松启发式)。"""
        lowered = (text or "").lower()
        # 成功登录后页面通常不再出现"登录"表单, 而出现账号信息 / 在线列表
        # 或跳转。出现明确失败字样的先排除。
        for bad in ("密码错误", "用户名", "账号不存在", "密码不正确",
                    "login failed", "invalid password", "用户不存在"):
            if bad in text:
                return False
        # 出现账号/在线语义即认为成功
        for good in ("在线", "注销", "退出", "selfservice", "online",
                     "用户信息", "账号信息"):
            if good in lowered:
                return True
        return False

    # ---- 在线设备列表 ----
    def list_online_devices(self):
        """拉取在线设备/会话列表。

        返回 list[dict], 每项至少含:
          {"id": ..., "name": ..., "ip": ..., "mac": ..., "time": ...,
           "_raw": <原始文本片段>}
        解析不到就返回空列表(不抛错), 由调用方判断。
        """
        if not self._logged_in:
            # 惰性登录
            if not self.login():
                raise SelfServiceError("自助服务登录失败, 请检查账号密码")
        for path in DEVICE_ENDPOINTS:
            try:
                status, body = self._request(self.base_url + path)
            except SelfServiceError:
                continue
            text = auth.decode_gbk(body)
            devices = self._parse_devices(text)
            if devices:
                return devices
        return []

    @staticmethod
    def _parse_devices(text):
        """从 HTML/JSON 文本里宽松解析设备列表。

        Dr.COM 自助服务在线列表常见两种形态:
          1) HTML <table> 行, 每行一个会话 (IP/MAC/登录时间)。
          2) JSON (可能是裸数组或包在 result/rows 字段里)。
        这里做"能解多少算多少"的解析, 并把原始片段挂在 _raw 上,
        供后续在真实环境校准。
        """
        devices = []
        # --- 尝试 JSON ---
        stripped = text.strip()
        if stripped.startswith(("{", "[")):
            try:
                data = json.loads(stripped)
                rows = None
                if isinstance(data, list):
                    rows = data
                elif isinstance(data, dict):
                    rows = (data.get("rows") or data.get("data")
                            or data.get("list") or data.get("result")
                            or data.get("onlineList") or data.get("devices"))
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        devices.append({
                            "id": str(row.get("id") or row.get("sessionId")
                                      or row.get("onlineId") or ""),
                            "name": row.get("name") or row.get("deviceName") or "",
                            "ip": row.get("ip") or row.get("ipAddr") or "",
                            "mac": row.get("mac") or row.get("macAddr") or "",
                            "time": row.get("loginTime") or row.get("time") or "",
                            "_raw": json.dumps(row, ensure_ascii=False),
                        })
                    if devices:
                        return devices
            except Exception:
                pass
        # --- 尝试 HTML 表格行 ---
        # 匹配 <tr> ... </tr>, 内含至少一个 IP 形状的字段
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            if not cells:
                continue
            joined = " | ".join(cells)
            ip = next((c for c in cells
                       if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", c)), "")
            mac = next((c for c in cells
                        if re.match(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$", c)), "")
            if not ip and not mac:
                continue
            devices.append({
                "id": cells[0] if cells else "",
                "name": cells[1] if len(cells) > 1 else "",
                "ip": ip,
                "mac": mac,
                "time": "",
                "_raw": joined,
            })
        return devices

    # ---- 踢下线 / 解除绑定 ----
    def kick_device(self, device):
        """对指定设备执行强制下线/解除绑定。成功返回 True。"""
        if not self._logged_in:
            if not self.login():
                raise SelfServiceError("自助服务登录失败, 请检查账号密码")
        # 提取会话标识
        session_id = ""
        for key in KICK_SESSION_FIELDS:
            if device.get(key):
                session_id = str(device.get(key))
                break
        if not session_id:
            # 退而求其次用 IP 或 MAC
            session_id = device.get("ip") or device.get("mac") or device.get("id") or ""
        if not session_id:
            raise SelfServiceError("无法确定要下线的设备标识")
        for path in KICK_ENDPOINTS:
            url = self.base_url + path
            for payload in ({KICK_SESSION_FIELDS[0]: session_id},
                            {KICK_SESSION_FIELDS[2]: session_id},
                            {"id": session_id},
                            {"uid": session_id}):
                try:
                    status, body = self._request(url, data=payload)
                except SelfServiceError:
                    continue
                text = auth.decode_gbk(body)
                if self._is_kick_success(status, text, session_id):
                    return True
        raise SelfServiceError("下线请求已发出但未确认成功, 请到自助系统页面核对")

    @staticmethod
    def _is_kick_success(status, text, session_id):
        lowered = (text or "").lower()
        for good in ("成功", "ok", "success", "已下线", "已解除", "下线成功"):
            if good in lowered:
                return True
        # 200 且响应里不再包含该会话标识, 视为可能成功
        if status == 200 and session_id and session_id not in text:
            return True
        return False


# ---------------------------------------------------------------------------
# 便捷函数 (供 GUI / 守护调用)
# ---------------------------------------------------------------------------
def discover_selfservice_url(auth_url):
    """由认证地址推导自助服务地址。返回 str 或 None。

    规则: 取认证主机, 拼上 8080/Self/。若 auth_url 本身已指向 8080 或
    已含 /Self/, 则直接沿用。
    """
    if not auth_url:
        return None
    url = auth_url.rstrip("/")
    if "8080" in url or "self" in url.lower():
        return url
    # 提取 host (含端口)
    m = re.match(r"^https?://([^/]+)", url)
    if not m:
        return None
    host = m.group(1).split(":")[0]  # 去掉已有端口
    return "http://%s:%s%s" % (host, SELF_PORT, SELF_PATH)


def fetch_online_devices(cfg, profile=None):
    """便捷: 用配置里的档案凭据拉取在线设备列表。

    返回 (devices, error)。devices 为 list, error 为 None 或面向用户的
    错误字符串。
    """
    profile = profile or _active_profile(cfg)
    if not profile or not profile.get("username") or not profile.get("password"):
        return [], "当前档案未填写账号密码, 无法登录自助服务"
    base = discover_selfservice_url(
        profile.get("auth_url", common.DEFAULT_AUTH_URL))
    if not base:
        return [], "无法确定自助服务地址"
    try:
        client = SelfServiceClient(
            base, profile["username"], profile["password"],
            login_type=profile.get("login_type", "cmcc"))
        devices = client.list_online_devices()
        return devices, None
    except SelfServiceError as e:
        return [], str(e)
    except Exception as e:
        return [], "自助服务异常: %s" % e


def kick_device(cfg, device, profile=None):
    """便捷: 用配置凭据对指定设备执行下线。返回 (ok, error)。"""
    profile = profile or _active_profile(cfg)
    if not profile or not profile.get("username") or not profile.get("password"):
        return False, "当前档案未填写账号密码, 无法登录自助服务"
    base = discover_selfservice_url(
        profile.get("auth_url", common.DEFAULT_AUTH_URL))
    if not base:
        return False, "无法确定自助服务地址"
    try:
        client = SelfServiceClient(
            base, profile["username"], profile["password"],
            login_type=profile.get("login_type", "cmcc"))
        ok = client.kick_device(device)
        return ok, (None if ok else "下线未确认成功")
    except SelfServiceError as e:
        return False, str(e)
    except Exception as e:
        return False, "自助服务异常: %s" % e


def list_devices(cfg, profile=None):
    """list_online_devices 的别名 (供 CLI 使用)。"""
    return fetch_online_devices(cfg, profile)


def _active_profile(cfg):
    name = cfg.get("active_profile")
    for p in cfg.get("profiles", []):
        if p.get("name") == name:
            return p
    return cfg.get("profiles", [None])[0] if cfg.get("profiles") else None
