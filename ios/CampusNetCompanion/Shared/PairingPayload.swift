import Foundation

/// QR 内容；仅可使用一次的令牌绝不写入日志或屏幕截图。
struct PairingPayload: Codable, Equatable {
    let version: Int
    let gatewayHost: String
    let gatewayPort: UInt16
    let enrollmentToken: String
    let certificatePinSHA256: String
    let expiresAt: Date

    var isExpired: Bool { expiresAt <= Date() }

    static func decodeQR(_ text: String) throws -> PairingPayload {
        guard let url = URL(string: text), url.scheme == "campusnet", url.host == "pair" else {
            throw PairingError.invalidQRCode
        }
        guard let encoded = URLComponents(url: url, resolvingAgainstBaseURL: false)?
            .queryItems?.first(where: { $0.name == "payload" })?.value,
              let data = Data(base64Encoded: encoded) else {
            throw PairingError.invalidQRCode
        }
        let value = try JSONDecoder.campus.decode(PairingPayload.self, from: data)
        let validCertificatePin = value.certificatePinSHA256.count == 64
            && value.certificatePinSHA256.allSatisfy { $0.isHexDigit }
        guard value.version == 1, !value.gatewayHost.isEmpty, value.gatewayPort > 0,
              !value.enrollmentToken.isEmpty, validCertificatePin else {
            throw PairingError.invalidQRCode
        }
        guard !value.isExpired else { throw PairingError.expired }
        return value
    }
}

enum PairingError: LocalizedError {
    case invalidQRCode, expired
    var errorDescription: String? {
        switch self {
        case .invalidQRCode: return "这不是校园网连接管家的有效配对码。"
        case .expired: return "配对码已过期，请在电脑端重新生成。"
        }
    }
}

extension JSONDecoder {
    static let campus: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()
}
