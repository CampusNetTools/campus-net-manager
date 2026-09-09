import CryptoKit
import Foundation
import Network
import Security

enum GatewayFrame: UInt8 { case handshake = 0x01, packet = 0x02, heartbeat = 0x03, status = 0x04, error = 0x7f }

/// 封帧和传输层，不检查或持久化任何用户数据包内容。
final class GatewayTransport {
    private var connection: NWConnection?
    private var receiveBuffer = Data()
    private let queue = DispatchQueue(label: "com.campusnettools.gateway-wire")
    private var startCompletion: ((Error?) -> Void)?
    private var didAuthenticate = false
    var onFrame: ((GatewayFrame, Data) -> Void)?
    var onFailure: ((Error) -> Void)?

    func start(host: String, port: UInt16, token: String, certificatePinSHA256: String,
               completion: @escaping (Error?) -> Void) {
        guard let expectedPin = Data(hexadecimalString: certificatePinSHA256), expectedPin.count == 32 else {
            completion(TunnelWireError.invalidCertificatePin)
            return
        }
        // 只接受系统信任且叶证书 SHA-256 与二维码一致的 TLS 端点。没有匹配的证书时
        // 宁可拒绝连接，也绝不退回明文或把未经认证的网关显示为“已连接”。
        let tls = NWProtocolTLS.Options()
        sec_protocol_options_set_verify_block(tls.securityProtocolOptions, { _, trust, verifyComplete in
            let secTrust = sec_trust_copy_ref(trust).takeRetainedValue()
            var trustError: CFError?
            guard SecTrustEvaluateWithError(secTrust, &trustError),
                  let certificate = SecTrustGetCertificateAtIndex(secTrust, 0) else {
                verifyComplete(false)
                return
            }
            let certificateData = SecCertificateCopyData(certificate) as Data
            let actualPin = Data(SHA256.hash(data: certificateData))
            verifyComplete(actualPin.constantTimeEquals(expectedPin))
        }, queue)
        let parameters = NWParameters(tls: tls, tcp: NWProtocolTCP.Options())
        startCompletion = completion
        didAuthenticate = false
        let connection = NWConnection(host: NWEndpoint.Host(host), port: NWEndpoint.Port(rawValue: port)!, using: parameters)
        self.connection = connection
        connection.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                self?.send(.handshake, body: Data(token.utf8))
                self?.receiveNext()
            case .failed(let error): self?.fail(error)
            case .cancelled: break
            default: break
            }
        }
        connection.start(queue: queue)
    }

    func sendPacket(_ packet: Data, family: Int32) {
        let marker: UInt8 = family == AF_INET6 ? 6 : 4
        send(.packet, body: Data([marker]) + packet)
    }

    func stop() {
        connection?.cancel()
        connection = nil
        receiveBuffer.removeAll()
        startCompletion = nil
        didAuthenticate = false
    }

    private func send(_ type: GatewayFrame, body: Data) {
        guard body.count < 16 * 1024 * 1024 else { return }
        var size = UInt32(body.count + 1).bigEndian
        var data = Data(bytes: &size, count: 4)
        data.append(type.rawValue); data.append(body)
        connection?.send(content: data, completion: .contentProcessed { [weak self] error in
            if let error { self?.fail(error) }
        })
    }

    private func receiveNext() {
        connection?.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { [weak self] data, _, complete, error in
            guard let self else { return }
            if let data { self.receiveBuffer.append(data); self.consumeFrames() }
            if let error { self.fail(error); return }
            if complete {
                if !self.didAuthenticate { self.fail(TunnelWireError.gatewayClosedDuringAuthentication) }
                return
            }
            self.receiveNext()
        }
    }

    private func consumeFrames() {
        while receiveBuffer.count >= 5 {
            let length = receiveBuffer.prefix(4).withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
            guard length > 0 && length < 16 * 1024 * 1024 else { fail(TunnelWireError.invalidFrame); return }
            guard receiveBuffer.count >= Int(length) + 4 else { return }
            guard let type = GatewayFrame(rawValue: receiveBuffer[4]) else { receiveBuffer.removeFirst(Int(length) + 4); continue }
            let body = receiveBuffer.subdata(in: 5..<(Int(length) + 4))
            receiveBuffer.removeFirst(Int(length) + 4)
            switch type {
            case .status where body == Data("ready".utf8):
                didAuthenticate = true
                finishStart(nil)
            case .error:
                fail(TunnelWireError.gatewayRejectedAuthentication)
                return
            default:
                onFrame?(type, body)
            }
        }
    }

    private func finishStart(_ error: Error?) {
        let completion = startCompletion
        startCompletion = nil
        completion?(error)
    }

    private func fail(_ error: Error) {
        if startCompletion != nil {
            finishStart(error)
            connection?.cancel()
        } else {
            onFailure?(error)
        }
    }
}

private extension Data {
    init?(hexadecimalString: String) {
        guard hexadecimalString.count == 64 else { return nil }
        var bytes = [UInt8]()
        bytes.reserveCapacity(32)
        var index = hexadecimalString.startIndex
        while index < hexadecimalString.endIndex {
            let next = hexadecimalString.index(index, offsetBy: 2)
            guard let byte = UInt8(hexadecimalString[index..<next], radix: 16) else { return nil }
            bytes.append(byte)
            index = next
        }
        self.init(bytes)
    }

    func constantTimeEquals(_ other: Data) -> Bool {
        guard count == other.count else { return false }
        return zip(self, other).reduce(UInt8(0)) { $0 | ($1.0 ^ $1.1) } == 0
    }
}

enum TunnelWireError: LocalizedError {
    case invalidFrame, invalidCertificatePin, gatewayRejectedAuthentication, gatewayClosedDuringAuthentication
    var errorDescription: String? {
        switch self {
        case .invalidFrame: return "电脑网关发送了无效的隧道数据。"
        case .invalidCertificatePin: return "配对码的电脑证书指纹无效。"
        case .gatewayRejectedAuthentication: return "电脑网关拒绝了配对令牌，请重新扫码。"
        case .gatewayClosedDuringAuthentication: return "电脑网关在完成配对认证前断开。"
        }
    }
}
