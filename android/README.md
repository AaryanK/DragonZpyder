# DragonZpyder native Android — v0.9.1 engineering candidate

Native Android Activity and Kotlin/Jetpack Compose chat. No embedded WebView. The first-party Web API selects its runtime using `GET /dz/status`. The APK never falls back to Operly after an explicit first-party cutover. Compatibility mode remains available only when the server explicitly returns false.

## Build
JDK 17, Android SDK 35, Gradle 8.9. Minimum API 26.
```sh
cd android
bash prepare-brand.sh
gradle :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
```

The GitHub Actions Android APK workflow checks the cookie and route contracts, builds and lints, runs parser tests and Android emulator tests on API 35 and API 26, then verifies and uploads a debug APK. This is not a production release.

## Runtime capability boundaries
- First-party: password login, Google login/signup, user-scoped encrypted session, profile, Personal Agent and its conversation history, explicit selection of existing authorized MCP accounts.
- Compatibility: legacy email signup/verification/reset, Discord device ticket flow (only if advertised by backend), AI Mesh chat and supported media, account/session/workspace views, legacy/Kernel approvals and workflow listing.
- First-party voice, Mesh, email recovery, Discord mobile handoff, and task/approval management are **not** exposed by the current server contract. Never send legacy credentials or call legacy routes in first-party mode. Use the website to authorize new MCP accounts; native selection uses only opaque connection aliases.
- Camera capture uses a dedicated non-exported FileProvider, sampled decoding, and bounded upload. Prior attachment payloads are not resent automatically; context omission is disclosed.

## v1.0 gates — remain open
1. New Android CI on both supported SDK levels; test reports retained.
2. Verify real authorized account login, Google onboarding, logout, cold start, and both runtime modes against their actual endpoints. No production business mutations in tests.
3. Verify account isolation, lifecycle/process restoration, keyboard, adaptive layouts, TalkBack, large fonts, slow/offline networks, unknown mutation outcomes, and physical-device install/update.
4. Complete server-supported idempotency and Agent streaming/cancellation; reconcile unknown execution outcomes without replay.
5. Complete first-party MCP authorization, workflow and approval integration, rich response rendering and realtime voice only after server contracts exist.
6. Production signing, signed AAB, release-mode tests, Play requirements, privacy disclosures, crash/performance monitoring.

Release signing uses `DZ_ANDROID_KEYSTORE`, `DZ_ANDROID_STORE_PASSWORD`, `DZ_ANDROID_KEY_ALIAS`, and `DZ_ANDROID_KEY_PASSWORD` supplied through an authorized secure environment. Never commit keys or passwords. Debug builds are for testing only.

The brand preparation command generates `R.drawable.brand_icon` as a vector from the shared `web/frontend/src/dz-mark.svg`; Android build and device verification are still required for changes.

The native composer exposes optional computer, media and durable work only when first-party status permits them, default-off and cleared on send or conversation change. The brand preparation script checks web/Android semantic palette parity. Dictation uses platform recognition, inserts text only and checks account binding. No provider activation or APK qualification implied.

When `voice_agent_enabled` and the ledger are advertised, the existing native WebRTC screen submits completed speech to the owner-scoped `/voice/{id}/turn` endpoint and reads the committed agent answer. Audio-only mode remains separately gated. Selected MCP aliases are fixed at session start; optional computer/media/scheduled-work consent is not inherited. The newer OpenRouter-only audio transport remains pending on PR #163.
