import SwiftUI
import AVFoundation

@main
struct CampusNetCompanionApp: App {
    var body: some Scene { WindowGroup { CompanionHome() } }
}

struct CompanionHome: View {
    @StateObject private var tunnel = TunnelManager()
    @State private var showScanner = false
    @State private var message = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 22) {
                Image(systemName: "network.badge.shield.half.filled")
                    .font(.system(size: 64)).foregroundStyle(.blue)
                Text("校园网连接管家").font(.largeTitle.bold())
                Text("手机 VPN 隧道配套端").foregroundStyle(.secondary)
                statusCard
                Button("扫描电脑配对码", systemImage: "qrcode.viewfinder") { showScanner = true }
                    .buttonStyle(.borderedProminent).controlSize(.large)
                HStack {
                    Button("连接") { tunnel.connect() }.buttonStyle(.borderedProminent)
                        .disabled(tunnel.pairing == nil)
                    Button("断开") { tunnel.disconnect() }.buttonStyle(.bordered)
                }
                Button("移除此设备") { tunnel.forget() }.foregroundStyle(.red)
                    .disabled(tunnel.pairing == nil)
                Spacer()
                Text("首次连接时，iOS 会要求你确认添加 VPN 配置。\n不会读取聊天内容、浏览内容或校园网密码。")
                    .multilineTextAlignment(.center).font(.footnote).foregroundStyle(.secondary)
            }
            .padding()
            .sheet(isPresented: $showScanner) {
                QRScanner { result in
                    showScanner = false
                    switch result {
                    case .success(let code):
                        do { Task { await tunnel.importPairing(try PairingPayload.decodeQR(code)) } }
                        catch { message = error.localizedDescription }
                    case .failure(let error): message = error.localizedDescription
                    }
                }
            }
            .alert("无法配对", isPresented: .init(get: { !message.isEmpty }, set: { if !$0 { message = "" } })) {
                Button("好", role: .cancel) {}
            } message: { Text(message) }
        }
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(tunnel.state.title, systemImage: "circle.fill")
                .foregroundStyle(tunnel.state == .connected ? .green : .secondary)
            if let pairing = tunnel.pairing {
                Text("电脑：\(pairing.gatewayHost):\(pairing.gatewayPort)")
                Text("配对有效期：\(pairing.expiresAt.formatted())").font(.caption).foregroundStyle(.secondary)
            }
        }.frame(maxWidth: .infinity, alignment: .leading).padding().background(.thinMaterial).clipShape(.rect(cornerRadius: 16))
    }
}

struct QRScanner: UIViewControllerRepresentable {
    let completion: (Result<String, Error>) -> Void
    func makeUIViewController(context: Context) -> ScannerController { ScannerController(completion: completion) }
    func updateUIViewController(_ uiViewController: ScannerController, context: Context) {}
}

final class ScannerController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    private let session = AVCaptureSession(); private let completion: (Result<String, Error>) -> Void
    init(completion: @escaping (Result<String, Error>) -> Void) { self.completion = completion; super.init(nibName: nil, bundle: nil) }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func viewDidLoad() { super.viewDidLoad()
        guard let camera = AVCaptureDevice.default(for: .video), let input = try? AVCaptureDeviceInput(device: camera), session.canAddInput(input) else { completion(.failure(PairingError.invalidQRCode)); return }
        session.addInput(input); let output = AVCaptureMetadataOutput(); session.addOutput(output); output.setMetadataObjectsDelegate(self, queue: .main); output.metadataObjectTypes = [.qr]
        let preview = AVCaptureVideoPreviewLayer(session: session); preview.frame = view.bounds; preview.videoGravity = .resizeAspectFill; view.layer.addSublayer(preview); session.startRunning()
    }
    func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput objects: [AVMetadataObject], from connection: AVCaptureConnection) { guard let text = (objects.first as? AVMetadataMachineReadableCodeObject)?.stringValue else { return }; session.stopRunning(); completion(.success(text)) }
}
