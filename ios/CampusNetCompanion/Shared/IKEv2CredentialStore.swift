import Foundation
import Security

enum IKEv2CredentialStore {
    private static let service = "com.campusnettools.companion.ikev2"

    static func savePassword(_ password: String) throws -> Data {
        let account = UUID().uuidString
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
            kSecValueData as String: Data(password.utf8),
            kSecReturnPersistentRef as String: true,
        ]
        var result: CFTypeRef?
        let status = SecItemAdd(query as CFDictionary, &result)
        guard status == errSecSuccess, let reference = result as? Data else {
            throw CredentialStoreError.keychain(status)
        }
        return reference
    }

    static func deletePassword(reference: Data?) {
        guard let reference else { return }
        SecItemDelete([kSecValuePersistentRef as String: reference] as CFDictionary)
    }
}

private enum CredentialStoreError: LocalizedError {
    case keychain(OSStatus)

    var errorDescription: String? {
        switch self {
        case .keychain(let status):
            return "无法将 VPN 凭据安全保存到钥匙串（错误 \(status)）。"
        }
    }
}
