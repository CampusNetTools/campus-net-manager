# -*- coding: utf-8 -*-
"""保活守护线程 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import auth, config, history, matching, netinfo, sysutils  # noqa: F401

__all__ = ['KeepAliveDaemon']

class KeepAliveDaemon(threading.Thread):
    def __init__(self, cfg, on_log=None, on_status=None, on_env=None, on_alert=None):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.on_log = on_log
        self.on_status = on_status      # callable(online, authed, last_check)
        self.on_env = on_env            # callable(mode, ssid, gw, profile_name, in_campus)
        self.on_alert = on_alert        # callable(text) 掉线/重登/失败通知
        self._stop = threading.Event()
        self.last_check = ""
        self._in_campus = None      # 最近一次环境判定 (None=未知, True=校园网, False=非校园网)
        self._user_any_network = False
        self._consecutive_errors = 0    # 守护循环连续异常计数 (健康循环后清零)
        self._error_alerted = False     # 本轮连续异常是否已告警过 (避免重复通知)

    def stop(self):
        self._stop.set()

    def _log(self, msg):
        line = sysutils.log(msg)
        if self.on_log:
            try:
                self.on_log(line)
            except Exception:
                pass

    def _safe_callback(self, cb, *args):
        """界面回调保护: 回调(GUI/测试 lambda)抛错不应被守护兜底误记为守护异常,
        记录日志后继续, 避免污染连续异常计数。回调签名变更时此处日志能立即暴露问题。"""
        try:
            cb(*args)
        except Exception as cb_err:
            sysutils.log("界面回调异常(已忽略, 请检查回调签名): %s" % cb_err)

    def _alert(self, text, category="failure"):
        if self.on_alert:
            try:
                self.on_alert(text, category)
            except Exception:
                pass

    def _check_and_publish_status(self, auth_url):
        """完成一次联网检查，并把结果同步给顶部状态栏。"""
        authed = auth.check_auth(auth_url)
        paths = auth.check_network_paths()
        self.last_check = sysutils.now_str()
        if self.on_status:
            # 传当前环境判定, 让 GUI 区分"校园网"和"任意网络非校园网"
            self._safe_callback(self.on_status, paths, authed, self.last_check,
                                getattr(self, "_in_campus", None),
                                getattr(self, "_user_any_network", False))
        return authed, paths

    def _refresh_after_login(self, mode, ssid, gw, profile, auth_url):
        """自动登录成功后立即复检，避免界面一直显示登录前的掉线状态。"""
        if self.on_env:
            self._safe_callback(self.on_env, mode, ssid, gw, profile["name"], True)
        authed, paths = self._check_and_publish_status(auth_url)
        if not authed and not self._stop.wait(2):
            authed, paths = self._check_and_publish_status(auth_url)
        return authed, paths

    def _wait_or_break(self, seconds, ref_fp=None):
        """分段等待: 每 60s 醒来检查一次连接指纹(SSID/网关)是否变化,
        网络切换/电脑唤醒后网络恢复时提前结束等待立即检测。
        返回 True = 应退出守护。"""
        waited = 0
        while waited < seconds:
            chunk = min(60, seconds - waited)
            if self._stop.wait(chunk):
                return True
            waited += chunk
            try:
                mode, ssid = netinfo.get_connection_mode()
                gw = netinfo.get_gateway()
                if ref_fp and (mode, ssid, gw) != ref_fp:
                    return False  # 网络变化 → 提前进入下一轮完整检测
            except Exception:
                pass
        return False

    def run(self):
        self._log("=" * 56)
        self._log("校园网连接管家守护启动")
        while not self._stop.is_set():
            try:
                mode, ssid = netinfo.get_connection_mode()
                gw = netinfo.get_gateway()
                fp = (mode, ssid, gw)
                # 尊重用户"任意网络"选择: 若当前激活档案是空账号的默认档案(SSID/网关留空),
                # 说明用户明确不想绑定特定网络 —— 不自动回退到其他校园网档案, 也不强制锁定为校园网。
                active_name = self.cfg.get("active_profile")
                active_prof = next((p for p in self.cfg.get("profiles", []) if p.get("name") == active_name), None)
                user_any_network = bool(
                    active_prof and not active_prof.get("ssid") and not active_prof.get("gateway")
                    and not matching.profile_has_credentials(active_prof))
                profile = matching.match_profile(self.cfg, ssid, gw,
                                        respect_user_choice=user_any_network)
                auth_url = profile.get("auth_url", common.DEFAULT_AUTH_URL) if profile else common.DEFAULT_AUTH_URL

                # 环境判定: 认证服务器可达 = 校园网环境; 不可达 = 非校园网。
                in_campus = auth.auth_reachable(auth_url)
                # --- 增强: 中继/直连校园网场景, 认证服务器可能暂时探测不到(如路由器链路抖动、
                # 交换机短暂隔离、有线接路由器时物理网卡探测超时), 但只要当前连接被"校园网档案
                # 锁定"(用户明确在该网络配过账号), 仍视为校园网环境进入检测并尝试重登。
                # 若用户选了「任意网络使用」, 则不锁定、不自动重登, 保持中立。
                if not in_campus and matching.is_campus_locked(profile, ssid, gw,
                                                      respect_user_choice=user_any_network):
                    self._log("认证服务器暂时不可达, 但处于校园网档案 [%s] 环境 (%s), 按校园网处理 (尝试检测/重登)"
                              % (profile["name"], ssid or ("有线/网关 " + (gw or "?"))))
                    in_campus = True
                if self.on_env:
                    self._safe_callback(self.on_env, mode, ssid, gw,
                                        profile["name"] if profile else None, in_campus)
                # 记住当前环境判定, 供顶部状态栏显示(区分校园网/任意网络非校园网)
                self._in_campus = in_campus
                self._user_any_network = user_any_network

                # --- 智能档案自动切换 ---
                # 若用户当前选的档案不匹配当前环境(可能误选「任意网络」/选错), 但存在
                # 明确匹配的档案(SSID/网关精确匹配, 或认证可达的校园网档案), 自动切换过去。
                best, reason = matching.best_match_profile(self.cfg, ssid, gw, auth_url)
                current_prof = next((p for p in self.cfg.get("profiles", [])
                                     if p.get("name") == self.cfg.get("active_profile")), None)
                if best and current_prof and best.get("name") != current_prof.get("name"):
                    self.cfg["active_profile"] = best["name"]
                    try:
                        config.save_config(self.cfg)
                    except Exception:
                        pass
                    self._log("检测到%s, 已自动切换到档案「%s」" % (reason, best["name"]))
                    self._alert("检测到%s，已自动切换到档案「%s」" % (reason, best["name"]), "device")
                    # 切换后重新走一轮完整检测(用新档案)
                    if self._wait_or_break(5, fp):
                        break
                    continue

                # --- 普通WiFi/热点档案: 不登录校园网, 但持续检测连通性, 断网通知用户 ---
                if profile and matching.profile_is_wifi(profile):
                    self._log("普通WiFi档案「%s」(%s): 不登录校园网, 检测网络连通性"
                              % (profile["name"], ssid or ("有线/网关 " + (gw or "?"))))
                    # 检测外网可达性 (用系统路径, 不强制物理网卡)
                    if not auth.check_internet(physical=False):
                        self._log("⚠️ 检测到断网 (%s), 通知用户" % (ssid or (gw or "?")))
                        history.record_network_history(self.cfg, "disconnect", "WiFi断网", profile=profile["name"])
                        self._alert("检测到断网：当前网络（%s）无法上网，请检查手机热点/路由器"
                                    % (ssid or (gw or "?")), "disconnect")
                    else:
                        self._log("网络正常 (%s)" % (ssid or (gw or "?")))
                    self._consecutive_errors = 0
                    self._error_alerted = False
                    if self._wait_or_break(30, fp):
                        break
                    continue

                # 用户明确选了「任意网络使用」: 无论认证服务器探测结果如何, 一律视为非校园网,
                # 直接休眠, 绝不尝试登录 —— 尊重用户选择, 避免在家 WiFi 等场景误登录。
                if user_any_network:
                    self._log("非校园网环境 (%s), 守护休眠 (任意网络档案, 不进行登录)"
                              % (ssid or ("有线/网关 " + (gw or "?"))))
                    if self._wait_or_break(30, fp):
                        break
                    continue

                if not in_campus:
                    self._log("非校园网环境%s, 守护休眠 (不进行登录)" % (" (" + ssid + ")" if ssid else " (有线/其他)"))
                    if self._wait_or_break(30, fp):
                        break
                    continue

                if profile is None:
                    self._log("校园网环境但未配置档案%s, 请在 App 中添加" % (" (" + ssid + ")" if ssid else ""))
                    if self._wait_or_break(30, fp):
                        break
                    continue

                interval = max(10, int(profile.get("interval", 60)))
                # 防踢: 会话刷新计数器 (每 interval 秒循环一次)
                if not hasattr(self, "_refresh_count"):
                    self._refresh_count = 0
                    self._kickguard = bool(self.cfg.get("kick_guard", True))
                authed, paths = self._check_and_publish_status(auth_url)
                # 一次完整检测成功 = 健康循环, 清零连续异常计数
                self._consecutive_errors = 0
                self._error_alerted = False
                campus_internet = paths["physical"] if paths["vpn"] and common.IS_MACOS else paths["current"]

                if authed and campus_internet:
                    if paths["vpn"] and not paths["current"]:
                        self._log("校园网物理出口正常，但 VPN/系统路径暂时不通；不重复登录校园网")
                        history.record_network_history(self.cfg, "vpn_issue", "校园网正常，但 VPN 暂时无法上网",
                                               profile=profile["name"])
                    else:
                        self._log("在线正常 (%s / 认证页OK+外网OK)" % profile["name"])
                        history.record_network_history(self.cfg, "online", "网络正常", profile=profile["name"])
                        # --- 防踢保活: 周期性刷新登录, 让本会话保持"最新" ---
                        # Dr.COM 名额按会话新鲜度淘汰: 第N+1台登录会挤掉最旧会话。
                        # 定期 try_login (同来源IP=刷新续期, 已实测会话IP不变) 使被保护
                        # 设备始终为最新, 新设备登录时被挤掉的是别人而不是本机/路由器。
                        self._refresh_count += 1
                        if self._kickguard and self._refresh_count >= 3:
                            self._refresh_count = 0
                            self._log("防踢保活: 刷新登录会话, 保持本设备名额最新")
                            if auth.try_login(profile):
                                self._log("会话刷新成功")
                            else:
                                self._log("会话刷新失败(不阻塞, 下轮再试)")
                elif authed and not campus_internet:
                    self._log("警告: 校园网认证在线但物理出口不通, 尝试重登...")
                    history.record_network_history(self.cfg, "disconnect", "校园网出口异常", profile=profile["name"])
                    self._alert("校园网出口异常，正在尝试恢复", "disconnect")
                    if auth.ensure_login(profile, on_log=self._log):
                        self._log("重登完成")
                        self._refresh_after_login(mode, ssid, gw, profile, auth_url)
                        history.record_network_history(self.cfg, "recovery", "网络已自动恢复", profile=profile["name"])
                        self._alert("网络已自动恢复", "recovery")
                    else:
                        reachable = auth.auth_reachable(auth_url)
                        if not reachable:
                            self._log("重登失败：认证服务器不可达。中继/路由器模式下校园网链路可能已断开，"
                                      "请重启路由器重新拨号恢复")
                            history.record_network_history(self.cfg, "failure", "校园网链路断开", profile=profile["name"])
                            self._alert("校园网链路已断开：请重启路由器恢复（电脑无法直接重连）", "failure")
                        else:
                            self._log("重登失败! 提示: 账号可能已被其他设备占用名额(校园网通常限2台), 或被服务器临时限制")
                            history.record_network_history(self.cfg, "failure", "自动恢复失败", profile=profile["name"])
                            self._alert("自动恢复失败：账号名额可能被其他设备占用，可登录自助系统处理占用设备", "failure")
                elif not authed:
                    self._log("检测到掉线 (%s), 自动登录中..." % profile["name"])
                    history.record_network_history(self.cfg, "disconnect", "检测到校园网掉线", profile=profile["name"])
                    self._alert("检测到校园网掉线，正在自动登录", "disconnect")
                    if auth.ensure_login(profile, on_log=self._log):
                        self._log("自动登录成功")
                        self._refresh_after_login(mode, ssid, gw, profile, auth_url)
                        history.record_network_history(self.cfg, "recovery", "已自动恢复连接", profile=profile["name"])
                        self._alert("已自动恢复连接", "recovery")
                    else:
                        # 区分"链路断开"(认证服务器不可达) 与 "账号问题"(可达但登录失败)
                        reachable = auth.auth_reachable(auth_url)
                        if not reachable:
                            self._log("自动登录失败：认证服务器不可达。当前处于中继/路由器模式时，"
                                      "校园网链路可能已断开，需要重启路由器重新拨号才能恢复")
                            history.record_network_history(self.cfg, "failure", "校园网链路断开", profile=profile["name"])
                            self._alert("校园网链路已断开：请重启路由器恢复（电脑无法直接重连）", "failure")
                        else:
                            self._log("自动登录失败 (稍后重试)")
                            history.record_network_history(self.cfg, "failure", "自动登录失败", profile=profile["name"])
                            self._alert("自动登录失败：请检查账号密码；若提示名额已满，需在自助系统下线其他设备", "failure")
                else:
                    self._log("异常状态")

                if self._wait_or_break(interval, fp):
                    break
            except Exception as e:
                # 兜底: 任何异常都不让守护线程退出。但连续异常多半是代码 bug(而非网络抖动),
                # 记录堆栈、超阈值告警并延长退避, 避免无声空转(历史教训: 回调签名失配曾在此死循环)。
                self._consecutive_errors += 1
                self._log("守护异常(连续第%d次): %s" % (self._consecutive_errors, e))
                if self._consecutive_errors == 1 or self._consecutive_errors % 20 == 0:
                    self._log(traceback.format_exc().rstrip())
                if self._consecutive_errors >= 5 and not self._error_alerted:
                    self._error_alerted = True
                    self._alert("守护连续异常（%s），请查看日志并重启守护；若反复出现请反馈"
                                % e, "failure")
                wait_s = 5 if self._consecutive_errors < 5 else 60
                if self._stop.wait(wait_s):
                    break
        self._log("守护已停止")
