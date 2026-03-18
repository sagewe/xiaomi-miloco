# Rust Agent Runtime Migration Backlog

GitHub tracking epic: [#2](https://github.com/sagewe/xiaomi-miloco/issues/2)

## Milestones

| Milestone | Issues |
| --- | --- |
| M0 | [#2](https://github.com/sagewe/xiaomi-miloco/issues/2) epic, [#3](https://github.com/sagewe/xiaomi-miloco/issues/3) templates, [#4](https://github.com/sagewe/xiaomi-miloco/issues/4) native package scaffold |
| M1 | [#5](https://github.com/sagewe/xiaomi-miloco/issues/5) wheel build matrix, [#6](https://github.com/sagewe/xiaomi-miloco/issues/6) release consumption path |
| M2 | [#7](https://github.com/sagewe/xiaomi-miloco/issues/7) runtime toggle and adapter, [#8](https://github.com/sagewe/xiaomi-miloco/issues/8) JSON bridge contract |
| M3 | [#9](https://github.com/sagewe/xiaomi-miloco/issues/9) streaming client, [#10](https://github.com/sagewe/xiaomi-miloco/issues/10) delta merge parity, [#11](https://github.com/sagewe/xiaomi-miloco/issues/11) ReAct loop + tool callback |
| M4 | [#12](https://github.com/sagewe/xiaomi-miloco/issues/12) NlpRequestAgent integration, [#13](https://github.com/sagewe/xiaomi-miloco/issues/13) dynamic execute integration |
| M5 | [#14](https://github.com/sagewe/xiaomi-miloco/issues/14) parity/perf/failure tests, [#15](https://github.com/sagewe/xiaomi-miloco/issues/15) Docker default switch |

## Current implementation status

- Implemented locally:
  - [#3](https://github.com/sagewe/xiaomi-miloco/issues/3) migration issue template and PR contract
  - [#4](https://github.com/sagewe/xiaomi-miloco/issues/4) native crate scaffold under `native/miloco-agent-runtime/`
  - [#5](https://github.com/sagewe/xiaomi-miloco/issues/5) wheel build workflow for Linux `x86_64` and `aarch64`
  - [#6](https://github.com/sagewe/xiaomi-miloco/issues/6) release consumption path via `install_miloco_agent_runtime.py`
  - [#7](https://github.com/sagewe/xiaomi-miloco/issues/7) runtime backend toggle (`python` / `rust` / `auto`)
  - [#8](https://github.com/sagewe/xiaomi-miloco/issues/8) Python/Rust JSON bridge contract
  - [#9](https://github.com/sagewe/xiaomi-miloco/issues/9) OpenAI-compatible streaming client in Rust
  - [#10](https://github.com/sagewe/xiaomi-miloco/issues/10) delta merge and assistant step finalization
  - [#11](https://github.com/sagewe/xiaomi-miloco/issues/11) ReAct loop and Python tool callback bridge
  - [#12](https://github.com/sagewe/xiaomi-miloco/issues/12) `NlpRequestAgent` integration behind the runtime flag
  - [#13](https://github.com/sagewe/xiaomi-miloco/issues/13) dynamic execute integration
  - [#14](https://github.com/sagewe/xiaomi-miloco/issues/14) parity/failure coverage and replay benchmark
  - [#15](https://github.com/sagewe/xiaomi-miloco/issues/15) Docker default switch to `auto`
- Still pending before merge:
  - Push branch and open PRs that map the staged changes back to the issue slices
  - Run GitHub Actions for wheel build and release upload against a real tag/release
  - Close issues only after the corresponding PRs merge

## Issue template checklist

Every migration issue should include:

- Problem
- Scope
- Out of scope
- Dependencies
- Acceptance criteria
- Verification
- Rollback plan
