import SwiftUI
import UniformTypeIdentifiers

@main
struct CampusNetCompanionApp: App {
    var body: some Scene { WindowGroup { CompanionHome() } }
}

struct CompanionHome: View {
    @StateObject private var tunnel = TunnelManager()
    @State private var isImporting = false
    @State private var message = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Image(systemName: "network.badge.shield.half.filled")
                    .font(.system(size: 60)).foregroundStyle(.blue)
                Text("校园网连接管家").font(.largeTitle.bold())
                Text("使用 iPhone 系统 IKEv2 VPN").foregroundStyle(.secondary)
                statusCard
                Button("导入 Mac 设备配置", systemImage: "square.and.arrow.down") {
                    isImporting = true
                }
                .buttonStyle(.borderedProminent).controlSize(.large)
                HStack {
                    Button("连接", systemImage: "network") { tunnel.connect() }
                        .buttonStyle(.borderedProminent)
                        .disabled(tunnel.configuration == nil || tunnel.state == .connected)
                    Button("断开", systemImage: "xmark") { tunnel.disconnect() }
                        .buttonStyle(.bordered)
                        .disabled(tunnel.configuration == nil)
                }
                Button("移除此设备", role: .destructive) { Task { await tunnel.forget() } }
                    .disabled(tunnel.configuration == nil)
                Spacer()
                Text("先在 iPhone 安装 Mac 提供的 IKEv2 根证书，再导入此设备的 .ikev2.json。配置文件含专用 VPN 密码，请仅用 AirDrop 或 USB 传输并在导入后删除。首次保存时，iOS 会要求确认添加 VPN 配置。")
                    .multilineTextAlignment(.center).font(.footnote).foregroundStyle(.secondary)
            }
            .padding()
            .fileImporter(isPresented: $isImporting,
                          allowedContentTypes: [.json],
                          allowsMultipleSelection: false) { result in
                switch result {
                case .success(let urls):
                    guard let url = urls.first else { return }
                    let didAccess = url.startAccessingSecurityScopedResource()
                    defer { if didAccess { url.stopAccessingSecurityScopedResource() } }
                    do {
                        let data = try Data(contentsOf: url)
                        Task { await tunnel.importConfiguration(data) }
                    } catch {
                        message = "无法读取配置文件：\(error.localizedDescription)"
                    }
                case .failure(let error):
                    message = "未能导入配置：\(error.localizedDescription)"
                }
            }
            .alert("设备配置", isPresented: .init(get: { !message.isEmpty }, set: { if !$0 { message = "" } })) {
                Button("好", role: .cancel) {}
            } message: { Text(message) }
        }
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(tunnel.state.title, systemImage: "circle.fill")
                .foregroundStyle(tunnel.state == .connected ? .green : .secondary)
            if let config = tunnel.configuration {
                Text("设备：\(config.deviceName)")
                Text("服务器：\(config.serverAddress)")
                Text("账号：\(config.username)")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding().background(.thinMaterial).clipShape(.rect(cornerRadius: 16))
    }
}
