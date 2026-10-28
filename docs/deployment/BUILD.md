# Shared Codex prototype build

Repository: /Users/shivadhiappan/Projects/t3code
Private remote: https://github.com/sadhiappan/codex-shared-t3
Branch: shared-daemon. Upstream baseline: v0.0.40.
Published milestone: 675e8708e safe shared transport/runtime.
Node 24.13.1 isolated here; pnpm 11.10.0. Codex 0.153.4 isolated daemon PID 81366.
Native socket requires WebSocket with perMessageDeflate disabled. Raw two-client prompt fanout, late approval replay/answer passed. Native TUI resume and receiving modified T3 runtime prompt passed (PTY session 70011 still open).
46 focused tests passed for first milestone, server typecheck and scoped lint passed.
Stock T3 server started/pairing offered in chat. Actual iPhone pairing/validation pending.
Stage 2 in progress: discovery restricted to test project, native message identities and external message ingestion, approval correlation fixes, checkpoint opt-out. Tests/typecheck and live integrated server validation pending.
Micro untouched. No phone prototype claim until actual device validation.
Server PID in server.pid; logs in server.log. Both isolated from existing installs.

## Published synchronization milestone — 2026-09-09

Commit 1b94d0844 pushed to origin/shared-daemon; worktree clean.
201 focused server tests + 2 RPC client tests passed. Scoped server typecheck, changed-file lint/format, git diff check passed.
Live proof: native CLI to integrated T3 server; authenticated T3 RPC to same native CLI; real Chrome UI to same native CLI; pending command approval replayed across T3 restart, resolved from another client; stable approval identity clears pending UI; browser prompt remains single after restart.
Browser UI caught persistent echo duplication after restart (command read model omits messages) and equal-timestamp history ordering. Fixed via durable message lookup before observation, restart regression test, and native item ordering. Early disposable test history retains artifacts from before this fix; new validation prompt BROWSER_SHARED_VALIDATED_4 remains single.
Native TUI tool session 70011 remains open. Isolated dev runner PID 8520 and daemon PID 81366 remain running for phone validation. Browser deliverable tab 1461867332 left open.
Actual Ghostty UI automation was blocked by computer-use safety policy. iPhone Mirroring unavailable (no window). Physical iPhone acceptance requested in chat; no phone confirmation received yet. Fresh pairing link generated separately in phone-pair.txt (not in Git).
Do not call the complete prototype accepted yet. Next gate is released T3 iPhone pairing, same-thread prompt/reply and approval. Then complete remaining initiative work for recovery/concurrency/read-only diffs, terminal identity + Micro integration, operational service/soak/rollback. Micro baseline and normal Codex home untouched.
Native settings remain authoritative; T3 model/permission/effort/interaction controls are not implemented for shared attachments. Historical tool/diff/attachment hydration and unsupported approvals remain documented limits. No service install or long soak claimed.

## Actual iPhone validation — 2026-09-10

User authorized iPhone Mirroring control. Replaced rejected pairing credential with fresh CLI pairing code and verified host. Native T3 iPhone app paired successfully, opened the existing shared conversation, sent PHONE_SHARED_OK test and displayed PHONE_SHARED_OK response. T3 database records the exchange once on the same shared native thread. Native daemon thread/read independently confirms completed matching turn. Phone messaging acceptance passed; phone approval/interruption/reconnect and physical Ghostty/Micro integration remain pending.

## Approval, reconnect, terminal identity, Micro extension — 2026-09-10

Actual iPhone T3 app: Allow once approved a harmless printf command; PHONE_APPROVAL_OK appeared. T3 server restarted through its own watch runner; phone sent PHONE_RECONNECTED_OK and received the reply without re-pairing. Phone Stop interrupted the native turn (native turn/completed status interrupted). iPhone Mirroring later disconnected because the user was using the phone.

T3 published commit ae96ecb8f adds transparent per-terminal Unix WebSocket relay, identity observer, interactive launcher, and private Micro IPC client. Native frames forwarded unchanged; no relay-generated approval answers. Real native CLI through relay: resume original ID, /new changed the observed ID, /resume restored original ID. A turn from another native client produced matching done/turn-ID in relay-state.json. Real committed launcher with pinned Codex 0.153.4 opened a new test-project conversation, received LAUNCHER_VALIDATED, and T3 imported the exchange once. Additional relay probe used globally updated CLI 0.154.0; daemon remains isolated 0.153.4. Both new test CLI processes exited cleanly and their temporary sockets were removed. Original PTY 70011 retained.

8 new relay/IPC tests passed; scoped server typecheck and changed-file lint/format passed. Micro extension: 67 tests passed and AppleScript compiled against installed Ghostty dictionary. Worktree /Users/shivadhiappan/Projects/codex-micro-shared, branch shared-daemon. Private backup https://github.com/sadhiappan/codex-micro-bridge, commit 268bcdb. Live bridge main fast-forwarded to same commit and service restarted, preserving 11 ordinary session associations. Normal hooks and device profile unchanged; shared registrations remain empty. Legacy recovery excludes descendants already owned by a verified shared wrapper.

Baseline rollback tag baseline-before-shared-20260910 points at 6cb0631 and is published. Restore those sources and restart local.codex-micro-bridge to roll back; preserve current state/journal and original native binding.

Outstanding physical acceptance: Micro reported disconnected before and after the passive bridge update. Ghostty computer-use access remains blocked by tool safety policy, so no real title-marker/physical-key/LED assertion. Shared launcher is NOT installed as default; ordinary codex routing remains unchanged. Real UI marker resolution, physical LEDs/keys, sleep/wake/long soak, and production work/personal-session migration remain pending. Do not route ordinary sessions through the prototype until those gates pass.

## Everyday native-home rollout — 2026-09-10

User explicitly authorized automatic everyday Ghostty routing. Commit a67b8dc58 implements interactive argument routing, cwd preservation for new sessions, durable opt-in native ID registration, ephemeral-helper exclusion, and a usable final resume hint. This supersedes the earlier requirement to gate normal launcher installation on physical Micro acceptance: Micro is optional and separate.

Native bootstrap started existing ~/.codex daemon with installed Codex 0.154.0 (backend pid). Original settings/history retained in place; test daemon/home retained separately. T3 now connects to the main native socket, retaining its prior isolated T3 home, pairing credentials, environment ID and tailnet URL. Registration directory here contains only launcher-observed IDs. No bulk history scan/import.

Installed everyday-codex shell script and marked codex function at end of ~/.zshrc; old shells require a new tab or reload. Original ~/.local/bin/codex symlink remains native for automation. Separate explicit CODEX_HOME invocations pass through. Backup zshrc-before-everyday. Existing running standalone CLIs need one-time exit/resume from a new shell; none were killed.

Installed local.codex-shared-t3 LaunchAgent using start-everyday-t3 here; starts native daemon and T3 development runner at login, restarts on exit. Repository node_modules/.bin and Node24 on service PATH. Stopped captured old runner 8520 and its owned process group after discovering orphan children. Service initial PATH failure fixed. Final full launchctl kickstart retained server13773/web5733 and tailnet root returned HTTP200. Latest service PID16786, read launchctl for current PID. Logs everyday-server.log; old server.pid is historical.

Validation: 14 focused tests, scoped server typecheck, changed-file lint, shell syntax and new-login-shell routing passed. Native main-home test thread 01a08ca4-da26-7440-ae64-fa51e797f2f9: EVERYDAY_SHARED_OK from Mac CLI imported once; authenticated T3 prompt EVERYDAY_T3_REPLY_OK returned on same live native TUI; after CLI exit and complete T3 service restart, EVERYDAY_RESTART_OK completed on same native thread and appears once in T3. Main shared environment prefix7725a7bc312befe2. Early probe caught ephemeral native helper wrongly replacing main observer identity; regression fixed, final resumed CLI exit hint verified correct. Helper registration from pre-fix probe has empty preview and is explicitly excluded.

No new physical iPhone test this rollout; prior iPhone acceptance remains, same pairing database/URL preserved. Actual ordinary work/personal sessions not forcibly migrated. No long sleep/wake/soak assertion. Still a watched development T3 build, not a packaged release. Micro marker probe on tool PTY failed exact-surface match; later CLI validation used TERM_PROGRAM=xterm so no hardware/UI claim.

## Everyday iPhone acceptance — 2026-09-10 13:55 CDT

Used iPhone Mirroring at user request. Existing paired T3 app opened the real-home EVERYDAY_SHARED_OK conversation without re-pairing. Sent "Say phonecheck" and visibly verified "phonecheck" reply. Independent native thread/read confirms completed turn 01a08cac-b987-77a2-a064-8f16129e77b9 on the same Mac native thread 01a08ca4-da26-7440-ae64-fa51e797f2f9. Everyday phone messaging acceptance passed. No physical Micro test or long soak claim.

## Resume picker repair — 2026-09-10 14:02 CDT

User screenshot exposed native in-session picker opening an auxiliary WebSocket, rejected by the relay single-client limit. Commit 0a47aaeba permits independent concurrent connections and reports identity/status only from the connection owning the actual selected conversation. Read-only picker connections cannot erase main state. Regression reproduced before patch; 5 focused tests, scoped server typecheck and lint passed. Real Codex0.154 CLI startup resume picker populated, selected test conversation, in-session /resume picker populated and cancelled cleanly. Existing running launchers need exit/relaunch to load patched module. Remote resume with --profile yolo remains unsupported by native CLI; use plain codex resume.

## Terminal artifact repair — 2026-09-10 14:05 CDT

User confirmed resumed session appears in T3; screenshot showed Micro osascript errors overwriting the TUI. b8683a2b1/d1d8bfc2e route runtime diagnostics to ~/.local/state/codex-shared-t3/terminal.log, with startup/exit summaries outside native rendering. Initial Micro binding failure disables Micro reporting for that launcher; no title-change retries while native TUI runs. Registration-loss errors disable reporting rather than rebind through active title. Native/T3 registration continues independently. Real native resume with deliberately unavailable mock Micro socket produced one logged error across heartbeat intervals and exited cleanly. Scoped lint and typecheck passed. Existing launcher processes need exit/resume to load fix. Underlying Ghostty marker identity failure still unresolved; shared Micro LEDs are not claimed working.

## Mascot rendering mitigation — 2026-09-10 14:33 CDT

Repeated screenshot showed base64 image data leaking into native screen. The krea launcher PID32187 still dates14:02 (before diagnostic fix); user process not killed. Removed tui.pet="codex" from main ~/.codex/config.toml; preserved all other settings, backup config-before-render-fix.toml outside Git. Controlled actual native0.154 shared resume in a100x24 PTY with explicit mascot enabled produced90 Kitty image sequences and327285 bytes over4 seconds. Same-size no-mascot run results captured separately in chat. Existing running TUI must detach/restart to load setting and current launcher; no live Ghostty UI access used. This is a verified removal of problematic graphics emission, not a claim that the underlying terminal graphics implementation was repaired.

## Rendering regression audit — 2026-09-10 15:04 CDT

Commit3cba7574e fixes additional shutdown race: launcher now waits for the pending Micro publication before closing diagnostics, and relay.close waits for socket close callbacks. Background writes were audited: startup title changes/warning occur before child UI; runtime errors go to private log; resume/diagnostic summaries occur after native exit. No active-TUI marker retries.

16 focused tests passed, scoped server typecheck and changed-file lint passed. Added40-frame alternating binary/Unicode stress echo test (large multibyte payloads, preserved byte-for-byte) and verified scoped close keeps upstream server alive. Actual native no-mascot shared resume underwent3 resizes (40x12,160x48,100x24), exited0 with zero Kitty/image payload frames and expected history loaded. Controlled fake Micro IPC on a real native PTY exercised pending update timeout; error retained in log, no Micro error/exception in terminal output, no image frames, exit0. First version expected a specific injected error but observed the client's1.5s timeout instead; assertion corrected to cover the actual forced timeout and explicitly reject timeout text on screen. No claim of reproducing every possible renderer or network issue.

Current krea launcher PID78366 started14:44, after mascot/logging fix; newer shutdown hardening loads on next launch. Other launcher PID57411 remains14:23. Main global tui.pet remains unset. No real Ghostty UI automation or long soak performed.

## Production hardening first increment — 2026-09-11

Plan tracked at https://github.com/sadhiappan/codex-shared-t3/issues/1; local PRODUCTION-PLAN.md. Benchmark commit 6adda21d4 adds repeatable direct/native-terminal-relay history reads, explicit thread and bounded sample counts, no model turns/transcript output. PERFORMANCE-BASELINE.md records full methodology and raw artifact paths. Long history 1.46MB: direct p95 26.44ms, relay p95 32.92ms, 30 samples each. Authenticated local T3 snapshot p95 7.00ms over30 samples. Dedicated test fork discovery after first prompt1.77s (one sample, not p95). Brief resource measurements are not a leak/soak verdict. Actual phone latency/render measurement remains pending.

18 focused tests passed for benchmark integration; additional recovery regression commit a52531af4 tested native peer termination during pending approval, visible unknown state, explicit reconnect with retained thread ID, no request replay or approval answer. Relay suite4/4 passed; scoped server typecheck and changed-file lint passed. This is simulated WebSocket failure, not full daemon restart/sleep recovery proof.

Mobile native prebuild and CocoaPods installation succeeded, using separate com.sadhiappan.codexshared.dev bundle; generated ios project ignored, existing phone app untouched. Device build failed: Xcode account credentials invalid/missing username, no provisioning profile. Simulator build failed in expo-modules-jsi with weak-let/C++ interop errors. Installed Xcode26.1.1; official Expo SDK57 requirements specify26.4+ (https://docs.expo.dev/versions/latest/). User notified to restore Xcode account; newer compatible Xcode required. Generated personal-team entitlements also retain push/associated-domain keys despite existing plugin, so inspect/fix config generation before device signing when toolchain is available. No mobile patch or blank-space fix claimed.

Remaining initiatives: mobile UI defects/control accuracy, complete recovery and concurrency tests, immutable release/backup/rollback operations, actual72h monitored workload soak. None marked production-complete.

## MCP retention fix — September12 07:41 CDT
Commit242b562a0 prevents shared discovery from reattaching unchanged idle stopped bindings. New native activity/updatedAt can reattach; explicit T3 prompt path unchanged.59 focused tests, server typecheck and targeted lint passed. Dev watcher deployed automatically, native daemonPID990 and terminal sessions preserved. Live T3 providers8→2 with idle bindings remaining stopped across sweeps. Native30-minute cleanup/other subscribers mean resource release is delayed; daemon limit change still not applied to existingPID990. Full evidence: lifecycle-audit-2026-09-12/report.md. User stopped number-dictation work; VoiceInk settings unchanged and temporary Ollama server stopped.
