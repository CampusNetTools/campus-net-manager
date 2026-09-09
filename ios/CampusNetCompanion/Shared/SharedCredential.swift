import Foundation
import Security

/// 主 App 和 Packet Tunnel 共用；只保存配对后交换的会话凭据。
enum SharedCredential {
    private static let service = "com.campusnettools.companion.gateway"
    private static let account = "paired-session"
    private static let group = "$(AppIdentifierPrefix)com.campusnettools.companion.shared"

    static func save(_ token: String) throws {
        let data = Data(token.utf8)
        SecItemDelete(query as CFDictionary)
        var add = query
        add[kSecValueData as String] = data
        let result = SecItemAdd(add as CFDictionary, nil)
        guard result == errSecSuccess else { throw CredentialError.keychain(result) }
    }

    static func load() throws -> String {
        var find = query
        find[kSecReturnData as String] = true
        find[kSecMatchLimit as String] = kSecMatchLimitOne
        var raw: CFTypeRef?
        let result = SecItemCopyMatching(find as CFDictionary, &raw)
        guard result == errSecSuccess, let data = raw as? Data,
              let value = String(data: data, encoding: .utf8) else {
            throw CredentialError.missing
        }
        return value
    }

    static func clear() { SecItemDelete(query as CFDictionary) }

    private static var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: account,
         kSecAttrAccessGroup as String: group]
    }
}

enum CredentialError: LocalizedError {
    case missing, keychain(OSStatus)
    var errorDescription: String? {
        switch self {
        case .missing: return "尚未完成安全配对。"
        case .keychain: return "无法安全保存配对凭据。"
        }
    }
}
