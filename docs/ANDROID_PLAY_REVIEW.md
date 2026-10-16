# Android / Google Play 审核材料草案

更新日期：2026-10-16  
适用功能：用户启动的校园网认证与前台保活（`campusguard`）

> 这是供 Play Console 填报前校对的事实草案，不构成 Google Play 政策批准或上架通过。服务用途和视频仍须在真实 APK/设备上确认。

## 前台服务申报草案

**Foreground service type**：`specialUse`  
**Subtype 建议值**：`User-requested campus network authentication and connectivity keepalive`

**政策适用性风险**：Google Play 前台服务政策要求用途与核心功能相关、由用户启动或可见、可由用户停止、被延迟/中断会造成负面影响，并且只在必要时运行。当前实现明确覆盖用户启动、持续通知和应用内停止；“持续运行并每分钟检查”的必要性以及替代 API 是否合适，仍需用真实设备场景向 Play 解释，最终是否获准由 Google 审核决定。

**功能说明**：用户在应用内填写校园网认证档案并主动开启保活后，应用以前台服务每 60 秒检查认证状态与互联网连通性；发现认证掉线时尝试重新登录并再次检查。服务使用持续通知告知用户当前正在运行，用户可回到应用停止服务。认证服务器不可达时，服务进入休眠状态，不执行登录。

**若服务被延迟或中断，对用户的影响**：校园网认证会话过期或被网络踢下线后，设备可能失去校园网访问能力；在保活恢复前，用户需要重新打开应用并手动登录。服务未开启时，不会后台保活。

**用户触发与停止步骤**：

1. 在真实 Android 设备安装本次待审核构建。
2. 填写测试校园网账号、认证服务器和运营商，点“立即登录”。
3. 允许通知后点“开启保活”；确认持续通知出现。
4. 将应用切到后台并锁屏，展示服务仍处于运行状态。
5. 返回应用点“停止保活”，确认通知和服务状态停止。

**演示视频要求**：录制以上流程，清晰展示用户主动开启、持续通知、锁屏期间运行和用户停止。视频不要暴露真实账号、密码、个人信息或可用的校园网络凭据。提交前用 Play Console 支持的可访问视频链接替换此说明。

## 提交前需核实

- [ ] 用最终签名的 APK/AAB 在实体设备复核开启、通知、锁屏运行、停止、网络恢复与 Keystore 档案解密。
- [ ] 在 Play Console 的 App content 中申报 `specialUse` 服务，填写最终功能说明和中断影响，并附上述视频链接。
- [ ] 根据真实数据流完成 Data safety 表、隐私政策和审核访问说明；不要根据本草案推断数据收集或共享答案。
- [ ] 验证商店 package id、版本号、签名证书和 Play App Signing 配置与已有应用一致。
- [ ] 若开发者是 2023-11-13 后创建的个人 Play 账号，先满足封闭测试要求，再申请生产访问。

## 当前发布证据边界

- 源码中的服务由用户主动启动，可见通知并可从应用停止；API 36 Manifest 构建门禁已通过。
- unsigned AAB 不是可上传 Play 的正式 bundle。GitHub Actions 当前没有 `ANDROID_KEYSTORE_BASE64`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD` 这些签名 secrets。
- API 36 模拟器启动 workflow 已加入，但须等 run `38892862907` 完成；模拟器证据仍不替代实体 Android 设备验收。
- Google Play 对 Android 14+ 要求在 Manifest 声明前台服务类型，并在 Play Console 为类型填写说明、用户影响和视频；最终是否接受由 Play 审核决定。
- 截至本文件日期，新应用和应用更新需 target Android 16 / API 36，政策生效日为 2026-08-31；当前 `mobile/buildozer.spec` 已设 API 36。
- 若 Play 开发者账号是 2023-11-13 后创建的个人账号，生产访问申请前需至少 12 位测试者连续参加封闭测试 14 天；账号类型和创建时间尚未核实。

## 官方参考

- [Google Play：Understanding foreground service and full-screen intent requirements](https://support.google.com/googleplay/android-developer/answer/13392821)
- [Google Play：Developer Program Policy — Permissions for Foreground Services](https://support.google.com/googleplay/android-developer/answer/18258653)
- [Google Play：Target API level requirements](https://support.google.com/googleplay/android-developer/answer/11926878)
- [Google Play：Testing requirements for new personal developer accounts](https://support.google.com/googleplay/android-developer/answer/14151465)
