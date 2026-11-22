# DragonZpyder Beta — Google Play release gate (2026-11-22)

**Not an authorization to publish.** This checklist separates source changes from verified live acceptance. The Android app currently uses DragonZpyder's HTTPS host and existing delegated Operly Personal session endpoints. Do not claim first-party identity completion merely because a frontend build passes.

## Store identity and technical submission

- Proposed title: **DragonZpyder Beta**. Package: `xyz.dragonzpyder.android` (must be checked against every existing Play listing before first upload).
- Release version: `0.9.0-beta.1`, version code `12` (must exceed the largest version code already uploaded to this Play app).
- Compile and target **Android API 36**, Android Gradle Plugin 8.11.1 and Gradle 8.13, Java 17.
- Upload **signed `.aab`**, not debug APK. Use Play App Signing and a dedicated upload key; protect the key material outside the repository and keep a backup. Never log passwords or include provider/API keys inside the binary.
- `android-play-beta.yml` is manual only: it does NOT connect to or upload to Google Play. Configure these Actions secrets to run it: `DZ_ANDROID_KEYSTORE_B64`, `DZ_ANDROID_STORE_PASSWORD`, `DZ_ANDROID_KEY_ALIAS`, `DZ_ANDROID_KEY_PASSWORD`. The base64 secret is the full JKS/keystore content encoded as base64. This workflow produces a signed AAB and graphics as short-lived artifacts.
- `prepare-brand.sh` downloads a pinned, hash-checked official favicon; `prepare-beta-brand.py` derives a beta launcher icon and store icon/feature graphic. Do not replace the official brand with an unrelated generated mascot. Check visual output on device and against Play asset guidelines.
- Verify AAB signature, `targetSdk`, install and update behavior with an actual Play-delivered build. Never upload a bundle signed with a throwaway key if an existing Play app already expects a different upload certificate.

## Mandatory Play Console declarations / content

- [ ] Confirm the original 2020 developer account is still active and has completed the account verification required for older accounts. The 12-tester/14-day policy targets personal accounts created **after November 13, 2023**; it ordinarily should not apply to a qualifying 2020 account, but verify Play Console's actual dashboard.
- [ ] Create app or choose the correct existing app. Confirm package ownership, app-signing policy, app access and track availability.
- [ ] Set app category, contact email, website, accurate short/full description, target countries, target audience, content rating, and ads declarations.
- [ ] Complete **Data safety** from observed production behavior, including account identifiers, prompts, stored messages, attachments, third-party model/hosting subprocessors, encryption in transit, sharing and deletion. Do not mark data as uncollected merely because it is proxied.
- [ ] Publish current **Android-specific privacy policy** URL both inside the app and on the store listing; the existing `web/privacy.html` describes an early-access web + Operly architecture and must be reviewed for exact current Android behavior and any first-party cutover.
- [ ] Implement and verify **in-app account deletion request** and a working **public web deletion-request page**. Confirm deletion propagation to DragonZpyder, Operly, retained chat/history, memory, connected providers and backups as applicable, with any lawful exceptions clearly disclosed. UI-only removal is insufficient.
- [ ] Implement and verify in-app **offensive AI content reporting/flagging** accessible from generated output without leaving the app. Ensure a real moderated/persisted server-side report path. Neither an inert button nor only an external email link meets this acceptance gate.
- [ ] Supply Play reviewers an active, least-privileged **demo/test account** and complete review instructions. It must reach functional chat without privileged business workspace access.
- [ ] If Google/Discord sign-in are advertised, complete legitimate OAuth/native deep-link flows and validate account identity isolation on Android; these flows were not confirmed in this branch and must not be promised in listing copy.

## Functional acceptance gates — must test real deployed backend

- [ ] All PR CI checks pass on the exact candidate SHA; `Android APK` emulator tests and a manual signed AAB build are green.
- [ ] Test email sign-up, verification, resend, password reset, login, secure password masking, session restoration, logout and failed-token flows on physical Android devices.
- [ ] Two-account isolation: no chat, memory, connected account, approval or workspace authority leaks across users/devices.
- [ ] Test real agent chat, streaming/cancellation, conversation recovery, attachments, model selection, voice dictation/TTS and responsive UI in light/dark, large fonts, rotation and keyboard.
- [ ] Verify AI content report and account deletion end-to-end, including read-back and audit evidence.
- [ ] Crash and ANR monitoring ready for a staged launch. Screenshot and store graphics must represent the actual installed Android app, not fabricated product functionality.
- [ ] Internal testing track, tester install from Play, and Google Play pre-launch report reviewed; fix blocking issues before production submission.
- [ ] Revalidate privacy policy and declarations if the first-party DragonZpyder identity migration PR is later merged. Do not merge that migration into the Android release merely to meet this deadline.

## Submission path

1. GitHub PR: review/reconcile Android beta release changes, validate CI, merge intentionally.
2. Configure upload-key secrets, run manual **Android Play Beta Bundle** workflow on the desired branch/revision and inspect artifacts.
3. In verified Play Console account: create/select app; fill declarations, store listing and app access; upload AAB first to internal testing.
4. Run Play-installed acceptance; use staged production rollout only after launch gates are met and Google has approved the application.

Official references:
- https://support.google.com/googleplay/android-developer/answer/11926878
- https://support.google.com/googleplay/android-developer/answer/14151465
- https://support.google.com/googleplay/android-developer/answer/10144311
- https://support.google.com/googleplay/android-developer/answer/13327111
- https://support.google.com/googleplay/android-developer/answer/13985936
- https://support.google.com/googleplay/android-developer/answer/9866151
- https://support.google.com/googleplay/android-developer/answer/9842756
