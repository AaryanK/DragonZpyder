# android/app/src/main/java/xyz/dragonzpyder/android

Native application source set or package namespace.

Read [repository instructions](../../../../../../../../AGENTS.md), [Android engineering contract](../../../../../../../../android/AGENTS.md), [Android code map](../../../../../../../../android/CODE_MAP.md), and [root codebase index](../../../../../../../../CODEBASE.md). Generated symbol pages provide checkout-specific navigation, not release evidence.

## Child directories

None.

## Files

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`AgentFileRepository.kt`](AgentFileRepository.kt) | Background content-resolver file upload, inventory and save; bounds file size and validates safe filenames and receipt IDs/digests. | Reviewed |
| [`AgentRequestViewModel.java`](AgentRequestViewModel.java) | Lifecycle-retained in-flight request and streaming outcome state, background executor and generation fencing; no Activity or automatic replay. | Reviewed |
| [`ApiRoutePolicy.java`](ApiRoutePolicy.java) | Explicit first-party route allowlist, preauth handling and CSRF header selection; prevents cross-realm fallback. | Reviewed |
| [`ChatPresentationState.kt`](ChatPresentationState.kt) | Immutable UI-only ChatScreenState snapshot updated through reducer bridge; no credentials or Activity references. | Reviewed |
| [`DragonApi.java`](DragonApi.java) | Fixed-origin native HTTP/session client; discovers runtime capabilities, routes authenticated requests, streams agent replies and manages request cancellation. | Reviewed |
| [`DragonDesignTokens.kt`](DragonDesignTokens.kt) | Shared light/dark brand tokens, Compose theme and transitional Java color adapter. | Reviewed |
| [`DragonNavigationRow.kt`](DragonNavigationRow.kt) | Compose navigation row with icon alignment, selection state and wrapping text for large fonts. | Reviewed |
| [`GoogleCredentialLogin.java`](GoogleCredentialLogin.java) | Native Android Credential Manager Google ID token request with supplied web client ID and nonce; handles credential outcomes. | Reviewed |
| [`MainActivity.java`](MainActivity.java) | Native ComponentActivity host coordinating Compose chat, auth, session restoration, attachments, files, voice, request state and compatibility actions. | Reviewed |
| [`MarkdownDocument.java`](MarkdownDocument.java) | Bounded CommonMark/GFM parser and plain-text extraction; does not render raw HTML or open links. | Reviewed |
| [`MarkdownRenderer.kt`](MarkdownRenderer.kt) | Compose rendering of markdown blocks, code, lists, tables, links and restored math markup. | Reviewed |
| [`MathMarkup.kt`](MathMarkup.kt) | Extracts math tokens while tracking code fences and inline code; preserves raw formulas for rendering. | Reviewed |
| [`MediaPayload.java`](MediaPayload.java) | Bounded base64 media decoding with explicit supported audio/image MIME prefixes. | Reviewed |
| [`MobileOAuthStore.java`](MobileOAuthStore.java) | Encrypted expiring single-attempt Discord PKCE device proof storage, verifier/challenge generation. | Reviewed |
| [`NativeChatView.kt`](NativeChatView.kt) | Compose native chat UI and Actions interface for navigation, composer, request state, account, files and product controls. | Reviewed |
| [`NativeCommandPalette.kt`](NativeCommandPalette.kt) | Compose searchable command dialog dispatching existing callbacks. | Reviewed |
| [`NativeVoiceSession.java`](NativeVoiceSession.java) | Foreground audio WebRTC session lifecycle, peer/audio resources, timeout and backend API integration; no provider secrets. | Reviewed |
| [`NativeVoiceView.kt`](NativeVoiceView.kt) | Compose voice presentation, animated orb, mute and end callbacks; transport lives separately. | Reviewed |
| [`NavigationGlyph.kt`](NavigationGlyph.kt) | Compose navigation icon drawing; inspect supported glyph names and semantics. | Indexed |
| [`PendingAgentRequestStore.java`](PendingAgentRequestStore.java) | Stores only request ID and verified first-party binding metadata for recovery; no prompt or credential storage. | Reviewed |
| [`SecurePasswordField.java`](SecurePasswordField.java) | Native password field behavior; inspect input type and visibility toggles. | Indexed |
| [`SecureSessionStore.java`](SecureSessionStore.java) | Authenticated cookie-pair storage encrypted with a non-exportable Android Keystore key. | Reviewed |
| [`SessionCookies.java`](SessionCookies.java) | Fixed-origin allowlisted cookie jar, separate first-party and compatibility session names, expiry and serialization. | Reviewed |
