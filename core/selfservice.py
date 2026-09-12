# -*- coding: utf-8 -*-
"""Dr.COM 哆点 ePortal 在线设备管理客户端。

v5.2.2 重写。原实现猜 Dr.COM 用户自助服务系统挂在 ``8080/Self/``, 但立达学院
认证服务器(192.168.16.3) 只开了 80(登录页) 和 801(ePortal 门户) 两个端口,
8080 未开、自助服务系统未部署 —— 于是"刷新设备列表"全部请求都连不上, 被误报成
"自助服务登录失败, 请检查账号密码"。

实测校准后的真实数据源 (Dr.COM 哆点 ePortal 用户门户, 无需登录自助服务):

  1. 在线设备列表  GET  http://<auth-host>:801/eportal/portal/online_list
       参数: user_account = 账号@运营商后缀 (如 24012752@cmcc)
       返回: JSONP ``dr1003({"result":1,"list":[...],"total":N})``,
       每项含 online_session / online_ip / online_mac / dhcp_host(设备名,
       如 MiWiFi-RD08) / online_time / time_long(在线秒数) / uplink_bytes /
       downlink_bytes / device_alias / is_owner_ip。
       实测仅 user_account 一个参数即返回完整列表(密码/MAC/IP 均可缺省)。

  2. 注销(踢下线)  GET  http://<auth-host>:801/eportal/portal/logout
       参数: user_account (必填)。
       **行为**: 注销"请求源 IP"对应的会话 —— 即本机/路由器出口自己。实测传入
       online_session=999999(无效会话) 依然返回成功且注销的是源 IP 会话, 说明
       该接口不支持按会话远程下线其他设备。因此"解除绑定其他设备"在当前部署下
       用户侧无法实现, 只能注销自己。

  3. 当前会话状态  GET  http://<auth-host>/drcom/chkstatus
       返回: result(1=在线) / uid / v4ip(出口IP) / ss4(会话MAC)。

所有请求必须走物理网卡(复用 auth.http_get physical=True), 否则 VPN 抢默认路由
时访问校园网内网地址会超时(与认证模块一致)。
"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import config  # noqa: F401
from core import auth  # noqa: F401

__all__ = ['SelfServiceError', 'SelfServiceClient', 'fetch_online_devices',
           'kick_device', 'discover_selfservice_url', 'list_devices',
           'current_session']

# ---------------------------------------------------------------------------
# 端点常量 (实测校准, 按学校实际部署微调这些即可)
# ---------------------------------------------------------------------------
EPORTAL_PORT = "801"                       # ePortal 门户端口 (非 8080)
ONLINE_LIST_PATH = "/eportal/portal/online_list"
LOGOUT_PATH = "/eportal/portal/logout"
CHKSTATUS_PATH = "/drcom/chkstatus"
JSONP_CALLBACK = "dr1003"


class SelfServiceError(Exception):
    """自助服务/门户操作失败。message 面向用户, 可直接展示。"""


def _host_of(auth_url):
    m = re.match(r"^https?://([^/:]+)", (auth_url or ""))
    return m.group(1) if m else None


def _portal_base(auth_url):
    """由认证地址推导 ePortal 门户地址 http://<host>:801。"""
    host = _host_of(auth_url) or _host_of(common.DEFAULT_AUTH_URL)
    return "http://%s:%s" % (host, EPORTAL_PORT)


def _full_username(profile):
    suffix = common.SUFFIX.get(profile.get("login_type", "cmcc"), "@cmcc")
    return (profile.get("username") or "") + suffix


def _jsonp_load(text):
    """解析 JSONP: ``dr1003({...})`` 或 ``dr1003({...});`` -> dict。

    Dr.COM 实际返回 ``callback({...});`` (结尾带分号), 故不能用 ``)$`` 锚定,
    直接取第一个 ``(`` 与最后一个 ``)`` 之间的内容。失败抛 ValueError。
    """
    text = (text or "").strip()
    start = text.find("(")
    end = text.rfind(")")
    if start >= 0 and end > start:
        text = text[start + 1:end]
    return json.loads(text)


def _device_from_row(row):
    """把 online_list 返回的一行映射为统一设备 dict (供 GUI 渲染)。"""
    return {
        "id": str(row.get("online_session") or ""),
        "name": (row.get("dhcp_host") or row.get("device_alias")
                 or row.get("online_mac") or ""),
        "ip": row.get("online_ip") or "",
        "mac": row.get("online_mac") or "",
        "time": row.get("online_time") or "",
        "duration": row.get("time_long") or "",
        "uplink": row.get("uplink_bytes") or "",
        "downlink": row.get("downlink_bytes") or "",
        "_raw": json.dumps(row, ensure_ascii=False),
    }


class SelfServiceClient:
    """Dr.COM ePortal 门户客户端 (v5.2.2: 直接调门户接口, 无需登录自助服务)。"""

    def __init__(self, auth_url, username, password, login_type="cmcc",
                 timeout=8):
        self.auth_url = auth_url or common.DEFAULT_AUTH_URL
        self.username = username or ""
        self.password = password or ""
        self.login_type = login_type
        self.timeout = timeout
        self.portal_base = _portal_base(self.auth_url)

    def _get_jsonp(self, url, params):
        """GET 并解析 JSONP。失败抛 SelfServiceError。"""
        query = urllib.parse.urlencode(params)
        url = "%s?%s" % (url, query)
        try:
            status, body = auth.http_get(url, timeout=self.timeout, physical=True)
        except Exception as e:
            raise SelfServiceError("请求校园网门户失败: %s" % e)
        text = body.decode("utf-8", errors="replace")
        try:
            return _jsonp_load(text)
        except Exception:
            raise SelfServiceError("校园网门户返回无法解析: %s" % text[:120])

    # ---- 在线设备列表 ----
    def list_online_devices(self):
        """拉取当前账号的在线设备/会话列表。返回 list[dict]。"""
        url = self.portal_base + ONLINE_LIST_PATH
        data = self._get_jsonp(url, {
            "callback": JSONP_CALLBACK,
            "user_account": self.username + common.SUFFIX.get(self.login_type,
                                                              "@cmcc"),
        })
        if not isinstance(data, dict):
            return []
        rows = data.get("list") or []
        return [_device_from_row(r) for r in rows if isinstance(r, dict)]

    # ---- 当前会话 ----
    def current_session(self):
        """chkstatus 查询当前出口会话。返回 dict 或 None。

        返回字段: {"ip": v4ip, "mac": ss4, "uid": uid, "online": bool}
        """
        host = _host_of(self.auth_url) or _host_of(common.DEFAULT_AUTH_URL)
        url = "http://%s%s" % (host, CHKSTATUS_PATH)
        data = self._get_jsonp(url, {"callback": JSONP_CALLBACK, "_": str(int(time.time()))})
        if not isinstance(data, dict):
            return None
        return {
            "ip": data.get("v4ip") or data.get("ss5") or "",
            "mac": data.get("ss4") or "",
            "uid": data.get("uid") or data.get("AC") or "",
            "online": data.get("result") == 1,
        }

    # ---- 注销 / 踢下线 ----
    def logout(self):
        """注销"当前设备"(请求源 IP = 本机/路由器出口)的会话。返回 (ok, msg)。"""
        url = self.portal_base + LOGOUT_PATH
        data = self._get_jsonp(url, {
            "callback": JSONP_CALLBACK,
            "user_account": self.username + common.SUFFIX.get(self.login_type,
                                                              "@cmcc"),
        })
        msg = str(data.get("msg") or "") if isinstance(data, dict) else ""
        ok = (isinstance(data, dict) and data.get("result") == 1
              and "成功" in msg)
        return ok, (msg or ("已注销" if ok else "注销未确认成功"))


# ---------------------------------------------------------------------------
# 便捷函数 (供 GUI / 守护调用)
# ---------------------------------------------------------------------------
def discover_selfservice_url(auth_url):
    """返回 ePortal 门户地址 http://<host>:801 (供展示/调试)。"""
    if not auth_url:
        return None
    return _portal_base(auth_url)


def _profile_of(cfg, profile):
    if profile is not None:
        return profile
    name = cfg.get("active_profile")
    for p in cfg.get("profiles", []):
        if p.get("name") == name:
            return p
    if cfg.get("profiles"):
        return cfg["profiles"][0]
    return None


def _client(cfg, profile):
    profile = _profile_of(cfg, profile)
    if not profile or not profile.get("username"):
        return None, "当前档案未填写账号, 无法查询在线设备"
    return SelfServiceClient(
        profile.get("auth_url", common.DEFAULT_AUTH_URL),
        profile["username"], profile.get("password", ""),
        login_type=profile.get("login_type", "cmcc")), None


def fetch_online_devices(cfg, profile=None):
    """便捷: 用配置档案凭据拉取在线设备列表。返回 (devices, error)。"""
    client, err = _client(cfg, profile)
    if err:
        return [], err
    try:
        return client.list_online_devices(), None
    except SelfServiceError as e:
        return [], str(e)
    except Exception as e:
        return [], "查询在线设备异常: %s" % e


def current_session(cfg, profile=None):
    """便捷: 用 chkstatus 查询当前出口会话。返回 (session_dict, error)。"""
    client, err = _client(cfg, profile)
    if err:
        return None, err
    try:
        return client.current_session(), None
    except SelfServiceError as e:
        return None, str(e)
    except Exception as e:
        return None, "查询当前会话异常: %s" % e


def kick_device(cfg, device, profile=None):
    """便捷: 对指定设备执行下线。返回 (ok, error)。

    说明: 当前部署下 logout 只能注销"请求源 IP"(本机/路由器)的会话, 无法远程
    下线其他设备。因此本函数对"其他设备"直接返回明确错误, 不误导用户。
    """
    client, err = _client(cfg, profile)
    if err:
        return False, err
    try:
        sess = client.current_session()
        dev_ip = str(device.get("ip") or "")
        # 仅当目标 IP 等于当前出口 IP 时, logout 才会真正作用于它; 否则提示不支持。
        if sess and sess.get("ip") and dev_ip and dev_ip == sess["ip"]:
            ok, msg = client.logout()
            return ok, (None if ok else msg)
        return False, "学校门户仅支持注销本机/路由器自己的会话, 无法远程下线其他设备"
    except SelfServiceError as e:
        return False, str(e)
    except Exception as e:
        return False, "下线操作异常: %s" % e


def list_devices(cfg, profile=None):
    """list_online_devices 的别名 (供 CLI 使用)。"""
    return fetch_online_devices(cfg, profile)
