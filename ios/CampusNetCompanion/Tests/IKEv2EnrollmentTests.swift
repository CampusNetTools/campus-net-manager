import XCTest
@testable import CampusNetCompanion

final class IKEv2EnrollmentTests: XCTestCase {
    func testDecodesGeneratedStyleEnrollment() throws {
        let enrollment = try IKEv2Enrollment.decode(payload())

        XCTAssertEqual(enrollment.deviceName, "iphone-1")
        XCTAssertEqual(enrollment.serverAddress, "10.12.72.55")
        XCTAssertEqual(enrollment.serverIdentifier, "vpn.campusnet.local")
        XCTAssertEqual(enrollment.username, "iphone-0123456789abcdef")
    }

    func testAcceptsValidIPv6ServerAddress() throws {
        let enrollment = try IKEv2Enrollment.decode(
            payload(serverAddress: "2001:db8::42")
        )

        XCTAssertEqual(enrollment.serverAddress, "2001:db8::42")
    }

    func testRejectsMalformedIPv6Addresses() {
        for address in [":::1", "2001::gg", "2001:db8:1"] {
            XCTAssertThrowsError(try IKEv2Enrollment.decode(payload(serverAddress: address)),
                                 "Expected \(address) to be rejected")
        }
    }

    func testRejectsMalformedNumericIPv4Address() {
        XCTAssertThrowsError(
            try IKEv2Enrollment.decode(payload(serverAddress: "999.1.1.1"))
        )
    }

    func testRejectsInvalidServerIdentifierAndEmptyCredentials() {
        XCTAssertThrowsError(
            try IKEv2Enrollment.decode(payload(serverIdentifier: "vpn..campusnet.local"))
        )
        XCTAssertThrowsError(
            try IKEv2Enrollment.decode(payload(username: ""))
        )
        XCTAssertThrowsError(
            try IKEv2Enrollment.decode(payload(password: ""))
        )
    }

    func testRejectsUnsupportedEnrollmentVersion() {
        XCTAssertThrowsError(try IKEv2Enrollment.decode(payload(version: 2)))
    }

    private func payload(
        version: Int = 1,
        serverAddress: String = "10.12.72.55",
        serverIdentifier: String = "vpn.campusnet.local",
        username: String = "iphone-0123456789abcdef",
        password: String = "one-time-test-password"
    ) -> Data {
        let object: [String: Any] = [
            "version": version,
            "deviceName": "iphone-1",
            "serverAddress": serverAddress,
            "serverIdentifier": serverIdentifier,
            "username": username,
            "password": password,
        ]
        return try! JSONSerialization.data(withJSONObject: object)
    }
}
