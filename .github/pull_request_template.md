## Summary

- Describe the migration slice in one paragraph.

## Issue

- Closes #

## Scope

- Included:
- Out of scope:

## Verification

- [ ] `cargo test --manifest-path native/miloco-agent-runtime/Cargo.toml`
- [ ] `uv run python -m py_compile miloco_server/agent/chat_agent.py miloco_server/agent/rust_runtime_adapter.py miloco_server/agent/runtime_bridge.py`
- [ ] Targeted Python/Rust integration tests

## Rollback

- Runtime backend can be forced to `python`
- Wheel installation is optional and isolated from `miloco_server`

## Checklist

- [ ] Single issue / single mergeable slice
- [ ] Acceptance criteria copied from the issue and satisfied
- [ ] Backward compatibility validated for WebSocket and chat history formats
- [ ] New config defaults documented
