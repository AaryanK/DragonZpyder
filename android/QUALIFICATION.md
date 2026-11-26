# Android performance, accessibility and security qualification

Scope: mobile qualification only. Do not change production flags, database schemas,
provider credentials or the backend harness as part of this work.

## Verified baseline

Build #364 (commit `cbb574a11a309428ac0774544ddfeb2d6144e3a2`, workflow run
45727663230, attempt 2) completed build, lint, JVM tests, 15 instrumentation tests
on API 36 and 15 on API 26, ZIP 16 KiB alignment, and APK signature verification.
Artifact 15075997924 is a debug APK, not a signed production release.
Observed SHA-1 for build #364: C2:AD:C9:26:F0:4F:43:39:78:5A:78:D2:80:B5:97:E9:26:1D:FD:80.
It differs from #356; these CI debug signing certificates are not a stable
Google OAuth or upgrade identity. Do not use them for the public release.

## Automated changes in this qualification branch

- Compose navigation row at 200% font scale and 280dp width: visible selected
  state, accessible click, disabled state and minimum 48dp bounds.
- Command menu search, labeled dismiss and selection callbacks.
- First-party OAuth route allowlist, cross-realm rejection, cookie origin/path
  restrictions, partial session denial, malformed attachment receipt rejection.
- Native ELF segment inspection for every packaged 64-bit shared library,
  separate from ZIP alignment. Report and fail on incompatible load segments.
- Non-debuggable, profileable, separately installed benchmark APK, synthetic
  chat fixture limited to benchmark source set, no benchmark code in production.
- CI compiles benchmark code; emulator regression suite is still functional
  evidence only, not a production performance claim.

## Physical-device benchmarks

Use a dedicated authorized Android 10+ test device, with no personal account
or data. Build from the exact commit with clean working tree and SDK 36/JDK 17/
Gradle 8.11.1. Run from repository root:

    bash android/run-benchmarks.sh <device-serial>

This installs the separate `xyz.dragonzpyder.android.benchmark` package, uses
Macrobenchmark with CompilationMode.None, collects 20 cold-start iterations
and 10 synthetic-chat scroll iterations. The fixture does not call the harness.
Startup timing measures initial display, not authenticated session readiness.
The separate initial MainActivity startup may make unauthenticated status reads.
No signed release credentials or paid model calls are required.

Record commit, APK hash, device, OS, refresh rate, power/thermal conditions,
and median/p95 startup. Evaluate frameDurationCpuMs and, on API 31+,
frameOverrunMs including p50/p95/p99. Repeat with production-like compilation
and real authenticated chats after the backend integration. A fast first frame
alone is not a pass for the <1.5s usable UI target.

## Additional release qualification (still required)

| Area | Test protocol | Evidence |
|---|---|---|
| Startup | Fresh and returning sessions, online/offline/slow network, separate TTID and usable readiness | Per-iteration timings, median and p95 |
| Smoothness | Long Markdown/math/chat, composer IME, drawer and streaming | Real-device Perfetto and frame timing distributions |
| Accessibility | TalkBack focus order, headings/labels, keyboard/Switch Access, both themes, real system 200% text, tablet/landscape/split | Device matrix and observed failures |
| Resources | Idle and sustained chat/voice, background and termination | Memory PSS, CPU, power and network measurements; no private message traces |
| Crash/ANR | Signed internal test cohort, actual sessions and OS/device breakdown | Crash-free sessions denominator, period, Android Vitals and ANRs |
| Security | Real OAuth consent, replay, callback tamper, account switching, revocation, TLS, server authorization, secret handling and user isolation | Redacted test outcomes on the exact deployed backend |
| Native | 16 KiB ARM64 physical device, install and exercise WebRTC/RaTeX; bundletool-generated APKs and alignment config | ELF/ZIP evidence plus real runtime outcome |
| Distribution | Stable upload/app signing, signed AAB, internal track install/upgrade | Certificate verification and Play Console acceptance |

Do not publish raw traces, logs, private accounts, messages or credentials.
No percentage-complete claim without evidence. See RELEASE_GATES.md for full
functional acceptance. Backend-dependent checks remain blocked until the
harness integration is deployed and authorized.
