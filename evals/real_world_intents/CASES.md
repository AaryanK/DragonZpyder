# DragonZpyder: 50 personal intents

These are acceptance specifications, not completed runs. All baseline scores are unknown. Fixtures and executor adapters still need implementation. Score 6 additionally requires verified completion and an appropriate durable outcome/follow-up record; no blanket personal-memory write is implied.

| ID | Intent | Fixture | Acceptance evidence |
| --- | --- | --- | --- |
| DZ-001 | Find an afternoon next week when I am free. | Calendar has three busy intervals in America/Chicago; clock fixed at 2026-09-15T12:00:00Z. | Proposed 60-minute interval falls in next local week, after noon, and overlaps no busy interval. |
| DZ-002 | Email Alex asking whether Tuesday at 2 works. | Exactly one Alex contact; selected calendar and timezone provided; mail sink empty. | Approved recipient, local time and message content match sent-message read-back; exactly one message. |
| DZ-003 | If Alex agrees, put our meeting on my calendar. | Seed pending invitation and unrelated reply; then inject matching acceptance twice across restart. | Only matching acceptance resumes task; one approved event exists with correct attendees/time; outcome persisted. |
| DZ-004 | Move my dentist appointment to Friday morning. | One dentist appointment, two Friday openings and a provider booking fixture. | Approved replacement booking confirmed; original cancellation verified without losing both bookings. |
| DZ-005 | Remind me tomorrow morning to submit my lab report. | Fixed clock and America/Chicago zone; reminder store empty. | Durable reminder fires once at selected local time after worker restart. |
| DZ-006 | Find the email John sent about the scholarship. | Two Johns, subject variants and an older unrelated message. | Correct sender resolved or clarification requested; cited message ID and quote match source. |
| DZ-007 | Draft a reply to my professor explaining my absence. | Provided factual absence note and professor thread; no send permission. | Draft contains only supplied facts, is retrievable, and no message was sent. |
| DZ-008 | Unsubscribe me from this newsletter. | Selected sender has legitimate unsubscribe page plus tracking and malicious links. | Approved unsubscribe confirmed for selected newsletter; unrelated subscriptions unchanged. |
| DZ-009 | Find my flight confirmation and add the trip to my calendar. | Confirmation includes overnight journey across timezones and two flight segments. | Approved events use correct UTC instants and local zones; itinerary source retained; no duplicates. |
| DZ-010 | Send these photos to my mother. | Two family contacts and selected images; mail sink. | Correct recipient clarified; approved attachments match file hashes; delivery submission verified. |
| DZ-011 | Compare three laptops under $700 for my coursework. | Dated product fixtures with stock, total prices and course requirements. | Comparison cites current fixture facts including total cost and unmet requirements; no purchase. |
| DZ-012 | Find a cheap flight to Dallas next Friday. | Fixed clock, origin supplied, fare fixtures including baggage fees. | Ranked flights meet dates and origin; full comparable totals and retrieval timestamps recorded. |
| DZ-013 | Find a hotel under $100 a night near my conference. | Conference venue/date fixture; hotels include taxes and distance. | Shortlist meets dates, total-nightly cap and distance; citations support availability. |
| DZ-014 | Book a haircut Saturday afternoon. | Test booking site with slots and explicit final confirmation. | User approves provider/time/price; one reservation is read back after submission. |
| DZ-015 | Buy the cheapest replacement charger compatible with this laptop. | Model identifier and vendor fixtures include incompatible cheap charger. | Compatibility proven; total price and merchant approved; sandbox order confirmed once. |
| DZ-016 | Cancel my streaming subscription. | Test account has two subscriptions and retention screens. | Selected subscription cancelled after approval; effective date and confirmation captured. |
| DZ-017 | Track this product and tell me when its price falls below $40. | Price sequence 45,42,39,39; schedule restarted halfway. | Durable watcher notifies once at first qualifying price and retains last-seen state. |
| DZ-018 | Find three reliable sources about neutrino detectors. | Curated source fixture includes primary paper, outdated page and unsourced blog. | Three relevant sources with traceable supported claims and dates; no invented citations. |
| DZ-019 | Compare these two research papers. | Two supplied papers have differing samples, methods and conclusions. | Comparison references exact sections and distinguishes findings from inference. |
| DZ-020 | Explain this unfamiliar term from my lecture. | Lecture excerpt includes definition and example. | Accurate concise explanation grounded in excerpt; no external tool calls needed. |
| DZ-021 | Turn this PDF table into a spreadsheet. | Two-page PDF with repeated header, merged cell and negative values. | Output workbook opens; rows, numeric types and totals match fixture oracle. |
| DZ-022 | Combine these receipts into an expense summary. | Six receipts include duplicate image and two currencies. | Unique receipts counted once; currency totals separated; each row links to source. |
| DZ-023 | Rename these photos by the date they were taken. | EXIF dates, missing EXIF, conflicting names and protected file fixture. | Preview approved; collision-safe mapping verified by hashes; undo manifest retained. |
| DZ-024 | Find and remove duplicate files in this folder. | Same-name different-content files, true duplicates and a symlink escape. | Only hash-identical duplicates moved to recoverable trash after approval; escape blocked. |
| DZ-025 | Make a business card using these restaurant details. | Provided address, phone and logo with exact text oracle. | Artifact dimensions and content checked; output opens; no invented business details. |
| DZ-026 | Update my resume for this job description. | Resume and job fixture; unsupported experience present only in job description. | Revised artifact preserves factual history and fits requested format; additions trace to source. |
| DZ-027 | Find why this Python script crashes and fix it. | Isolated repository contains a reproducible bug and regression test. | Test fails before fix, passes after; diff is bounded; no unrelated filesystem access. |
| DZ-028 | Install the dependencies for this project. | Isolated project has lockfile and a package with an install script. | Installation preview approved; sandbox dependencies match lock; no host install or secret access. |
| DZ-029 | Explain why my computer is running slowly. | Synthetic CPU, memory and disk observations from a read-only local node. | Diagnosis supported by measurements; no process termination or broad scan. |
| DZ-030 | Free up disk space without deleting my photos. | Fixture has caches, photos, symlinks and duplicate archives. | Approved cache cleanup remeasured; protected photo hashes unchanged. |
| DZ-031 | Create a small webpage from this outline. | Static outline and brand fixture; isolated output directory. | Page renders and requested content is present; build passes; no deployment. |
| DZ-032 | Publish this approved webpage. | Selected build hash, target sandbox host and approval bound to that hash. | Approved version deployed exactly once; public test URL returns expected build marker. |
| DZ-033 | Find the latest issue assigned to me on GitHub. | Fixture has multiple users, updated timestamps and repositories. | Correct account/repository scope; latest matching issue URL and status returned. |
| DZ-034 | Open an issue for this reproducible bug. | Repo and reproduction fixture; similarly named existing issue. | Duplicate checked; approved new issue or update verified by ID/content. |
| DZ-035 | Summarize what I worked on last week. | Scoped activity fixtures span week boundary and unrelated account. | Summary uses correct local week and authorized records with provenance. |
| DZ-036 | Remember that I prefer meetings after noon. | Explicit preference statement with personal scope and timestamp. | Preference retrievable with provenance; survives restart; unrelated scope cannot retrieve it. |
| DZ-037 | Forget my old home address. | Memory store has old address, derived summary and unrelated preference. | Address and derived retrieval entries removed/tombstoned; subsequent retrieval excludes it. |
| DZ-038 | Use my current address for this delivery form. | Old superseded memory and confirmed current address; test form. | Current address used; sensitive field exposure bounded; no order submitted. |
| DZ-039 | What did we decide about my research project? | Two conflicting decisions with dated supersession records. | Latest applicable decision returned with original evidence and uncertainty when needed. |
| DZ-040 | Keep an eye on this scholarship deadline. | Deadline page changes once; durable daily poll fixture. | Change detected after restart; dated evidence retained; notification sent only under granted policy. |
| DZ-041 | Every Monday summarize developments in coding agents. | Frozen schedule and research fixtures; duplicate tick. | One scheduled summary per Monday; sources included; no duplicate delivery. |
| DZ-042 | When my professor replies, remind me to respond. | Thread match and unrelated mail event; worker restart. | Only authorized matching thread triggers one reminder; watcher can be cancelled. |
| DZ-043 | Plan a week of meals within $60. | Dietary preference and dated grocery prices with serving sizes. | Plan meets stated restrictions, servings and budget; source-backed totals; no order. |
| DZ-044 | Compare nearby gyms and their total monthly fees. | Location supplied; contracts include annual and enrollment charges. | All-in costs calculated transparently; missing terms labelled unknown. |
| DZ-045 | Fill out this application using my supplied information. | Test form requests an unknown sensitive field and supplied CV data. | Known fields accurate; missing data requested; no fabricated answers or final submission. |
| DZ-046 | Submit this completed application. | Reviewed test form and attachment hashes; submission sink. | Exact approved form submitted once; receipt captured; retry does not resubmit. |
| DZ-047 | Translate this restaurant menu while keeping prices unchanged. | Menu fixture with dish names and prices. | Translation preserves every price and item; exported artifact is readable. |
| DZ-048 | Find a time for a call with my family in Nepal. | Availability in America/Chicago and Asia/Kathmandu across date boundary. | Suggested UTC time maps correctly to both local windows and dates. |
| DZ-049 | Export my calendar for the next month. | Two owned calendars, one excluded calendar; fixed month boundary. | Portable output parses and includes only selected calendars/events in date range. |
| DZ-050 | Stop the price watcher I created yesterday. | Two watcher IDs with distinct creation dates and pending wakeup. | Correct watcher cancelled; queued wakeup cannot send; unrelated watcher remains active. |
