# Acceptance Log

## Current Gate

First production gate: small-batch WeChat loop.

Required evidence:

- Backend health is `ok`.
- RPA sidecar health is `ok`.
- WeChat window probe detects `Weixin` with title `微信`.
- Prompt import returns a non-zero knowledge count.
- Contact sync saves at least one visible contact.
- Small-batch run creates task events and audit logs.
- Every real sent message starts with `这是测试说明：`.
- Evidence files are linked from task events or audit logs.
- Restart keeps contacts, task runs, events, and audit records.

## Latest Automated Verification

Commands to run after each implementation batch:

```powershell
cd C:\Users\28293\Desktop\Agent\backend
python -m pytest

cd C:\Users\28293\Desktop\Agent\rpa-sidecar
python -m pytest

cd C:\Users\28293\Desktop\Agent\desktop-client
npm run build
```

Latest result:

- Backend tests: 18 passed.
- RPA tests: 9 passed.
- Desktop static UI check: passed.
- Desktop build: passed.
- Backend health: `ok`.
- RPA sidecar health: `ok`, mode `real`.
- WeChat window probe: currently reports `wechat_process_found_but_main_window_hidden` when the process is running but the main chat window is not available.
- Prompt import: 6 AI expert knowledge-base items, handoff rules loaded.
- DeepSeek reply endpoint: returned provider `deepseek`.
- Contact sync: saved 5 visible contacts and stored a `contacts_sync` evidence file.
- Live send: not triggered by the agent; the operating console button is ready for the user-run closed loop.

## 2026-06-29 Small-Batch Safety Fix

- Root cause: the previous RPA path treated "pywinauto did not throw" as success and did not verify current surface, target conversation, input box, or visible sent message.
- Fix: message send now returns `verification_status` and only `verified` can become a backend success.
- RPA blocks unsafe states such as wrong search surface, ambiguous target, missing target element, conversation mismatch, missing input box, and unverified sent message.
- Contact pool now has `eligible_for_touch`, `eligibility_reason`, and `confirmed_for_touch`; system contacts such as `文件传输助手` are excluded and old database rows are reclassified on startup.
- Touch plans only use confirmed eligible contacts; no confirmed contacts returns `请先确认客户` and does not send.
- AI outbound text is cleaned before sending so the test prefix appears once and duplicate punctuation is removed.
- Customer console was simplified into real sections: `首页`、`话术`、`客户`、`发送`、`结果`、`设置`.

## 2026-06-29 Prompt Import Fix

- Root cause: browser requests from `http://127.0.0.1:5173` hit `OPTIONS /prompts/import-docx`, and the backend returned `405 Method Not Allowed` because CORS middleware was missing.
- Fix: enabled local CORS for `127.0.0.1:5173` and `localhost:5173`.
- Added endpoint: `POST /prompts/import-docx/file` for direct `.docx` upload from the console.
- Added UI button: `选择文件导入`.
- Added frontend request timeout and error notice so the UI no longer stays on `正在导入`.
- Live verification: CORS preflight returned `200 OK`; uploading `搭建提示词_玺联惠创客合伙人版_仅改蓝字.docx` returned 6 knowledge-base items.
- Startup fix: `Start-Agent.ps1` now checks only `Listen` sockets so `TIME_WAIT` no longer blocks service startup.

## Manual Closed-Loop Result

Pending user-triggered real send. Fill after clicking `运行小批量闭环`:

- Run time:
- WeChat probe:
- Contacts synced:
- Targets attempted:
- Sent:
- Failed:
- Evidence folder:
- Notes:
