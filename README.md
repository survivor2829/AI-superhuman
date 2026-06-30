# Agent MVP

Agent MVP is a clean rebuild of the observed `dt-ai-helper` workflow: a Windows desktop client, a self-hosted backend, and a local RPA sidecar for authorized WeChat desktop automation.

## What Is Included

- `docs/reverse-report.md`: reverse-engineering feature profile and evidence map.
- `docs/architecture.md`: product architecture, data flow, task flow, and RPA state machine.
- `api/openapi.yaml`: backend and local sidecar API contract.
- `backend/`: FastAPI backend for accounts, contacts, conversations, automation plans, task runs, and audit logs.
- `rpa-sidecar/`: local Python sidecar with guarded WeChat desktop automation endpoints.
- `desktop-client/`: Electron + React + TypeScript operator console.

## Safety Defaults

The implementation is designed for authorized Windows test accounts:

- whitelist required before any outbound contact action;
- quota and time-window checks before managed automation;
- audit log for each action attempt;
- dry-run mode available in the RPA sidecar;
- no reuse of upstream secrets, tokens, binary modules, or brand assets.

## Quick Start

1. Clone submodules after pulling this repository:

```powershell
git submodule update --init --recursive
```

2. Keep real keys in `.env`; `.env.example` is intentionally placeholder-only.
3. Start the backend:

```powershell
cd C:\Users\28293\Desktop\Agent\backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8710
```

4. Start the RPA sidecar:

```powershell
cd C:\Users\28293\Desktop\Agent\rpa-sidecar
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8720
```

5. Start the desktop client:

```powershell
cd C:\Users\28293\Desktop\Agent\desktop-client
npm install
npm run dev
```

Or run all three services:

```powershell
cd C:\Users\28293\Desktop\Agent
.\Start-Agent.ps1
```

## Verification

Run backend and sidecar tests:

```powershell
cd C:\Users\28293\Desktop\Agent\backend
python -m pytest

cd C:\Users\28293\Desktop\Agent\rpa-sidecar
python -m pytest
```

Run frontend checks:

```powershell
cd C:\Users\28293\Desktop\Agent\desktop-client
npm run typecheck
```
