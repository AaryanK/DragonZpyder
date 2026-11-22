# DragonZpyder Android preview

Install the debug APK from the Android APK GitHub Actions artifact. This is a lightweight Android launcher for the existing live React product at https://dragonzpyder.xyz/app, not a duplicate agent runtime or an offline native rewrite.

The device browser handles authentication, cookies, microphone/camera prompts, downloads, uploads and browser speech APIs. Actual functionality is subject to browser support and existing server configuration. Nothing adds access to user data or provider keys. The launcher first attempts a Trusted Web Activity (TWA); until the deployed HTTPS site verifies the signing certificate through Digital Asset Links, compatible browsers display the browser origin bar. Standard browser fallback is intentional. No production changes are made.

Build with JDK 17, Android SDK 35 and Gradle 8.9:

    cd android
    gradle :app:assembleDebug

APK: app/build/outputs/apk/debug/app-debug.apk

This is a debug build for testing, not Play Store release signing. CI debug keys may change; uninstall an earlier debug build if Android rejects the update due to a signature mismatch. For a stable signed release, provision a release key outside source, publish matching package and SHA-256 certificate in /.well-known/assetlinks.json on dragonzpyder.xyz, validate navigation/fullscreen on device, and audit login, chat, voice, upload, sign-out and revocation. No offline capability is claimed.
