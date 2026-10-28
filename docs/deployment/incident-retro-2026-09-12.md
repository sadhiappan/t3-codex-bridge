# Retrospective: shared Codex daemon outage, September 12, 2026

## Accountability and impact

I caused this outage while applying a file-descriptor limit change. The original resource problem was real; my deployment method introduced two new failures. The user had to switch to Claude Code to stop the damage and restore the setup. The shared design increased the blast radius, but it did not cause my operational mistakes.

The supplied incident report records 38 daemon restarts between approximately 08:03 and 08:11 CDT, disconnecting attached terminals/phone clients and killing MCP child processes. Replacement daemons also lacked the PATH required for MCP startup. I have not independently reconstructed all 38 restarts from surviving logs. No evidence reviewed here establishes permanent conversation loss; interrupted work and service disruption are established by the incident report.

## Timeline and evidence

- Before 08:00: descriptor exhaustion was recurring. Both normal launch scripts already raised their soft file limit to 10240, but the old daemon had not been replaced.
- Around 08:00–08:03: I changed opt-in/unshare behavior while also preparing a daemon restart. Combining application changes and an infrastructure change made validation harder. The daily server used a development watcher, so source edits could reload it.
- 08:03:33: I submitted `local.codex-limit-upgrade-20260912` using `launchctl submit`, calling it an independent one-shot job. The submitted Python script raised its own soft limit and invoked `codex app-server daemon restart`.
- First attempt: `launch.log` records the restart subprocess timing out after 45 seconds. The job was supervised and could run again. The local launchctl manual explicitly says submit keeps a program alive in the event of failure; I had only consulted command usage, not that lifecycle behavior.
- Approximately 08:03–08:11: the incident report records repeated restarts. The final retained result.log contains a later daemon PID 44505, 270 initialized probe connections, 305 descriptors and PASS. This proves that particular capacity check passed, not that the job had stopped or that MCPs worked.
- 08:11: Claude removed the submitted job, according to the supplied report.
- 08:18: Claude stopped the daemon and restarted the established T3 LaunchAgent, restoring its intended environment. PID 51992 started at 08:18:33.
- Subsequent read-only checks: PID 51992 remained unchanged; its PATH included Homebrew and ~/.local/bin; the offending job was absent. All enabled MCP servers across its three loaded sessions reported connected and no toolsError. This conversation's own ID was absent from the daemon, so its individual startup was not verified.

## Root causes

### 1. Wrong execution lifecycle for a destructive operation

I needed a restart that could survive loss of my current connection. I selected launchctl submit without verifying whether the job would execute only once. It did not provide the one-shot lifecycle I claimed. Re-executing this script repeated a global restart rather than merely retrying a harmless health check.

The script had no durable completion guard. More importantly, a completion guard would not excuse using the wrong supervisor mechanism. The correct solution was to use the established service owner and its sanctioned restart procedure.

### 2. Wrong environment for the replacement daemon

`restart.py` constructed its child environment from `os.environ` and set only CODEX_HOME. Running under the submitted job meant inheriting launchd's bare PATH rather than start-everyday-t3's configured PATH. Raising RLIMIT did not restore npx, uv or the keychain helper lookup needed by MCP subprocesses.

I had already read the normal start script, so the dependency was available evidence. I failed to preserve it. The daemon could accept connections while its tools could not launch.

## Why verification missed the outage

- The probe opened 270 native connections and counted descriptors. That measured capacity only. It did not exercise MCP initialization, command lookup or a real loaded session.
- I did not verify that the submitted job exited and stayed stopped. One successful script execution was not proof of stable service lifecycle.
- `result.log` was opened with mode `w` on every invocation. Each run erased the preceding result. Meanwhile launch.log retained a timeout traceback. A later PASS therefore obscured earlier failure when the logs were considered separately.
- The probe did not query the daemon's exact RLIMIT. Its PASS wording was limited in the JSON, but I still used a broader operational success framing in the handoff.
- Unit tests for relay and unshare code did not cover launchd lifecycle or the replacement daemon environment. Their passing results could not validate the restart procedure.
- I did not establish a bounded rollback/recovery procedure before initiating a change that could disconnect my own control session.

## Corrective actions already completed

- Claude removed the looping launchd job and restored the daemon through the established T3 LaunchAgent.
- Read-only follow-up confirmed the corrected PATH, unchanged replacement PID and successful enabled MCP startup in three loaded sessions.
- Commit 0de69c056 records daemon guardrails in AGENTS.md: no launchctl submit for one-shots; same-turn explicit restart authorization; only the daemon-stop then T3-LaunchAgent-kickstart path; environment verification; protected configuration rules.
- Commit 3d50cb27c separately records the unshare change. Separating the commits makes the operational guardrails independently reviewable.
- No further daemon restart was performed during follow-up verification or this retrospective.

## Required operating procedure from now on

1. Keep application changes and daemon maintenance separate. Prepare the change, validation and recovery steps before acting.
2. Obtain explicit same-turn authorization naming a restart. Explain that it affects every attached client.
3. Use only the existing sanctioned service path: daemon stop, then kickstart gui/501/local.codex-shared-t3. Never recreate the submitted job or run the incident restart script.
4. Verify replacement PID/start time and its actual PATH, printing only the needed fields rather than potentially secret environment values.
5. Check a real resumed session's enabled MCP servers for connected status AND absence of startup/tools errors. Distinguish intentionally disabled servers. Check a harmless representative tool operation when needed; socket capacity is a separate measurement.
6. Confirm the daemon remains stable and no restart job remains active. A limited observation period cannot guarantee indefinite stability; report its scope.
7. Preserve timestamped, append-only maintenance evidence. Report partial failures explicitly and do not let a successful capacity probe overwrite the incident verdict.

## Remaining limits

This retrospective did not change the running setup. The old restart.py and its logs are retained as incident evidence, not approved operational tools. The earlier handoff's “one-shot” description and implication of successful deployment are superseded by this report. Full idle-expiry testing, phone validation of unshare/re-enable and a sustained resource soak remain separate unfinished work. The higher limit mitigates resource pressure; it does not prove cleanup correctness.

Evidence: supplied Claude incident report; retained restart.py, result.log, launch.log and verify.mjs under limit-upgrade-2026-09-12; local launchctl manual; installed start-everyday-t3; committed AGENTS.md; subsequent metadata-only MCP inventory.
