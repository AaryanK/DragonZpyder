# DragonZpyder native Android preview (0.7.0)

Native Android Activity, widgets and HTTPS client. No browser wrapper, Custom Tabs, or WebView. Uses the existing DragonZpyder public user-session API at dragonzpyder.xyz; the backend currently proxies Personal authentication and chat to Operly. Private inference tokens are never embedded.

Included: email/password sign-in, Personal scope validation, agent chat, server conversation history, AI Mesh text model selection, system speech dictation and text-to-speech, read-only pending approvals, logout. The v0.7 implementation additionally supports Android Keystore-encrypted authenticated cookie persistence with expiry and server validation on launch; v0.7 tests are pending. Voice is turn-based, not realtime WebRTC. Google sign-in, streaming, and realtime companion are not yet implemented; v0.7 adds governed approval decision/execution and encrypted session restoration, pending integration tests. No backend changes.

Build with JDK 17, SDK 35 and Gradle 8.9:
    cd android
    bash prepare-brand.sh
    gradle :app:assembleDebug :app:lintDebug

APK artifact: DragonZpyder-Android-debug. Debug signing only. If signatures differ, uninstall the prior preview before installing. Test login, chat, conversation restoration, text model selection, dictation and logout on a real device before claiming functional parity.

Version 0.3.0 sends exact host-bound production cookies and the matching session CSRF value, checks the current session before switching scope, and compiles the website's pinned official logo into the package. No backend exemptions were added. Verify successful sign-in on device before certifying authentication.

The native screen now follows the website PersonalTemplate.jsx, workspace.css and ui-v1.css (current light default and orange-accent dark appearance), with matching welcome copy, sidebar search, theme switching, command menu, and native document/photo selection for AI Mesh. Realtime voice, capture, account management and approval execution remain incomplete. Exact visual parity requires side-by-side device screenshot testing.

Version 0.5.0 ports email sign-in, registration, verification/resend, password recovery and account profile editing from AccountTemplate.jsx and account.js. Displays backend-returned sign-in methods, sessions and workspaces, with confirmed server-side logout. Google sign-in and persistent encrypted session storage remain future work; on-device end-to-end authentication tests are required.

## v0.7 engineering candidate

Main chat is now a mounted Kotlin/Jetpack Compose workspace; authentication, account and menus still use native Views. The production endpoint and user-scoped authority remain unchanged. Android Keystore session encryption, expiry tests, Compose mounting tests and explicit approval review are added. These are not proof of working production sign-in or execution. Release signing accepts `DZ_ANDROID_KEYSTORE`, `DZ_ANDROID_STORE_PASSWORD`, `DZ_ANDROID_KEY_ALIAS`, `DZ_ANDROID_KEY_PASSWORD` from a trusted environment; never commit keys or passwords. Do not distribute a debug-signed build as production.

## v1.0 release gates

- Compile, lint, emulator credential masking, encrypted session restoration/tamper/logout, and Compose UI tests pass.
- Test real production login, sign-up, verification, reset, logout, and cold launch using authorized isolated accounts; check that business scope is not granted.
- Compare website and installed UI in both themes, phone and tablet dimensions, IME, TalkBack and large font. No clipping or blocked navigation.
- Confirm server conversation recovery, rich rendering, attachment MIME/size handling, timeout recovery without duplicate side effects; only expose streaming/cancel when backed by a tested API.
- Verify task discovery/recovery, connector status and approval review/decision/execution using isolated non-destructive fixtures; preserve user confirmation and frozen arguments.
- Verify realtime voice and other media against actual first-party gateway APIs; no service keys in APK.
- Stable release signing plus verified signature, install/update test and external device test. Never declare v1.0 from compile/lint alone.
