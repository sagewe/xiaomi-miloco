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

- Implemented and merged:
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
- Verified in GitHub Actions:
  - `agent-runtime-ci.yml` runs successfully on `main`
  - `build-agent-runtime-wheels.yml` builds `cp312` wheels for Linux `x86_64` and `aarch64`
  - workflow artifacts include both wheel files:
    - `miloco_agent_runtime-0.1.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`
    - `miloco_agent_runtime-0.1.0-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl`
- Remaining rollout step:
  - Validate asset upload against a draft or published GitHub Release tag

## Manual release-upload validation

Use the `Build Agent Runtime Wheels` workflow in `workflow_dispatch` mode with:

- `upload_to_release = true`
- `release_tag = <existing draft release tag>`

This keeps the normal `release.published` path unchanged while allowing wheel asset upload to be tested against a prepared draft release before a real publish.

## Issue template checklist

Every migration issue should include:

- Problem
- Scope
- Out of scope
- Dependencies
- Acceptance criteria
- Verification
- Rollback plan
