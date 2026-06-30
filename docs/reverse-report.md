# Reverse Report: dt-ai-helper v1.8.28

## Executive Summary

The target installation at `C:\Users\28293\AppData\Local\Programs\dt-ai-helper` is an Electron desktop product named `谷小智AI员工`. It combines a React/Vite renderer, bytecode-loaded Electron main/preload scripts, a local PyInstaller Python service, and bundled browser/RPA automation dependencies.

The rebuild should be a clean product implementation: use the reverse analysis to derive behavior, UI modules, API concepts, and task flow, but do not reuse upstream tokens, binary components, production API hosts, or brand assets.

## Observed Structure

- Electron app package: `resources/app.asar`
- Main entry: `./out/main/index.js`
- Bytecode payloads: `out/main/index.jsc`, `out/preload/index.jsc`
- Renderer windows: `main`, `agent`, `agentTask`, `workflow`, `hoverBall`, `exposureRecord`, `midscene`
- Local sidecar: `resources/app.asar.unpacked/resources/main.exe`
- PyInstaller marker detected near the end of `main.exe`
- RPA runtime dependencies: Flask, Playwright, Patchright, Selenium, OpenCV, PIL, sqlcipher, pywin32, wx-specific assets, OCR model files

## Key Feature Evidence

| Area | Evidence | Rebuild Interpretation |
|---|---|---|
| WeChat account status | `/wechat/status`, local Python calls, `wxid` helpers | Sidecar detects active WeChat account and reports account identity |
| Contact sync | `/we-chat/contact/pages`, `/wechat/contacts/sync`, `/rpa_sync_chat_history` | Backend stores contacts; sidecar refreshes from desktop client |
| AI chat | `/api/agent/chat`, task event streams, session history APIs | Backend manages AI conversations and tasks |
| Mass send | `/message_send_plan/*` constants | Backend plan engine with guarded send queue |
| Moments publish | `/auto/we_chat/post/*` constants | Publish plan with content, attachments, schedule |
| Moments marketing | `/auto/we-chat-moment-campaigns/*` constants | Like/comment campaign with targets, quotas, and prompt config |
| Add friend | `/auto/add_friend/*` constants | Optional plan type for test account workflows |
| Local automation | `@computer-use/nut-js`, Playwright, Patchright, wx images | Sidecar performs desktop/UI actions behind safe endpoints |

## Important Upstream Constants

Observed hosts:

- `https://client.rpa.dockingtech.com/`
- `https://agent.dockingtech.com`
- `https://rpahelper.dockingtech.com`

These hosts are evidence only. The MVP uses a self-hosted backend and local sidecar.

## Rebuild Scope

MVP should implement:

- Windows-only operator console.
- Local sidecar health and WeChat status.
- Test account contact sync.
- AI-generated reply and copywriting.
- Mass-send plan creation/execution.
- Moments publish plan creation/execution.
- Moments marketing plan creation/execution with like/comment actions.
- Task events and audit logs.

## Exclusions

- No captcha bypass.
- No anti-detection or stealth escalation.
- No use of extracted credentials, tokens, or upstream production accounts.
- No non-whitelisted customer actions.
