First increment implemented in 6adda21d4 and a52531af4.

- Added repeatable shared-native transport benchmark; 30-sample long-history p95: direct26.44ms, relay32.92ms. Authenticated local T3 snapshot p957.00ms. Single test-fork discovery1.77s. These are Mac-side measurements; actual phone network/render and sustained resource baselines remain pending.
- Benchmark integration:18 focused tests passed. Additional relay recovery test:4/4 relay tests passed, scoped server typecheck and changed-file lint passed. Native peer termination during pending approval becomes unknown; explicit reconnect retains identity with no automatic replay/approval answer.
- Native mobile prebuild/dependencies succeeded. Actual-device build blocked by invalid saved Xcode Apple account/no provisioning profile. Simulator build blocked by Xcode26.1.1 compiling Expo57 (requires26.4+), with reproducible native compilation failures. Existing installed phone app and pairing remain intact. Need compatible Xcode and restored account before device validation; no blank-space fix claimed.

Plan remains active. Full recovery/concurrency, release operations and72h workload soak are not complete.
