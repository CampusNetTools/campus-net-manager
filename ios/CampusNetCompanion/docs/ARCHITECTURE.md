# iPhone 全流量隧道架构

```text
iPhone App --扫码一次性配对--> Mac Desktop App
     |                                 |
     +-- Packet Tunnel (iOS VPN) <--TLS/UDP--> Mac Gateway (TUN + NAT)
                                                |
                                           校园网 / 系统 VPN
```

## 为什么不继续依赖 HTTP 代理

Wi-Fi 的 HTTP 代理只覆盖遵从该设置的 HTTP/HTTPS 连接；部分 App 的 UDP、QUIC、私有长连接或自定义网络栈不会稳定经过它。Packet Tunnel 将系统路由交给 iOS 的 VPN 扩展，才能覆盖 TCP 和 UDP 数据包。

## 配对与安全

1. 桌面端只在用户点击“创建手机 VPN 配对”后启动本地网关。
2. 生成 60 秒有效、仅能兑换一次的随机令牌；二维码不包含校园网密码、电脑用户资料或第三方 VPN 订阅。
3. 手机扫码后用 TLS 与电脑交换令牌，校验二维码携带的电脑叶证书 SHA-256 指纹，并将会话密钥保存到 App Group/Keychain。
4. 网关显示设备名称、连接时间、上传/下载字节和最近错误；用户可随时撤销单台设备。

## 网关协议 v1（实现契约）

传输层使用认证的 TLS 连接；生产版优先使用基于 UDP 的可靠/拥塞控制传输，避免将 UDP 业务全部套入 TCP 产生队头阻塞。帧格式：

```text
length: UInt32 (big endian, 不含自身)
type:   UInt8
body:   bytes
```

类型：`0x01` 配对/握手、`0x02` IPv4/IPv6 原始 IP 包、`0x03` 心跳、`0x04` 状态、`0x7f` 错误。网关仅在令牌成功兑换后发送 `0x04 + "ready"`；iPhone 收到此前不得将系统 VPN 标记为已连接。

Mac 端必须用受控特权组件创建 TUN、配置 NAT 和转发规则；不要让普通 GUI 静默执行 `pfctl` 或要求用户关闭系统防火墙。此部分没有接入前，iOS 客户端应明确显示“网关未就绪”。

## 验收标准

- 电脑端明确显示已配对的 iPhone 和实时连接状态。
- iPhone 端连接后显示系统 VPN 已连接，断开后恢复原网络。
- Safari、微信图片和测速 App 在同一网络条件下各验证一次。
- 失败时显示阶段（配对、TLS、网关、路由），不记录页面内容、聊天内容或账号密码。
