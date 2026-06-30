# Implementation TODO

## Completed In This Production Pass

- DeepSeek adapter with OpenAI-compatible `/chat/completions` request shape.
- DOCX prompt import for role, sales flow, constraints, handoff rules, and knowledge-base Q&A.
- SQLite persistence for accounts, contacts, conversations, messages, plans, plan targets, task runs, task events, audit logs, AI profiles, moment posts, moment interactions, and evidence files.
- Fifteen-day touch interval guard for each contact and plan.
- RPA sidecar window probe for personal WeChat `Weixin` / `微信`.
- RPA evidence capture before probe, before input, after send, and failure.
- Backend APIs for settings, prompt import, AI reply, window probe, contact sync, message send, touch plans, task events, evidence, and audit.
- Desktop operating console for the first small-batch loop.

## First Real Closed Loop

1. Start backend, sidecar, and desktop preview with `Start-Agent.ps1`.
2. Open `http://127.0.0.1:5173`.
3. Click `导入提示词`.
4. Click `同步联系人`.
5. Confirm WeChat is visible and unlocked.
6. Click `运行小批量闭环`.
7. Check task events, audit logs, and evidence paths.

## Next Iterations

- Improve contact sync by teaching the driver stable selectors for WeChat 4.1.9.35 after observing screenshots.
- Add an operator review queue for AI replies before enabling wider automatic sending.
- Implement visible conversation reading and inbound auto-reply.
- Implement real Moments feed navigation, scan, like, and comment selectors.
- Package Electron as a Windows installer after the small-batch loop is stable.
