# DragonZpyder Android engineering contract

This applies to every Android change, including hotfixes. Preserve the single DragonZpyder API and identity authority; do not create a mobile agent harness or duplicate backend authorization.

## Release targets (not measured claims)
- >=99.9% crash-free sessions over a defined measurement window, with sample size and device/OS cohort reported.
- Cold startup <1.5 s to usable UI on a named reference device; measure release builds with Macrobenchmark, report median and p95, distinguish network-dependent readiness.
- Smooth frame delivery at supported refresh rates; report frame overruns/jank with Macrobenchmark on representative devices.
- All actionable controls have >=48dp targets, meaningful TalkBack labels, focus order and keyboard access; never communicate state solely via color.
- Usable at 200% text scaling; test compact/expanded windows, phones, tablets, foldables, portrait/landscape, split screen and IME.
- WCAG AA contrast: 4.5:1 normal text, 3:1 large text and meaningful nontext controls.
- Network failures, process death, rotation, cancellation and account switching are tested; no automatic replay of uncertain side-effecting requests.
- Measure battery, memory, startup and network usage; stop microphone/camera/stream resources when their authorized lifetime ends.
- Verify signing, 16KB native library compatibility, real-device coverage, dependency/security review and Play internal release.

## Architecture
- Kotlin and native Compose for new product UI; Android platform pickers, permissions and secure credential UI are intentional exceptions.
- Shared design tokens and components. No arbitrary inline palette, Unicode glyph buttons, competing design systems or hardcoded dimensions that break large fonts.
- Unidirectional immutable screen state, lifecycle-aware ViewModels and StateFlow; repositories own network/data operations. No Activity or View references in long-lived state.
- Maintain compatibility with the shared API; authenticate, authorize and verify server receipts. Never put secrets in UI state, logs, saved instance state or model prompts.
- Introduce dependencies for demonstrated needs; do not install Room/Hilt/WorkManager merely to satisfy a checklist.
- All implementation changes must include suitable tests and verification evidence. Do not call a feature complete merely because its code exists.
- Keep refactor changes reviewable, preserve supported behavior, and do not merge a red or unqualified release.

See RELEASE_GATES.md for the exact acceptance matrix. Performance and accessibility targets cannot be marked passed without measurements.
