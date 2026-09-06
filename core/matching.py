# -*- coding: utf-8 -*-
"""档案匹配与校园网环境判定 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import auth  # noqa: F401

__all__ = ['profile_has_credentials', 'profile_is_wifi', 'is_campus_locked', 'best_match_profile', 'match_profile']

def profile_has_credentials(profile):
    """档案是否已填写账号密码 (具备登录能力)。"""
    return bool(profile and profile.get("username") and profile.get("password"))


def profile_is_wifi(profile):
    """档案是否为"普通WiFi/热点"类型 (不登录校园网, 只检测连通性)。"""
    return bool(profile and profile.get("profile_type") == "wifi" or
                (profile and not profile.get("profile_type")
                 and not profile_has_credentials(profile) and not profile.get("auth_url")))


def is_campus_locked(profile, ssid, gw, respect_user_choice=False):
    """判断当前连接是否被校园网档案"锁定"。
    命中条件: 匹配到的档案已填账号密码且指向校园网认证地址, 且
      - SSID 精确绑定 (直连 LIDA / 中继路由器 WiFi), 或
      - 网关精确绑定 (有线接指定路由器), 或
      - 无 SSID 但用户未明确选"任意网络"的有线/其他连接。
    用于认证服务器短暂探测不到时, 不误判"非校园网"而静止休眠。

    respect_user_choice=True 时(用户明确选了「任意网络使用」的默认档案),
    绝不锁定 —— 尊重用户不绑定选择, 即使无 SSID 也不按校园网处理, 避免
    在手机热点等非校园网下被硬拉去登录校园网。"""
    profile_bound = bool(profile and profile.get("username") and profile.get("password")
                         and (profile.get("auth_url") or "").strip())
    if respect_user_choice:
        return False
    if not profile_bound:
        return False
    ssid_bound = bool(profile.get("ssid") and profile.get("ssid") == ssid)
    gw_bound = bool(profile.get("gateway") and profile.get("gateway") == gw)
    return bool(ssid_bound or gw_bound or not ssid)


def best_match_profile(cfg, ssid, gateway=None, auth_url=None):
    """返回当前环境下的"最优匹配"档案 (用于智能自动切换)。
    匹配优先级: SSID 精确匹配 > 网关精确匹配 > 认证可达的有账号校园网档案。
    返回 (profile, reason); reason 描述匹配原因; 无匹配返回 (None, None)。
    注意: 仅当匹配是"明确"的(精确SSID/网关, 或认证服务器可达的校园网)才建议切换,
    避免在家 WiFi 场景被误切到校园网档案。"""
    profiles = cfg.get("profiles", [])
    # 1. SSID 精确匹配
    if ssid:
        for p in profiles:
            if p.get("ssid") and p["ssid"] == ssid:
                return p, "SSID 精确匹配「%s」" % ssid
    # 2. 网关精确匹配 (有线接固定路由器)
    if gateway:
        for p in profiles:
            if p.get("gateway") and p["gateway"] == gateway:
                return p, "网关精确匹配 %s" % gateway
    # 3. 认证服务器可达且在校园网: 用"认证可达"判定, 匹配任何指向该认证服务器的有账号校园网档案。
    #    覆盖无SSID的有线接路由器(中继)场景 —— 此时SSID为None无法精确匹配, 但认证可达即校园网。
    if auth_url and auth.auth_reachable(auth_url):
        for p in profiles:
            if (profile_has_credentials(p) and p.get("auth_url") == auth_url
                    and p.get("ssid") and p["ssid"] != ssid):
                # 有SSID绑定但不匹配当前SSID: 仅当当前确实无法精确匹配时才选择
                if not ssid:
                    return p, "检测到校园网认证可用（%s），自动选用档案「%s」" % (
                        ssid or "有线/经路由器", p["name"])
        for p in profiles:
            if (profile_has_credentials(p) and p.get("auth_url") == auth_url
                    and not p.get("ssid")):
                return p, "检测到校园网认证可用，切到档案「%s」" % p["name"]
    return None, None


def match_profile(cfg, ssid, gateway=None, respect_user_choice=False):
    """匹配档案: SSID 精确匹配 > 网关精确匹配(有线) > 默认档案 > 首个有账号档案。

    respect_user_choice=True 时(用户明确选了「任意网络使用」的默认档案), 即使该默认档案
    没有账号, 也返回它本身, 绝不回退到其他有账号的校园网档案 —— 尊重用户"不绑定"的选择,
    避免选了任意网络却被硬用立达账号登录并显示校园网环境。
    """
    profiles = cfg.get("profiles", [])
    if ssid:
        for p in profiles:
            if p.get("ssid") and p["ssid"] == ssid:
                return p
    if gateway:
        for p in profiles:
            if p.get("gateway") and p["gateway"] == gateway:
                return p
    # ---- 活跃档案优先 (根治: 空绑定默认档案抢用用户显式选择) ----
    # 无 SSID/网关精确匹配后, 若用户显式选中的档案(下拉框激活)本身可登录
    # (有凭据 + 指向认证服务器), 则代表用户当前意图 —— 例如用手机热点/中继
    # 接入校园网时 SSID 与档案绑定的 LIDA-UNIVERSITY 不一致, 但用户就是想让
    # 这个账号登录。历史上此处会被"SSID/网关全空的默认档案"先抢走,
    # 导致用错档案登录(陆冠霖的热点事故)。
    active = next((p for p in profiles if p.get("name") == cfg.get("active_profile")), None)
    if active and profile_has_credentials(active) and (active.get("auth_url") or "").strip():
        return active
    # 默认档案: ssid / gateway 均为空
    for p in profiles:
        if not p.get("ssid") and not p.get("gateway"):
            # 尊重用户选择: 选了「任意网络」就用它本身, 不回退
            if respect_user_choice:
                return p
            # 否则: 若该默认档案没有账号, 且存在有账号的校园网档案, 则优先用后者
            if not profile_has_credentials(p):
                with_account = next((x for x in profiles
                                     if profile_has_credentials(x)
                                     and x.get("auth_url") == p.get("auth_url")), None)
                if with_account:
                    return with_account
            return p
    return profiles[0] if profiles else None
