# -*- coding: utf-8 -*-
"""v5.4.2 「Clash 节点管理」测试。

覆盖三块:
  - core.clash_api 的纯逻辑(节点过滤/协议归一/排序/编码), 不依赖 tkinter
  - relay_request 的请求封装(打桩 urlopen, 校验 CGI 二次编码与 base64 节点名)
  - proxy_subscription 的协议过滤(「切换协议」在部署侧生效)
  - GUI 源码断言(读文件而非导入, 避免无 tkinter 环境跑不了)
"""
import base64
import json
import os
import sys
import unittest
from urllib.error import URLError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import proxy_subscription as sub
from core import clash_api as clash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status

    def read(self, *_a):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class FakeOpener:
    def __init__(self, body, recorder, status=200):
        self.body, self.recorder, self.status = body, recorder, status

    def open(self, req, timeout=None):
        self.recorder.append(req)
        return FakeResponse(self.body, self.status)


class TestNodeFilters(unittest.TestCase):
    def test_pseudo_and_info(self):
        self.assertTrue(clash.is_pseudo_node("DIRECT"))
        self.assertTrue(clash.is_pseudo_node("自动选择"))
        self.assertFalse(clash.is_pseudo_node("🇯🇵AWS日本09 | 电信移动联通推荐"))
        self.assertTrue(clash.is_info_node("剩余流量：99.89 GB"))
        self.assertTrue(clash.is_info_node("距离下次重置剩余：12 天"))
        self.assertFalse(clash.is_info_node("🇯🇵AWS日本09"))
        self.assertFalse(clash.is_real_node("REJECT"))
        self.assertFalse(clash.is_real_node("套餐到期：2026-09-28"))
        self.assertTrue(clash.is_real_node("🇯🇵AWS日本09"))

    def test_protocol_label(self):
        self.assertEqual("VLESS", clash.protocol_label("vless"))
        self.assertEqual("Hysteria2", clash.protocol_label("Hysteria2"))
        self.assertEqual("UNKNOWNX", clash.protocol_label("unknownx"))
        self.assertEqual("未知", clash.protocol_label(""))


class TestGroupParsing(unittest.TestCase):
    def setUp(self):
        self.group = {"all": ["自动选择", "故障转移", "剩余流量：1 GB", "A", "B"],
                      "now": "B", "type": "Selector"}
        self.proxies = {
            "A": {"type": "vless", "alive": True,
                  "history": [{"time": "t1", "delay": 0}, {"time": "t2", "delay": 320}]},
            "B": {"type": "hysteria2", "alive": True, "history": []},
        }

    def test_selection_and_members(self):
        self.assertEqual("B", clash.selection_now(self.group))
        self.assertEqual("", clash.selection_now({}))
        self.assertEqual(5, len(clash.group_members(self.group)))
        self.assertEqual([], clash.group_members(None))

    def test_last_delay(self):
        self.assertEqual(320, clash.last_delay(self.proxies["A"]))
        self.assertIsNone(clash.last_delay(self.proxies["B"]))
        self.assertIsNone(clash.last_delay({"history": [{"delay": 0}]}))
        self.assertIsNone(clash.last_delay({"history": [{"delay": "x"}]}))
        self.assertIsNone(clash.last_delay(None))

    def test_build_nodes_filters_and_marks_current(self):
        nodes = clash.build_nodes(self.proxies, self.group)
        self.assertEqual(["A", "B"], [n["name"] for n in nodes])
        self.assertEqual(["VLESS", "Hysteria2"], [n["proto"] for n in nodes])
        self.assertEqual(320, nodes[0]["delay"])
        self.assertFalse(nodes[0]["current"])
        self.assertTrue(nodes[1]["current"])

    def test_sort_and_fastest(self):
        nodes = [{"name": "slow", "delay": 900, "alive": True},
                 {"name": "fast", "delay": 120, "alive": True},
                 {"name": "unknown", "delay": None, "alive": True}]
        self.assertEqual(["fast", "slow", "unknown"],
                         [n["name"] for n in clash.sort_nodes(nodes)])
        self.assertEqual("fast", clash.fastest_node(nodes)["name"])
        self.assertIsNone(clash.fastest_node([{"name": "x", "delay": None, "alive": True}]))

    def test_format_delay(self):
        self.assertEqual("—", clash.format_delay(None))
        self.assertEqual("312 ms", clash.format_delay(312))
        self.assertEqual("1.5 s", clash.format_delay(1500))

    def test_throughput(self):
        self.assertEqual(40.0, clash.throughput_mbps(5_000_000, 1.0))
        self.assertEqual(0.0, clash.throughput_mbps(0, 3))
        self.assertEqual(0.0, clash.throughput_mbps(100, 0))


class TestRelayEncoding(unittest.TestCase):
    def test_path_is_percent_encoded_but_keeps_slash(self):
        enc = clash._encode_path("proxies/节点选择")
        self.assertTrue(enc.startswith("proxies/"))
        self.assertNotIn("节", enc)
        self.assertEqual("proxies/%E8%8A%82%E7%82%B9%E9%80%89%E6%8B%A9", enc)

    def test_relay_body_is_ascii_json_with_base64_name(self):
        raw = clash._relay_body("tok", "proxies/节点选择", "PUT", "🇯🇵AWS日本09")
        text = raw.decode("ascii")                     # 必须全 ASCII
        payload = json.loads(text)
        self.assertEqual("tok", payload["token"])
        self.assertEqual("PUT", payload["method"])
        self.assertEqual("proxies/%E8%8A%82%E7%82%B9%E9%80%89%E6%8B%A9", payload["path"])
        self.assertEqual("🇯🇵AWS日本09",
                         base64.b64decode(payload["name_b64"]).decode("utf-8"))

    def test_get_has_no_name_field(self):
        payload = json.loads(clash._relay_body("t", "version", "GET").decode("ascii"))
        self.assertNotIn("name_b64", payload)


class TestRelayRequest(unittest.TestCase):
    def _patch(self, body, status=200):
        sent = []
        original = clash.urlrequest.build_opener
        clash.urlrequest.build_opener = lambda *_a, **_k: FakeOpener(body, sent, status)
        self.addCleanup(lambda: setattr(clash.urlrequest, "build_opener", original))
        return sent

    def test_success_and_error_mapping(self):
        sent = self._patch('{"version":"v1.19.30"}')
        data = clash.relay_request("192.168.31.1", "8088", "tok", "version")
        self.assertEqual("v1.19.30", data["version"])
        self.assertEqual(1, len(sent))
        self.assertEqual("POST", sent[0].method)
        self.assertIn(b"/cgi-bin/proxy-api.sh", sent[0].full_url.encode())
        sent.clear()

        self._patch('{"ok":false,"msg":"令牌错误"}')
        with self.assertRaises(clash.ClashApiError) as ctx:
            clash.relay_request("h", "p", "bad", "version")
        self.assertIn("令牌错误", str(ctx.exception))

        self._patch("not json")
        with self.assertRaises(clash.ClashApiError):
            clash.relay_request("h", "p", "t", "version")

        self._patch("")
        self.assertEqual({}, clash.relay_request("h", "p", "t", "version"))

    def test_network_failure_is_wrapped(self):
        def boom(*_a, **_k):
            raise URLError("unreachable")
        original = clash.urlrequest.build_opener
        clash.urlrequest.build_opener = boom
        self.addCleanup(lambda: setattr(clash.urlrequest, "build_opener", original))
        with self.assertRaises(clash.ClashApiError):
            clash.relay_request("h", "p", "t", "version")

    def test_api_select_sends_base64_name(self):
        sent = self._patch("{}")
        clash.api_select("h", "8088", "t", "🇯🇵AWS日本09")
        body = json.loads(sent[0].data.decode("ascii"))
        self.assertEqual("PUT", body["method"])
        self.assertEqual("proxies/%E8%8A%82%E7%82%B9%E9%80%89%E6%8B%A9", body["path"])

    def test_api_delay_returns_none_on_error(self):
        self._patch('{"message":"timeout"}')
        self.assertIsNone(clash.api_delay("h", "8088", "t", "node"))
        self._patch('{"delay":233}')
        self.assertEqual(233, clash.api_delay("h", "8088", "t", "node"))


class TestProtocolSwitchInSubscription(unittest.TestCase):
    NODES = [
        {"name": "v1", "type": "vless"},
        {"name": "h1", "type": "hysteria2"},
        {"name": "v2", "type": "vless"},
    ]

    def test_filter_by_protocols(self):
        self.assertEqual(["v1", "v2"], [n["name"] for n in
                                        sub.filter_by_protocols(self.NODES, ["vless"])])
        self.assertEqual(["h1"], [n["name"] for n in
                                  sub.filter_by_protocols(self.NODES, ["HYSTERIA2"])])
        self.assertEqual(3, len(sub.filter_by_protocols(self.NODES, None)))
        self.assertEqual(3, len(sub.filter_by_protocols(self.NODES, [])))

    def test_build_config_respects_protocol_selection(self):
        config, _secret = sub.build_mihomo_config(self.NODES, "s", allow_types=["vless"])
        self.assertIn('"v1"', config)
        self.assertNotIn('"h1"', config)

    def test_build_config_rejects_empty_selection(self):
        with self.assertRaises(sub.SubscriptionError):
            sub.build_mihomo_config(self.NODES, "s", allow_types=["trojan"])

    def test_build_config_backward_compatible(self):
        config, _secret = sub.build_mihomo_config(self.NODES, "s")
        self.assertIn('"h1"', config)

    def test_protocol_labels(self):
        self.assertEqual(["VLESS"], sub.protocol_labels(["vless"]))
        self.assertEqual(["VLESS", "Hysteria2"], sub.protocol_labels(["vless", "hysteria2"]))


class TestClashWindowSource(unittest.TestCase):
    """GUI 源码断言: 用户要的能力必须真的接进窗口。"""

    def _src(self):
        with open(os.path.join(ROOT, "gui", "clash_nodes_ui.py"), encoding="utf-8") as fh:
            return fh.read()

    def test_window_has_required_capabilities(self):
        src = self._src()
        for needle in ("show_clash_nodes_window", "Treeview", "切换节点",
                       "全部测速", "下载测速", "换一个可用节点", "更新订阅",
                       "透明", "FALLBACK_PROTO_CHOICES"):
            self.assertIn(needle, src, needle)

    def test_window_goes_through_relay_not_ssh(self):
        src = self._src()
        self.assertIn("clash.api_group", src)
        self.assertNotIn("paramiko", src)
        # 面板密钥只留在路由器本地, 电脑端不得出现读取密钥的代码
        self.assertNotIn("external-controller", src)
        self.assertNotIn("config.yaml", src)

    def test_main_window_registers_entry(self):
        with open(os.path.join(ROOT, "app_gui.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("ClashNodesMixin", src)
        self.assertIn("show_clash_nodes_window", src)

    def test_console_action_knows_rotate_node(self):
        with open(os.path.join(ROOT, "gui", "router_console_ui.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("rotate_node", src)

    def test_router_assets_ship_watchdog_and_api(self):
        for name in ("proxy-rotate.sh", "proxy-api.sh"):
            path = os.path.join(ROOT, "router_assets", name)
            self.assertTrue(os.path.isfile(path), name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("#!/bin/sh", text)
            self.assertNotIn("\r\n", text, "路由器脚本必须用 LF 换行")

    def test_watchdog_never_touches_transparent_proxy(self):
        with open(os.path.join(ROOT, "router_assets", "proxy-rotate.sh"),
                  encoding="utf-8") as fh:
            src = fh.read()
        # 注释里可以解释「为什么不碰 iptables」, 但真正会被执行的命令里绝不能有。
        code = "\n".join(line for line in src.splitlines()
                         if not line.strip().startswith("#"))
        self.assertNotIn("iptables", code)
        self.assertNotIn("transparent.enabled", code)
        self.assertNotIn("ip rule", code)
        # 看门狗只允许通过控制 API 的选择组切换节点
        self.assertIn("proxies/", code)

    def test_watchdog_lock_does_not_rely_on_find_mmin(self):
        """路由器的 busybox find 没有 -mmin/-mtime。

        曾经用 ``find "$LOCK" -mmin +5`` 判陈旧锁 —— 该选项在这台设备上直接报错,
        于是陈旧锁永远清不掉, 一次崩溃就能把看门狗永久锁死(实测踩到)。
        现在改成「锁目录 + 时间戳文件」, 这里把它钉住防止回退。
        """
        with open(os.path.join(ROOT, "router_assets", "proxy-rotate.sh"),
                  encoding="utf-8") as fh:
            code = "\n".join(line for line in fh.read().splitlines()
                             if not line.strip().startswith("#"))
        self.assertNotIn("-mmin", code)
        self.assertNotIn("-mtime", code)
        self.assertIn('$LOCK/ts', code)
        self.assertIn("LOCK_TTL", code)

    def test_watchdog_candidate_type_strips_quotes(self):
        """config.yaml 里 type 是带引号的 ('type: "vless"')。

        生成器统一用 JSON 字符串语法写值, 所以 awk 拿到的 type 是 ``"hysteria2"``
        而不是 ``hysteria2``。不剥引号的话 ``type != "hysteria2"`` 永远成立,
        剔除逻辑静默失效(实测踩到: 候选数 69 而非 52, 多测了 17 个必然不可用的 hy2)。
        因此 name 与 type 都必须剥引号 —— 这里钉住「有两处剥引号」。
        """
        with open(os.path.join(ROOT, "router_assets", "proxy-rotate.sh"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertEqual(2, src.count('gsub(/^"|"$/'),
                         "name 与 type 各需要一处剥引号")
        self.assertIn('type != "hysteria2"', src)

    def test_watchdog_prefers_lowest_delay_not_first_working(self):
        """只按「能通」落位会把用户钉在慢速线路上, 必须比过延迟。"""
        with open(os.path.join(ROOT, "router_assets", "proxy-rotate.sh"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("node_delay", src)
        self.assertIn('"delay"', src)
        # 节点名要先百分号编码才能进 /proxies/<name>/delay 的路径
        self.assertIn("hexdump", src)
        self.assertIn("pct", src)

    def test_watchdog_measures_before_switching(self):
        """轮换期间不应反复改道用户流量: 先全量测延迟(不改选择), 最后只切一次。"""
        with open(os.path.join(ROOT, "router_assets", "proxy-rotate.sh"),
                  encoding="utf-8") as fh:
            src = fh.read()
        # 取「第一步: 测延迟」那一段, 里面不允许出现 select_node
        body = src.split("# ---- 第一步")[1].split("# ---- 第二步")[0]
        body_code = "\n".join(line for line in body.splitlines()
                              if not line.strip().startswith("#"))
        self.assertNotIn("select_node", body_code)
        self.assertIn("node_delay", body_code)

        code = "\n".join(line for line in src.splitlines()
                         if not line.strip().startswith("#"))
        # 并行批量测速
        self.assertIn("wait", code)
        self.assertIn("BATCH", code)
        # 实测复验后再落位
        self.assertIn("VERIFY_TRY", code)
        # sed 行号必须从 1 起: busybox 的 sed -n "0p" 会打印第 1 行(GNU 则输出空),
        # 之前的批次偏移写法让首个节点被测了两次。
        self.assertNotIn("sed -n \"0p", code)
        self.assertIn("NEXT=1", code)


class TestRelayErrorKinds(unittest.TestCase):
    """错误分层: 「路由器不可达」绝不能和「节点不通」混为一谈。"""

    def _patch(self, body, status=200):
        sent = []
        original = clash.urlrequest.build_opener
        clash.urlrequest.build_opener = lambda *_a, **_k: FakeOpener(body, sent, status)
        self.addCleanup(lambda: setattr(clash.urlrequest, "build_opener", original))
        return sent

    def _patch_boom(self):
        def boom(*_a, **_k):
            raise URLError("unreachable")
        original = clash.urlrequest.build_opener
        clash.urlrequest.build_opener = boom
        self.addCleanup(lambda: setattr(clash.urlrequest, "build_opener", original))

    def test_rejected_and_badjson_kinds(self):
        self._patch('{"ok":false,"msg":"令牌错误"}')
        with self.assertRaises(clash.ClashApiError) as ctx:
            clash.relay_request("h", "p", "t", "version")
        self.assertEqual("rejected", ctx.exception.kind)

        self._patch("not json")
        with self.assertRaises(clash.ClashApiError) as ctx:
            clash.relay_request("h", "p", "t", "version")
        self.assertEqual("badjson", ctx.exception.kind)

    def test_network_kind(self):
        self._patch_boom()
        with self.assertRaises(clash.ClashApiError) as ctx:
            clash.relay_request("h", "p", "t", "version")
        self.assertEqual("network", ctx.exception.kind)

    def test_api_delay_does_not_swallow_environment_failure(self):
        """节点不通是正常业务结果(返回 None), 但路由器不可达必须抛出去。

        否则批量测速会显示成「52 个节点全挂了」, 把用户引向完全错误的方向
        (实测踩到: 路由器重启期间就是这个表现)。
        """
        self._patch('{"message":"timeout"}')
        self.assertIsNone(clash.api_delay("h", "8088", "t", "node"))

        self._patch_boom()
        with self.assertRaises(clash.ClashApiError):
            clash.api_delay("h", "8088", "t", "node")

    def test_error_hint_distinguishes_kinds(self):
        net = clash.error_hint(clash.ClashApiError("x", kind="network"))
        rej = clash.error_hint(clash.ClashApiError("x", kind="rejected"))
        bad = clash.error_hint(clash.ClashApiError("x", kind="badjson"))
        self.assertIn("连不上", net)
        self.assertIn("令牌", rej)
        self.assertIn("劫持", bad)
        self.assertEqual("", clash.error_hint(RuntimeError("x")))


class TestNodeSorting(unittest.TestCase):
    def _nodes(self):
        return [{"name": "b", "delay": 900, "alive": True},
                {"name": "a", "delay": 120, "alive": True},
                {"name": "u", "delay": None, "alive": True}]

    def test_ascending_puts_unmeasured_last(self):
        self.assertEqual(["a", "b", "u"],
                         [n["name"] for n in clash.sort_nodes(self._nodes())])

    def test_descending_still_puts_unmeasured_last(self):
        """降序时「未测」也必须留在最后, 否则一堆「—」会盖住真正可用的节点。"""
        nodes = clash.sort_nodes(self._nodes(), desc=True)
        self.assertEqual(["b", "a", "u"], [n["name"] for n in nodes])

    def test_sort_by_name_and_proto(self):
        nodes = [{"name": "b", "proto": "VLESS", "delay": 1},
                 {"name": "a", "proto": "Hysteria2", "delay": 2}]
        self.assertEqual(["a", "b"],
                         [n["name"] for n in clash.sort_nodes(nodes, by="name")])
        self.assertEqual(["a", "b"],
                         [n["name"] for n in clash.sort_nodes(nodes, by="proto")])

    def test_sort_tolerates_none_input(self):
        self.assertEqual([], clash.sort_nodes(None))


class TestProtocolChoices(unittest.TestCase):
    def test_derived_from_nodes_not_hardcoded(self):
        """订阅里出现 VMess/Trojan 时下拉框必须能筛出来(原来是硬编码三项)。"""
        nodes = [{"proto": "VLESS"}, {"proto": "Hysteria2"}, {"proto": "VLESS"},
                 {"proto": "VMess"}, {"proto": ""}]
        self.assertEqual(["全部", "Hysteria2", "VLESS", "VMess"],
                         clash.protocol_choices(nodes))
        self.assertEqual(["Hysteria2", "VLESS", "VMess"],
                         clash.protocol_choices(nodes, include_all=False))
        self.assertEqual(["全部"], clash.protocol_choices([]))
        self.assertEqual(["全部"], clash.protocol_choices(None))


class TestV542FixSource(unittest.TestCase):
    """把本轮修掉的几个真 bug 钉在源码层面, 防止回退。"""

    def _src(self):
        with open(os.path.join(ROOT, "gui", "clash_nodes_ui.py"), encoding="utf-8") as fh:
            return fh.read()

    def test_table_sort_actually_persists(self):
        """点表头必须真的改变顺序。

        曾经 _clash_sort 重排 _clash_nodes, 但 _clash_fill_tree 每次都无条件
        重排一遍, 于是点列头完全没有反应。
        """
        src = self._src()
        self.assertIn("_clash_sort_key", src)
        self.assertIn("_clash_sort_desc", src)
        body = src.split("def _clash_visible_nodes(")[1].split("\n    def ")[0]
        self.assertIn("sort_nodes", body, "排序必须由 _clash_visible_nodes 落实")

    def test_delay_batch_repaints_single_row(self):
        """测速期间只重画那一行, 不能整表重填把选中和滚动位置冲掉。"""
        src = self._src()
        self.assertIn("_clash_paint_delay", src)
        self.assertIn("_clash_tree_ref", src)

    def test_batch_tasks_are_mutually_exclusive(self):
        src = self._src()
        self.assertIn("_clash_begin_busy", src)
        self.assertIn("_clash_end_busy", src)
        # 批量测速与「一键选最快」都必须占闸, 否则两次 4 路并发会互相拖慢
        for fn in ("_clash_run_delay", "_clash_pick_fastest"):
            body = src.split("def %s(" % fn)[1].split("\n    def ")[0]
            self.assertIn("_clash_begin_busy", body, fn)

    def test_protocol_choices_are_synced_from_data(self):
        src = self._src()
        self.assertIn("_clash_sync_proto_choices", src)
        self.assertIn("clash.protocol_choices", src)

    def test_speed_test_has_wallclock_cap(self):
        """慢速管道上 socket 超时形同没有上限, 必须有墙钟上限与最小样本门槛。"""
        src = self._src()
        self.assertIn("SPEED_MAX_SECONDS", src)
        self.assertIn("SPEED_MIN_BYTES", src)

    def test_cgi_reports_mihomo_down_instead_of_empty_body(self):
        """mihomo 挂掉时不能返回空正文, 否则界面显示成「0 个节点」。"""
        with open(os.path.join(ROOT, "router_assets", "proxy-api.sh"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("mihomo 无响应", src)
        self.assertIn("RC=$?", src)


class TestThreadSafeUiUpdates(unittest.TestCase):
    """工作线程绝不能碰 tkinter —— 这是真机上才暴露的一类缺陷。"""

    def _src(self):
        with open(os.path.join(ROOT, "gui", "clash_nodes_ui.py"), encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def _code(text):
        """只留真正会执行的代码, 去掉 docstring 与注释。

        断言必须针对代码 —— 注释和文档里解释「为什么禁止 winfo_exists」是应该
        存在的, 不能因此判失败。
        """
        out, in_doc = [], False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.count('"""') >= 2:
                continue
            if stripped.count('"""') == 1:
                in_doc = not in_doc
                continue
            if in_doc or stripped.startswith("#"):
                continue
            out.append(line)
        return "\n".join(out)

    def _body(self, fn):
        # 注意带左括号: 不加的话 "def _clash_refresh" 会先匹配到 _clash_refresh_later
        raw = self._src().split("def %s(" % fn)[1].split("\n    def ")[0]
        return self._code(raw)

    def test_no_cross_thread_after_left(self):
        """整个文件里不允许再出现 self.after(0, ...) 这种跨线程 tkinter 调用。

        实测: 从工作线程调 ``self.after`` 会抛
        ``RuntimeError: main thread is not in main loop``, 异常顺着 pool.map
        冒到 worker, 被当成「测速中断」报给用户 —— 而真实原因跟节点毫无关系。
        """
        src = self._src()
        self.assertEqual(0, src.count("self.after(0"),
                         "跨线程 after 必须全部改成 _clash_ui 投递")

    def test_worker_bodies_do_not_touch_tkinter(self):
        for fn in ("_clash_refresh", "_clash_apply_named", "_clash_run_delay",
                   "_clash_pick_fastest", "_clash_speed_test"):
            body = self._body(fn)
            for bad in ("self.after", "winfo_exists", "configure(", "cget("):
                self.assertNotIn(bad, body, "%s 里出现了跨线程 tkinter 调用 %s" % (fn, bad))

    def test_ui_channel_is_pure_python_queue(self):
        """投递函数本身只允许碰队列。

        第一版这里写了 ``win.winfo_exists()`` 做存活检查 —— 那同样是一次跨线程
        tkinter 调用, 异常被 except 吞掉后界面再也刷不出来(实测踩到)。
        """
        body = self._body("_clash_ui")
        self.assertIn("ui_queue.put", body)
        self.assertNotIn("winfo_exists", body)
        self.assertNotIn("self.after", body)
        self.assertNotIn("_clash_window", body)

    def test_pump_runs_on_main_thread_with_generation_guard(self):
        body = self._body("_clash_pump")
        self.assertIn("get_nowait", body)
        self.assertIn("win.after(80, self._clash_pump)", body)
        # 换代后旧窗口遗留的更新必须被丢弃
        self.assertIn("_clash_gen", body)
        self.assertIn("_clash_gen", self._src())

    def test_close_replaces_window_ref(self):
        src = self._src()
        self.assertIn("def _clash_close", src)
        body = self._body("_clash_close")
        self.assertIn("self._clash_window = None", body)


class TestDisplayedDataConsistency(unittest.TestCase):
    """界面上显示的延迟、排序用的延迟、判定死活用的延迟必须是同一份数据。"""

    def _src(self):
        with open(os.path.join(ROOT, "gui", "clash_nodes_ui.py"), encoding="utf-8") as fh:
            return fh.read()

    def test_sort_uses_the_delay_shown_in_the_list(self):
        """排序必须用界面上显示的延迟, 而不是 mihomo 的历史值。

        实测踩到: 点完「全部测速」再按延迟排序, 顺序和列表里的数字对不上 ——
        因为排序读的是 node["delay"](mihomo 历史), 列表显示的是 _clash_delays。
        """
        src = self._src()
        self.assertIn("_clash_effective_delay", src)
        body = src.split("def _clash_visible_nodes(")[1].split("\n    def ")[0]
        self.assertIn("_clash_effective_delay", body)

    def test_row_painting_uses_same_source(self):
        src = self._src()
        for fn in ("_clash_fill_tree", "_clash_paint_delay"):
            body = src.split("def %s(" % fn)[1].split("\n    def ")[0]
            self.assertIn("_clash_effective_delay", body, fn)

    def test_delay_batch_restores_head(self):
        """测速结束后头部不能卡在「正在测速 N/N」。"""
        src = self._src()
        body = src.split("def _clash_run_delay(")[1].split("\n    def ")[0]
        self.assertIn("self._clash_ui(self._clash_refresh)", body)


if __name__ == "__main__":
    unittest.main()
