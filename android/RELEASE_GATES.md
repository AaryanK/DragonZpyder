# DragonZpyder Android v1.0 release gates

All ten gates require evidence from the exact release commit and deployed API.
An implemented code path, a debug APK, or a green general CI job is not sufficient.

| Gate | Required acceptance evidence |
|---|---|
| Lifecycle | Activity recreation, process kill, cold restore, account switch, network loss, no duplicate submission. |
| Streaming/cancellation | Actual first-party agent stream, disconnect/reconnect, server cancellation, no replay or rollback claims, final durable response. |
| Request identity | Concurrent PostgreSQL duplicate requests, payload conflict, unknown outcome, restart and cross-user denial. |
| Rich response | Markdown, tables, code copy, links, inline/block equations, execution receipt truthfulness, malformed/large content, both themes. |
| Realtime voice | Authorized physical-device audio in/out, mute, denied/revoked microphone, interruption, foreground exit, hangup, expired-call reconciliation and provider billing cap. |
| Workflows | First-party create/schedule, inspect durable receipts, cancellation and permission renewal on real Hatchet wakes. Legacy Operly authority cannot be reused implicitly. |
| MCP | Native OAuth provider consent, original session/device proof, replay/cross-account rejection, refresh/revocation, actual authorized provider read. |
| Adaptive/accessibility | Phone/tablet, API 26 and 36, 200% text, portrait/landscape, IME, TalkBack, contrast and 48dp targets. |
| Physical devices | At least one ARM64 phone and tablet/large-screen device, install/update, actual mic and camera, 16KB page-size device, crash-free test run. |
| Release | API 36, release tests, verified upload certificate, signed AAB, 16KB native-library compatibility, Play internal test and privacy/data-safety review. |

## Rollout dependencies (backend PR #141)
Apply request-ledger and voice migrations to the agent database; apply native OAuth handoff migration to the MCP credential database. Use the authorized migration role. Keep feature flags off until tests and isolated runtime checks pass. Existing MCP egress and read-only policy remain in effect. Voice requires a dedicated, capped provider project/key; it is audio conversation only and has no agent tool access.

## Physical-device evidence
Run `bash android/qualify-device.sh <device-serial> <apk>` from repository root.
The script collects install and launch evidence, not a full pass. Record each
matrix case with device/OS, commit, APK SHA-256, observed result and redacted
failure evidence. Do not commit account credentials, tokens, private chats or
raw logs. Test a real device with `adb shell getconf PAGE_SIZE` = 16384.

## Signing
Use the existing Play upload key if the application already has one. Configure
the protected GitHub environment `android-release` with
`DZ_ANDROID_KEYSTORE_B64`, `DZ_ANDROID_STORE_PASSWORD`,
`DZ_ANDROID_KEY_ALIAS`, `DZ_ANDROID_KEY_PASSWORD` and the variable
`DZ_ANDROID_UPLOAD_CERT_SHA256`. Never send signing secrets in chat.
Require deployment reviewers and access restricted to develop. After verified
merge and qualification, manually run Android Signed Release on develop.
The workflow builds and verifies the APK/AAB; publication is separately controlled.
