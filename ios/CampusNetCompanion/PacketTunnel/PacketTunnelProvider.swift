import Foundation
import NetworkExtension

final class PacketTunnelProvider: NEPacketTunnelProvider {
    private let transport = GatewayTransport()

    override func startTunnel(options: [String : NSObject]?, completionHandler: @escaping (Error?) -> Void) {
        guard let configuration = protocolConfiguration.providerConfiguration,
              let host = configuration["gatewayHost"] as? String,
              let port = configuration["gatewayPort"] as? NSNumber else {
            completionHandler(TunnelStartupError.configurationMissing); return
        }
        guard let token = try? SharedCredential.load() else {
            completionHandler(TunnelStartupError.credentialMissing); return
        }
        guard !host.isEmpty, port.uint16Value > 0 else { completionHandler(TunnelStartupError.configurationMissing); return }

        let settings = makeSettings(host: host)
        setTunnelNetworkSettings(settings) { [weak self] error in
            guard let self else { return }
            if let error { completionHandler(error); return }
            self.transport.onFrame = { [weak self] type, body in self?.handle(type, body: body) }
            self.transport.start(host: host, port: port.uint16Value, token: token,
                                 certificatePinSHA256: configuration["certificatePinSHA256"] as? String ?? "") { [weak self] result in
                guard let self else { return }
                if let result {
                    completionHandler(result)
                    return
                }
                self.transport.onFailure = { [weak self] error in self?.cancelTunnelWithError(error) }
                self.readPackets()
                completionHandler(nil)
            }
        }
    }

    override func stopTunnel(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) {
        transport.stop(); completionHandler()
    }

    private func makeSettings(host: String) -> NEPacketTunnelNetworkSettings {
        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: host)
        let ipv4 = NEIPv4Settings(addresses: ["10.77.0.2"], subnetMasks: ["255.255.255.0"])
        ipv4.includedRoutes = [NEIPv4Route.default()]
        // 避免去电脑网关的 TLS 连接再次被路由进自身 Packet Tunnel。
        if host.split(separator: ".").count == 4 { ipv4.excludedRoutes = [NEIPv4Route(destinationAddress: host, subnetMask: "255.255.255.255")] }
        settings.ipv4Settings = ipv4
        settings.mtu = 1280
        // DNS 由配对后的电脑网关下发；没有可信网关时不擅自替换用户 DNS。
        return settings
    }

    private func readPackets() {
        packetFlow.readPackets { [weak self] packets, protocols in
            guard let self else { return }
            for (packet, proto) in zip(packets, protocols) { self.transport.sendPacket(packet, family: proto.int32Value) }
            self.readPackets()
        }
    }

    private func handle(_ type: GatewayFrame, body: Data) {
        guard type == .packet, let family = body.first else { return }
        let packet = body.dropFirst()
        let proto: NSNumber = family == 6 ? NSNumber(value: AF_INET6) : NSNumber(value: AF_INET)
        packetFlow.writePackets([Data(packet)], withProtocols: [proto])
    }
}

enum TunnelStartupError: LocalizedError {
    case configurationMissing, credentialMissing
    var errorDescription: String? {
        switch self {
        case .configurationMissing: return "缺少电脑网关配置，请重新扫码配对。"
        case .credentialMissing: return "配对凭据已失效，请重新扫码。"
        }
    }
}
