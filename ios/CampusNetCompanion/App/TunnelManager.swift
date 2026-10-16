import Foundation
import NetworkExtension

@MainActor
final class TunnelManager: ObservableObject {
    enum State: Equatable {
        case unpaired, preparing, disconnected, connecting, connected, disconnecting, failed(String)

        var title: String {
            switch self {
            case .unpaired: return "尚未导入设备配置"
            case .preparing: return "正在保存系统 IKEv2 配置"
            case .disconnected: return "已配置，未连接"
            case .connecting: return "正在连接校园网网关"
            case .connected: return "IKEv2 已连接"
            case .disconnecting: return "正在断开"
            case .failed(let reason): return reason
            }
        }
    }

    struct Configuration: Equatable {
        let deviceName: String
        let serverAddress: String
        let username: String
    }

    @Published private(set) var state: State = .unpaired
    @Published private(set) var configuration: Configuration?

    private let manager = NEVPNManager.shared()
    private var statusObserver: NSObjectProtocol?

    init() {
        statusObserver = NotificationCenter.default.addObserver(
            forName: .NEVPNStatusDidChange, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.refreshStatus() }
        }
        Task { await reload() }
    }

    func importConfiguration(_ data: Data) async {
        do {
            let enrollment = try IKEv2Enrollment.decode(data)
            state = .preparing
            try await loadPreferences()
            let previousProtocol = manager.protocolConfiguration
            let previousDescription = manager.localizedDescription
            let previousEnabled = manager.isEnabled
            let previousOnDemand = manager.isOnDemandEnabled
            let previousReference = (manager.protocolConfiguration as? NEVPNProtocolIKEv2)?.passwordReference
            let newReference = try IKEv2CredentialStore.savePassword(enrollment.password)

            let ikev2 = NEVPNProtocolIKEv2()
            ikev2.serverAddress = enrollment.serverAddress
            ikev2.remoteIdentifier = enrollment.serverIdentifier
            ikev2.serverCertificateCommonName = enrollment.serverIdentifier
            ikev2.authenticationMethod = .none
            ikev2.useExtendedAuthentication = true
            ikev2.username = enrollment.username
            ikev2.passwordReference = newReference
            ikev2.localIdentifier = enrollment.username
            ikev2.disableMOBIKE = false
            ikev2.enablePFS = true
            ikev2.deadPeerDetectionRate = .medium
            ikev2.includeAllNetworks = true

            manager.protocolConfiguration = ikev2
            manager.localizedDescription = "校园网连接管家 · \(enrollment.deviceName)"
            manager.isEnabled = true
            manager.isOnDemandEnabled = false

            do {
                try await savePreferences()
                IKEv2CredentialStore.deletePassword(reference: previousReference)
                configuration = Configuration(deviceName: enrollment.deviceName,
                                               serverAddress: enrollment.serverAddress,
                                               username: enrollment.username)
                state = .disconnected
            } catch {
                manager.protocolConfiguration = previousProtocol
                manager.localizedDescription = previousDescription
                manager.isEnabled = previousEnabled
                manager.isOnDemandEnabled = previousOnDemand
                IKEv2CredentialStore.deletePassword(reference: newReference)
                throw error
            }
        } catch {
            state = .failed("导入或保存 VPN 配置失败：\(error.localizedDescription)")
        }
    }

    func connect() {
        guard configuration != nil, manager.isEnabled,
              manager.protocolConfiguration is NEVPNProtocolIKEv2 else {
            state = .failed("请先导入 Mac 生成的 IKEv2 设备配置。")
            return
        }
        do {
            state = .connecting
            try manager.connection.startVPNTunnel()
            refreshStatus()
        } catch {
            state = .failed("无法启动系统 VPN：\(error.localizedDescription)")
        }
    }

    func disconnect() {
        manager.connection.stopVPNTunnel()
        refreshStatus()
    }

    func forget() async {
        let reference = (manager.protocolConfiguration as? NEVPNProtocolIKEv2)?.passwordReference
        manager.connection.stopVPNTunnel()
        do {
            try await removePreferences()
            IKEv2CredentialStore.deletePassword(reference: reference)
            configuration = nil
            state = .unpaired
        } catch {
            state = .failed("移除此设备配置失败：\(error.localizedDescription)")
        }
    }

    func reload() async {
        do {
            try await loadPreferences()
            guard let ikev2 = manager.protocolConfiguration as? NEVPNProtocolIKEv2,
                  let server = ikev2.serverAddress, let username = ikev2.username else {
                configuration = nil
                state = .unpaired
                return
            }
            let label = manager.localizedDescription ?? "校园网连接管家"
            let device = label.components(separatedBy: " · ").last ?? label
            configuration = Configuration(deviceName: device, serverAddress: server,
                                           username: username)
            refreshStatus()
        } catch {
            state = .failed("无法读取系统 VPN 配置：\(error.localizedDescription)")
        }
    }

    private func refreshStatus() {
        switch manager.connection.status {
        case .invalid:
            state = configuration == nil ? .unpaired : .failed("系统 VPN 配置无效，请重新导入设备配置。")
        case .disconnected:
            state = configuration == nil ? .unpaired : .disconnected
        case .connecting, .reasserting:
            state = .connecting
        case .connected:
            state = .connected
        case .disconnecting:
            state = .disconnecting
        @unknown default:
            state = .failed("系统返回未知 VPN 状态。")
        }
    }

    private func loadPreferences() async throws {
        try await withCheckedThrowingContinuation { continuation in
            manager.loadFromPreferences { error in
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume() }
            }
        }
    }

    private func savePreferences() async throws {
        try await withCheckedThrowingContinuation { continuation in
            manager.saveToPreferences { error in
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume() }
            }
        }
    }

    private func removePreferences() async throws {
        try await withCheckedThrowingContinuation { continuation in
            manager.removeFromPreferences { error in
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume() }
            }
        }
    }
}
