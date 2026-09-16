# -*- coding: utf-8 -*-
"""VPN 订阅导入与路由器 mihomo 安全部署窗口。"""
import json
import threading
import tkinter as tk
from tkinter import ttk
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

import keepalive_core as core
import proxy_subscription
from gui.theme import *  # noqa: F401,F403


class SubscriptionUiMixin:
    def _subscription_settings(self):
        section = self.cfg.get("vpn_subscription") or {}
        url = ""
        if section.get("url_store") == "dpapi":
            url = core.dpapi_decrypt(section.get("url_enc", ""))
        return section, url

    def show_subscription_window(self):
        existing = getattr(self, "_subscription_window", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                return existing
        except Exception:
            pass

        win = tk.Toplevel(self)
        self._subscription_window = win
        win.title("VPN 订阅 · 安全导入")
        win.geometry("720x520")
        win.minsize(620, 440)
        win.configure(bg=BG)
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 20))
        card.pack(fill="both", expand=True, padx=18, pady=18)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(6, weight=1)

        ttk.Label(card, text="VPN 订阅安全导入", style="DialogTitle.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Label(
            card,
            text=("支持 Base64 URI 列表中的 VLESS / Hysteria2。订阅地址仅以 Windows DPAPI 密文保存；"
                  "部署时只把转换后的 mihomo 配置发送到局域网路由器，不把订阅地址写入日志。"),
            style="Muted.TLabel", wraplength=650, justify="left").grid(
                row=1, column=0, sticky="ew", pady=(8, 16))

        section, saved_url = self._subscription_settings()
        form = ttk.Frame(card, style="Inner.TFrame")
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="订阅地址", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        url_entry = ttk.Entry(form, show="●")
        url_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        url_entry.insert(0, saved_url)

        ttk.Label(form, text="路由器", style="Field.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        router_var = tk.StringVar(value=(section.get("router_host") or "192.168.31.1"))
        ttk.Entry(form, textvariable=router_var).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(10, 0))

        status_var = tk.StringVar(value="尚未校验")
        ttk.Label(card, textvariable=status_var, style="Muted.TLabel", wraplength=650,
                  justify="left").grid(row=3, column=0, sticky="ew", pady=(14, 8))

        actions = ttk.Frame(card, style="Inner.TFrame")
        actions.grid(row=4, column=0, sticky="ew")
        validate_btn = ttk.Button(actions, text="校验并加密保存", style="Gray.TButton")
        validate_btn.pack(side="left")
        deploy_btn = ttk.Button(actions, text="部署到路由器（先不透明接管）", style="Accent.TButton")
        deploy_btn.pack(side="left", padx=(8, 0))

        detail = tk.Text(card, height=12, width=1, bg="#09101c", fg="#b7c4d8",
                         font=("Microsoft YaHei UI", 10), relief="flat", wrap="word",
                         padx=12, pady=10, state="disabled")
        detail.grid(row=6, column=0, sticky="nsew", pady=(14, 0))
        state = {"nodes": None, "controller_secret": ""}

        def set_detail(text):
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            detail.insert("1.0", text)
            detail.configure(state="disabled")

        def save_url(url, router_host, summary, controller_secret=""):
            encrypted = core.dpapi_encrypt(url)
            if not encrypted:
                raise proxy_subscription.SubscriptionError("当前系统无法用 DPAPI 加密订阅地址，已拒绝明文保存")
            old = self.cfg.get("vpn_subscription") or {}
            secret_enc = old.get("controller_secret_enc", "")
            if controller_secret:
                secret_enc = core.dpapi_encrypt(controller_secret)
            self.cfg["vpn_subscription"] = {
                "url_store": "dpapi",
                "url_enc": encrypted,
                "router_host": router_host,
                "node_count": summary["node_count"],
                "protocols": summary["protocols"],
                "controller_secret_enc": secret_enc,
            }
            core.save_config(self.cfg)

        def ui(callback):
            self.after(0, callback)

        def validate_worker(url, router_host, deploy=False):
            try:
                raw = proxy_subscription.fetch_subscription(url)
                nodes, rejected = proxy_subscription.parse_subscription(raw)
                summary = proxy_subscription.subscription_summary(nodes, rejected)
                state["nodes"] = nodes
                save_url(url, router_host, summary)
                text = "校验通过：%d 个节点；协议 %s；忽略 %d 条不支持/无效记录。" % (
                    summary["node_count"], json.dumps(summary["protocols"], ensure_ascii=False), rejected)
                if not deploy:
                    ui(lambda: status_var.set(text))
                    ui(lambda: set_detail(text + "\n\n此时只保存了加密订阅，尚未改变电脑或路由器流量。"))
                    return

                config_text, controller_secret = proxy_subscription.build_mihomo_config(nodes)
                host = router_host
                console = self._rc_settings()
                token = console.get("token", "")
                if not token:
                    raise proxy_subscription.SubscriptionError("请先在“路由器后台工作台”保存控制令牌")
                payload = token.encode("utf-8") + b"\n" + config_text.encode("utf-8")
                req = urlrequest.Request(
                    "http://%s:8088/cgi-bin/proxy-config.sh" % host,
                    data=payload, method="POST",
                    headers={"Content-Type": "application/octet-stream"})
                opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
                with opener.open(req, timeout=45) as response:
                    reply = json.loads(response.read().decode("utf-8"))
                if not reply.get("ok"):
                    raise proxy_subscription.SubscriptionError(reply.get("error") or "路由器拒绝配置")
                state["controller_secret"] = controller_secret
                save_url(url, router_host, summary, controller_secret)
                self.cfg["vpn_upstream"] = {"host": host, "port": 7890, "type": "http"}
                core.save_config(self.cfg)
                ui(self._refresh_vpn_status)
                ui(lambda: status_var.set("部署成功：显式代理已验证；透明接管保持关闭"))
                ui(lambda: set_detail(text + "\n\n路由器已原子加载新配置并通过显式代理连通性测试。"
                                      "为避免断网，透明接管不会在导入时自动开启，可在路由器工作台单独启用。"))
            except (proxy_subscription.SubscriptionError, HTTPError, URLError, OSError, ValueError) as exc:
                error_text = str(exc)
                ui(lambda: status_var.set("导入失败，网络设置未改变"))
                ui(lambda: set_detail("失败：%s\n\n旧配置与当前网络保持不变。" % error_text))
            finally:
                ui(lambda: validate_btn.configure(state="normal"))
                ui(lambda: deploy_btn.configure(state="normal"))

        def start(deploy):
            url = url_entry.get().strip()
            router_host = router_var.get().strip() or "192.168.31.1"
            validate_btn.configure(state="disabled")
            deploy_btn.configure(state="disabled")
            status_var.set("正在下载并校验（不会记录订阅内容）…")
            threading.Thread(target=validate_worker, args=(url, router_host, deploy), daemon=True).start()

        validate_btn.configure(command=lambda: start(False))
        deploy_btn.configure(command=lambda: start(True))
        return win
