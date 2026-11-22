# DragonZpyder native Android preview (0.4.0)

Native Android Activity, widgets and HTTPS client. No browser wrapper, Custom Tabs, or WebView. Uses the existing DragonZpyder public user-session API at dragonzpyder.xyz; the backend currently proxies Personal authentication and chat to Operly. Private inference tokens are never embedded.

Included: email/password sign-in, Personal scope validation, agent chat, server conversation history, AI Mesh text model selection, system speech dictation and text-to-speech, read-only pending approvals, logout. Session cookies are held in process memory only; a cold restart requires sign-in. Voice is turn-based, not realtime WebRTC. Google sign-in, signup, approval execution, streaming, persistent secure login, and realtime companion are not yet implemented. No backend changes.

Build with JDK 17, SDK 35 and Gradle 8.9:
    cd android
    bash prepare-brand.sh
    gradle :app:assembleDebug :app:lintDebug

APK artifact: DragonZpyder-Android-debug. Debug signing only. If signatures differ, uninstall the prior preview before installing. Test login, chat, conversation restoration, text model selection, dictation and logout on a real device before claiming functional parity.

Version 0.3.0 sends exact host-bound production cookies and the matching session CSRF value, checks the current session before switching scope, and compiles the website's pinned official logo into the package. No backend exemptions were added. Verify successful sign-in on device before certifying authentication.

The native screen now follows the website PersonalTemplate.jsx, workspace.css and ui-v1.css (current light default and orange-accent dark appearance), with matching welcome copy, sidebar search, theme switching, command menu, and native document/photo selection for AI Mesh. Realtime voice, capture, account management and approval execution remain incomplete. Exact visual parity requires side-by-side device screenshot testing.
