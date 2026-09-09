# CampusNet Companion for iPhone

这是“校园网连接管家”的 iPhone 配套端，不是另一套校园网登录器。

它的目标是让手机扫描电脑显示的一次性配对码后，建立由 iOS 显式授权的 Packet Tunnel VPN；流量经过加密隧道到达电脑网关，再由电脑的校园网/VPN出口转发。

## 已包含的工程边界

- SwiftUI 主 App：扫码导入配对信息、查看 VPN 状态、连接/断开。
- `PacketTunnelProvider`：使用 iOS 系统 VPN 扩展接收 IP 数据包。
- 一次性配对协议模型：二维码只含服务器地址、短期配对令牌与证书指纹，不含校园网账号、密码或 VPN 订阅。
- Mac 网关协议说明：隧道建立、心跳、IP 数据帧、断开与错误码。

## 仍不能宣称已完成的部分

本机当前只有 Command Line Tools，未安装完整 Xcode，无法签名或部署到 iPhone。更重要的是，Packet Tunnel 必须配合 Mac 网关的 TUN/NAT 特权组件和有效 TLS 证书/证书指纹校验才可转发真实全流量。未接入这些组件前，本工程的连接按钮不会伪装成“已能上网”。

## 开发前置条件

1. 安装完整 Xcode，并登录具有 Network Extension 能力的 Apple Developer 团队。
2. 在 App ID 启用 `packet-tunnel-provider`，主 App 与扩展共享 Keychain Access Group。
3. 用 XcodeGen 生成工程：`xcodegen generate`；或按 `project.yml` 手工建立同名 target。
4. 真机安装后，首次连接必须由用户确认 iOS 的“添加 VPN 配置”提示。

详情见 [架构说明](docs/ARCHITECTURE.md)。
