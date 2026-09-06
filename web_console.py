# -*- coding: utf-8 -*-
"""局域网 Web 管理控制台。

手机/电脑浏览器访问 http://<局域网IP>:<port>/?key=<口令> 即可:
- 查看守护/网络/环境状态、最近日志、断网时间线、测速入口
- 管理隧道共享已授权设备(查看/移除)
- 启动/停止守护

安全: 所有请求必须带访问口令(query key= 或 X-Console-Key 头), 口令来自
core.gen_tunnel_key(), 与隧道共享口令同级强度; 仅监听局域网场景使用。
"""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core import common, history, sysutils


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>校园网连接管家 · 控制台</title>
<style>
:root { --bg:#0b1220; --card:#131d2e; --card2:#1b2940; --border:#2a3a53;
        --fg:#f3f7fc; --muted:#8fa1ba; --accent:#4f7cff; --green:#32c48d;
        --red:#f06478; --yellow:#f1b84b; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg); font-family: -apple-system, "PingFang SC", sans-serif;
       padding: 16px; max-width: 720px; margin: 0 auto; }
h1 { font-size: 20px; margin-bottom: 4px; }
.sub { color: var(--muted); font-size: 13px; margin-bottom: 16px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px;
        padding: 14px 16px; margin-bottom: 14px; }
.card h2 { font-size: 15px; margin-bottom: 10px; color: var(--muted); font-weight: 600; }
.row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px;
       border-bottom: 1px solid var(--border); }
.row:last-child { border-bottom: none; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.g { background: var(--green); } .r { background: var(--red); } .y { background: var(--yellow); }
button { background: var(--accent); color: #fff; border: none; border-radius: 8px;
         padding: 8px 16px; font-size: 14px; cursor: pointer; }
button.gray { background: var(--card2); color: var(--fg); }
button.danger { background: var(--red); }
pre { background: var(--card2); border-radius: 8px; padding: 10px; font-size: 11px;
      overflow-x: auto; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; }
.device { display: flex; justify-content: space-between; align-items: center; padding: 6px 0;
          border-bottom: 1px solid var(--border); font-size: 14px; }
.device:last-child { border-bottom: none; }
.device button { padding: 4px 10px; font-size: 12px; }
#toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
         background: var(--card2); padding: 8px 18px; border-radius: 20px; font-size: 13px;
         display: none; }
</style>
</head>
<body>
<h1>校园网连接管家 · 控制台</h1>
<div class="sub" id="ver"></div>

<div class="card"><h2>运行状态</h2><div id="status">加载中…</div></div>

<div class="card"><h2>操作</h2>
  <button id="btn-daemon" onclick="toggleDaemon()">启动/停止守护</button>
  <button class="gray" onclick="refresh()">刷新</button>
</div>

<div class="card"><h2>隧道共享 · 已授权设备</h2><div id="devices">加载中…</div></div>

<div class="card"><h2>断网时间线（7 天）</h2><div id="outages">加载中…</div></div>

<div class="card"><h2>最近日志</h2><pre id="logs">加载中…</pre></div>

<div id="toast"></div>
<script>
const KEY = new URLSearchParams(location.search).get('key') || '';
function api(path, opts) {
  opts = opts || {};
  opts.headers = Object.assign({'X-Console-Key': KEY}, opts.headers || {});
  return fetch(path, opts).then(r => {
    if (r.status === 403) throw new Error('口令错误');
    return r.json();
  });
}
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 2000);
}
function dot(ok, na) { return '<span class="dot ' + (na ? 'y' : (ok ? 'g' : 'r')) + '"></span>'; }
function row(k, v) { return '<div class="row"><span>' + k + '</span><span>' + v + '</span></div>'; }

function refresh() {
  api('/api/status').then(s => {
    document.getElementById('ver').textContent = 'v' + s.version + ' · ' + (s.platform || '')
        + ' · ' + (s.hostname || '');
    const lanRow = (s.lan_ips && s.lan_ips.length)
      ? row('本机局域网 IP', s.lan_ips.join(', ')) : '';
    const env = s.in_campus === null ? '未知' : (s.in_campus ? '校园网环境' : '非校园网（休眠）');
    const net = s.authed ? (s.internet ? '已认证·可上网' : '已认证·出口异常') : '未认证/掉线';
    document.getElementById('status').innerHTML =
      row('守护', dot(s.daemon_running) + (s.daemon_running ? '运行中' : '已停止')) +
      row('网络', dot(s.authed && s.internet, !s.daemon_running) + net) +
      row('环境', env) +
      row('当前档案', s.profile || '—') +
      row('接入方式', s.mode + (s.ssid ? ' · ' + s.ssid : '') + (s.gateway ? ' · 网关 ' + s.gateway : '')) +
      row('隧道共享', dot(s.proxy_running, true) + (s.proxy_running ? '已开启' : '未开启')) +
      row('最近检测', s.last_check || '—') + lanRow;
    document.getElementById('btn-daemon').textContent = s.daemon_running ? '停止守护' : '启动守护';
  }).catch(e => toast(e.message));

  api('/api/devices').then(d => {
    const el = document.getElementById('devices');
    if (!d.allowed.length) { el.innerHTML = '<span style="color:var(--muted)">暂无已授权设备</span>'; return; }
    el.innerHTML = d.allowed.map(ip =>
      '<div class="device"><span>' + ip + '</span>' +
      '<button class="danger" onclick="removeDevice(\\'' + ip + '\\')">移除</button></div>').join('');
  }).catch(() => {});

  api('/api/outages').then(o => {
    const el = document.getElementById('outages');
    if (!o.outages.length) { el.innerHTML = '<span style="color:var(--muted)">最近 7 天没有断网记录</span>'; return; }
    el.innerHTML = o.outages.map((x, i) =>
      row((i + 1) + '. ' + x.start, '→ ' + x.end + '（' + x.duration + '）')).join('');
  }).catch(() => {});

  api('/api/logs?n=60').then(l => {
    document.getElementById('logs').textContent = l.lines.join('\\n') || '（暂无日志）';
  }).catch(() => {});
}

function toggleDaemon() {
  api('/api/daemon/toggle', {method: 'POST'}).then(r => { toast(r.message); refresh(); })
    .catch(e => toast(e.message));
}
function removeDevice(ip) {
  api('/api/devices/remove', {method: 'POST', body: JSON.stringify({ip: ip})})
    .then(r => { toast(r.message); refresh(); }).catch(e => toast(e.message));
}
refresh();
setInterval(refresh, 8000);
</script>
</body>
</html>
"""


KEY_ENTRY_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>校园网连接管家 · 控制台</title>
<style>
:root { --bg:#0b1220; --card:#131d2e; --card2:#1b2940; --border:#2a3a53;
        --fg:#f3f7fc; --muted:#8fa1ba; --accent:#4f7cff; --red:#f06478; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg); font-family: -apple-system, "PingFang SC", sans-serif;
       padding: 24px 18px; max-width: 480px; margin: 0 auto; }
h1 { font-size: 18px; margin-bottom: 6px; }
.sub { color: var(--muted); font-size: 13px; line-height: 1.6; margin-bottom: 18px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px;
        padding: 16px; margin-bottom: 14px; }
label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
input { width: 100%; padding: 11px 12px; font-size: 15px; background: var(--card2);
        color: var(--fg); border: 1px solid var(--border); border-radius: 8px;
        outline: none; -webkit-appearance: none; }
input:focus { border-color: var(--accent); }
button { background: var(--accent); color: #fff; border: none; border-radius: 8px;
         padding: 11px 18px; font-size: 15px; cursor: pointer; width: 100%; margin-top: 10px; }
.err { color: var(--red); font-size: 13px; margin-top: 8px; min-height: 18px; }
.tip { color: var(--muted); font-size: 12px; line-height: 1.7; margin-top: 14px; }
</style>
</head>
<body>
<h1>校园网连接管家 · 控制台</h1>
<div class="sub">在电脑上 App 窗口里点「复制访问口令」并粘贴到下方（口令已包含在二维码链接里，扫码可跳过这一步）。</div>
<div class="card">
  <label for="key">访问口令</label>
  <input id="key" type="text" autocapitalize="off" autocorrect="off" autocomplete="off"
         placeholder="粘贴访问口令…" />
  <button onclick="enter()">进入控制台</button>
  <div class="err" id="err"></div>
</div>
<div class="tip">
提示：如果一直转圈或显示"未接入互联网"，说明 iOS Safari 缓存了上一次失败状态。请下拉刷新，或切 WiFi 重连一下电脑热点/路由器。
</div>
<script>
function enter() {
  var k = document.getElementById('key').value.trim();
  if (!k) { document.getElementById('err').textContent = '请先粘贴口令'; return; }
  var err = document.getElementById('err');
  err.textContent = '校验口令…';
  // 先探测 key 有效性, 避免跳到控制台后所有 API 都返引导页导致页面卡死
  fetch('/api/key?key=' + encodeURIComponent(k)).then(function(r) {
    return r.json();
  }).then(function(j) {
    if (j && j.authed) {
      location.replace(location.pathname + '?key=' + encodeURIComponent(k));
    } else {
      err.textContent = '口令错误, 请重新复制';
    }
  }).catch(function() {
    // 探测失败也允许跳转, 让用户看到控制台再去确认
    location.replace(location.pathname + '?key=' + encodeURIComponent(k));
  });
}
document.getElementById('key').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') enter();
});
// 自动读取 URL ?key= 并预填(便于复制后回访)
(function() {
  var url = new URL(location.href);
  var k = url.searchParams.get('key');
  if (k) document.getElementById('key').value = k;
})();
</script>
</body>
</html>
"""


class WebConsole:
    """局域网控制台 HTTP 服务。state_fn() 返回状态 dict; action_fn(name) 执行操作。"""

    def __init__(self, state_fn, key, port=8081, host="0.0.0.0",
                 proxy=None, action_fn=None):
        self.state_fn = state_fn
        self.key = key
        self.port = port
        self.host = host
        self.proxy = proxy          # SharedProxy 实例(可为 None)
        self.action_fn = action_fn  # callable(action_name) -> message
        self._server = None
        self._thread = None

    @property
    def running(self):
        return self._server is not None

    def start(self):
        if self.running:
            return True
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def _authed(self):
                query = urllib.parse.parse_qs(
                    urllib.parse.urlsplit(self.path).query)
                return (query.get("key", [None])[0] == outer.key
                        or self.headers.get("X-Console-Key") == outer.key)

            def _send(self, code, body, ctype="text/html; charset=utf-8"):
                data = body.encode("utf-8") if isinstance(body, str) else body
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                # 防止 iOS Safari 因短失败响应缓存"未接入互联网"状态
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                # 关闭长连接, 避免手机后台连接断开后被 Safari 误判"网络中断"
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _json(self, obj, code=200):
                self._send(code, json.dumps(obj, ensure_ascii=False),
                           "application/json; charset=utf-8")

            def _read_body(self):
                length = int(self.headers.get("Content-Length") or 0)
                if not length:
                    return {}
                try:
                    return json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception:
                    return {}

            def do_GET(self):
                path = urllib.parse.urlsplit(self.path).path
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                # 注意: 根路径 "/" 不强制鉴权, 而是返回"输入口令"引导页 ——
                # iOS Safari 对 403 会展示"未接入互联网"误导并缓存,
                # 引导页无此副作用, 用户输口令后自动跳到控制台
                if path == "/":
                    key_in = query.get("key", [None])[0] or self.headers.get("X-Console-Key")
                    if key_in == outer.key:
                        self._send(200, PAGE)
                    else:
                        self._send(200, KEY_ENTRY_HTML)
                    return
                # /api/key 鉴权查询接口: 永远返 JSON, 便于引导页实时校验 key
                # (其余 API 鉴权失败仍返 HTML 引导页, 避免 iOS Safari 缓存"未接入互联网")
                if path == "/api/key":
                    self._json({"authed": self._authed()})
                    return
                if not self._authed():
                    self._send(200, KEY_ENTRY_HTML)
                    return
                if path == "/api/status":
                    try:
                        self._json(outer.state_fn())
                    except Exception as e:
                        self._json({"error": str(e)}, 500)
                elif path == "/api/logs":
                    n = min(int(query.get("n", ["60"])[0] or 60), 500)
                    self._json({"lines": _tail_log(n)})
                elif path == "/api/outages":
                    try:
                        self._json({"outages": history.analyze_outage_timeline(7)})
                    except Exception:
                        self._json({"outages": []})
                elif path == "/api/devices":
                    allowed = sorted(outer.proxy.allowed) if outer.proxy else []
                    self._json({"allowed": allowed,
                                "proxy_running": bool(outer.proxy and outer.proxy.running)})
                else:
                    self._send(404, "404")

            def do_POST(self):
                path = urllib.parse.urlsplit(self.path).path
                if not self._authed():
                    self._send(200, KEY_ENTRY_HTML)
                    return
                if path == "/api/devices/remove":
                    ip = self._read_body().get("ip", "")
                    if outer.proxy and ip in outer.proxy.allowed:
                        outer.proxy.allowed.discard(ip)
                        self._json({"ok": True, "message": "已移除 %s" % ip})
                    else:
                        self._json({"ok": False, "message": "设备不存在或隧道未开启"})
                elif path == "/api/daemon/toggle":
                    if outer.action_fn:
                        try:
                            msg = outer.action_fn("toggle_daemon")
                        except Exception as e:
                            msg = "操作失败: %s" % e
                        self._json({"ok": True, "message": msg})
                    else:
                        self._json({"ok": False, "message": "未接入守护控制"})
                else:
                    self._send(404, "404")

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        sysutils.log("Web 控制台已启动: 端口 %d" % self.port)
        return True

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            sysutils.log("Web 控制台已停止")


def _tail_log(n):
    try:
        with open(common.LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            return [ln.rstrip("\n") for ln in f.readlines()[-n:]]
    except Exception:
        return []
