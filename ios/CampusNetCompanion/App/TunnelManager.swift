import Foundation
import NetworkExtension

@MainActor
final class TunnelManager: ObservableObject {
    enum State: Equatable {
        case unpaired, preparing, disconnected, connecting, connected, failed(String)
        var title: String {
            switch self {
            case .unpaired: return "等待扫码配对"
            case .preparing: return "正在保存 VPN 配置"
            case .disconnected: return "已配对，未连接"
            case .connecting: return "正在连接电脑"
            case .connected: return "已通过电脑隧道连接"
            case .failed(let reason): return reason
            }
        }
    }

    @Published private(set) var state: State = .unpaired
    @Published private(set) var pairing: PairingPayload?
    private var manager: NETunnelProviderManager?

    init() { Task { await reload() } }

    func importPairing(_ payload: PairingPayload) async {
        do {
            // 生产版这里先向电脑兑换一次性令牌，再保存短期会话凭据。
            // 未接入网关前不允许把它当作已连接状态。
            try SharedCredential.save(payload.enrollmentToken)
            pairing = payload
            state = .preparing
            try await configureVPN(payload)
            state = .disconnected
        } catch {
            state = .failed(error.localizedDescription)
        }
    }

    func connect() {
        guard let manager else { state = .failed("VPN 配置尚未完成"); return }
        do {
            state = .connecting
            try manager.connection.startVPNTunnel()
            watchStatus(manager.connection.status)
        } catch { state = .failed("iOS 拒绝启动 VPN：\(error.localizedDescription)") }
    }

    func disconnect() {
        manager?.connection.stopVPNTunnel()
        state = pairing == nil ? .unpaired : .disconnected
    }

    func forget() {
        disconnect()
        SharedCredential.clear()
        pairing = nil
        state = .unpaired
    }

    func reload() async {
        do {
            let managers = try await NETunnelProviderManager.loadAllFromPreferences()
            manager = managers.first(where: { $0.protocolConfiguration?.providerBundleIdentifier == "com.campusnettools.companion.packet-tunnel" })
            guard let manager else { return }
            if let config = manager.protocolConfiguration?.providerConfiguration,
               let host = config["gatewayHost"] as? String,
               let port = config["gatewayPort"] as? NSNumber,
               let expires = config["expiresAt"] as? Date {
                pairing = PairingPayload(version: 1, gatewayHost: host, gatewayPort: port.uint16Value,
                                         enrollmentToken: "stored-in-keychain", certificatePinSHA256: "stored", expiresAt: expires)
                watchStatus(manager.connection.status)
            }
        } catch { state = .failed("无法读取 iOS VPN 配置：\(error.localizedDescription)") }
    }

    private func configureVPN(_ payload: PairingPayload) async throws {
        let manager = self.manager ?? NETunnelProviderManager()
        let proto = NETunnelProviderProtocol()
        proto.providerBundleIdentifier = "com.campusnettools.companion.packet-tunnel"
        proto.serverAddress = payload.gatewayHost
        proto.providerConfiguration = ["gatewayHost": payload.gatewayHost,
                                       "gatewayPort": NSNumber(value: payload.gatewayPort),
                                       "certificatePinSHA256": payload.certificatePinSHA256,
                                       "expiresAt": payload.expiresAt]
        manager.protocolConfiguration = proto
        manager.localizedDescription = "校园网连接管家 · 电脑隧道"
        manager.isEnabled = true
        try await manager.saveToPreferences()
        self.manager = manager
    }

    private func watchStatus(_ status: NEVPNStatus) {
        switch status {
        case .connected: state = .connected
        case .connecting, .reasserting: state = .connecting
        case .disconnected, .disconnecting: state = pairing == nil ? .unpaired : .disconnected
        case .invalid: state = .failed("VPN 配置无效")
        @unknown default: state = .failed("未知 VPN 状态")
        }
    }
}
