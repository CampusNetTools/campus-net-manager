# 手机全流量共享：iPhone 内建 IKEv2

```text
iPhone 系统 VPN（手动安装描述文件） -- IKEv2 --> Mac「校园网连接管家」 --> 校园网 / 用户已有 VPN
```

此路线不需要 iPhone App、App Store 下载、Xcode 或 Apple Developer 签名。iPhone 用户会在系统设置中看到并确认添加 VPN；删除该描述文件即可移除手机端配置。

## Mac 端职责

- 用户可见授权后安装和启动 IKEv2 服务端（例如 strongSwan 的 `swanctl`/`charon`）。
- 为 Mac 网关创建专用 CA 与服务器证书；服务器证书的 SAN/CN 必须匹配配置中的 `RemoteIdentifier`。
- 为每台手机生成独立 EAP 用户名和随机密码；Mac 保存这些凭据仅用于网关认证，绝不使用或传输校园网账号密码。
- 在用户确认后配置最小化、可撤销的 IP 转发/NAT；未确认前仅可生成预检信息，不能改变系统网络。

## iPhone 描述文件

项目生成的是标准 `com.apple.vpn.managed` / `IKEv2` 配置描述文件，内含网关 CA、服务器地址、远端标识和单机 EAP 凭据。IKE 层固定校验服务器 X.509 证书（`AuthenticationMethod=Certificate`），EAP 层使用该手机独立的随机账号密码；不会以 `None` 跳过服务器身份验证。描述文件本身包含认证密码，属于敏感文件：只可通过本地 AirDrop/USB 交给该手机，安装后立即从临时位置删除，不能上传网盘、发聊天或打印二维码。

## 验收

1. iPhone 手动安装描述文件并确认系统 VPN 提示。
2. 同一局域网完成连接，Safari、微信图片和测速各验证一次。
3. 断开、移除描述文件、撤销服务器端 EAP 凭据后，确认手机无法再连入。
4. 恢复 Mac 原网络设置，确认校园网和用户已有 VPN 不受残留规则影响。
