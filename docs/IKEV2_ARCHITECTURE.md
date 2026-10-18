# 手机全流量共享：iPhone 内建 IKEv2

```text
iPhone Companion App / iOS 系统 VPN -- IKEv2 --> Mac「校园网连接管家」 --> 校园网 / 用户已有 VPN
```

系统 `.mobileconfig` 仍是无需 App 的备用安装方式。iOS Companion App 使用 `NEVPNManager` 管理内建 IKEv2，首次配置由 iOS 显示授权提示；VPN 服务上架仍需组织开发者账号、隐私披露和 App Review。

## 无 Xcode 的长期 iPhone 使用方式

如果用户不接受个人免费签名短周期重装，则使用安装在 iOS 设置中的完整 IKEv2 `.mobileconfig`，而不是把 unsigned Simulator app 或 Home Screen PWA 当成原生 VPN App。该系统配置可以由 iPhone Safari 下载后在“设置 > 通用 > VPN 与设备管理”安装；配置没有设置 profile expiration，但受服务端证书有效期约束。安装器会把单设备 EAP 凭据写进配置文件，因此只允许在网关 Mac 本地生成后经 AirDrop/USB 私下传递，安装后删除传输副本，不上传公开网站或聊天。该方式用 iOS Settings 管理连接，不包含 companion app 的 UI/Keychain 管理能力。

本仓库 `scripts/install_ikev2_gateway.sh` 创建的 CA 有效期 3650 天，服务器证书有效期 825 天。到期前需由管理员续发服务器证书；CA 到期前需替换根证书并重新发放 profile。浏览器 PWA 可以提供流程说明，但不能调用 `NEVPNManager` 控制系统 VPN。参见 [Apple 的 profile 安装说明](https://support.apple.com/guide/iphone/iph6c493b19/ios) 与 [IKEv2 payload 参考](https://developer.apple.com/documentation/devicemanagement/vpn/ikev2-data.dictionary)。

## Mac 端职责

- 用户可见授权后安装和启动 IKEv2 服务端（例如 strongSwan 的 `swanctl`/`charon`）。
- 为 Mac 网关创建专用 CA 与服务器证书；服务器证书的 SAN/CN 必须匹配配置中的 `RemoteIdentifier`。
- 为每台手机生成独立 EAP 用户名和随机密码；Mac 保存这些凭据仅用于网关认证，绝不使用或传输校园网账号密码。
- 在用户确认后配置最小化、可撤销的 IP 转发/NAT；未确认前仅可生成预检信息，不能改变系统网络。

## iPhone 描述文件

项目为每台设备生成：完整 `.mobileconfig` 备用配置、仅含 CA 根证书的 `-ca.mobileconfig`，以及给 App 导入的 `.ikev2.json`。App JSON 含单设备随机 EAP 凭据，权限设为 `0600`，只能通过本地 AirDrop/USB 交付，并在 App 导入后删除；不能上传网盘、发聊天或打印二维码。App 把密码写入 iOS Keychain，并把 persistent reference 交给系统 VPN 配置。安装并信任根 CA 后，IKEv2 使用 EAP-only（`AuthenticationMethod=None`、`ExtendedAuthEnabled=1`）并显式校验服务器证书名称；这不会跳过服务器身份验证。EAP 账号与校园网 Wi‑Fi 凭据相互独立。

`.mobileconfig` 备用方式仍含 VPN EAP 凭据；该文件同样敏感，按本地一次性交付并在安装后删除。

## 验收

1. 在 iPhone 安装/信任根证书，导入 App JSON 并确认系统 VPN 提示；或使用完整 `.mobileconfig` 备用路线。
2. 同一局域网完成连接，Safari、微信图片和测速各验证一次。
3. 在 App 中断开/移除配置并撤销服务端 EAP 凭据，确认手机无法再连入。
4. 恢复 Mac 原网络设置，确认校园网和用户已有 VPN 不受残留规则影响。
