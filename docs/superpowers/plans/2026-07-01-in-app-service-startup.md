# In-App Service Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the desktop app own service startup and recovery so users do not open PowerShell or copy commands.

**Architecture:** Electron main process manages local services, exposes startup and administrator restart IPC to the React UI, and keeps PowerShell hidden except for the Windows UAC confirmation. The React app shows a plain Chinese service readiness card and offers a single repair button when services are unavailable or stale.

**Tech Stack:** Electron main/preload IPC, React + TypeScript renderer, PowerShell `Start-Process -Verb RunAs`, existing `Start-Agent.ps1`.

## Global Constraints

- Customer-facing operation happens inside the desktop app.
- The only acceptable external confirmation is a Windows permission popup.
- Do not expose API keys, database keys, tokens, or technical command output in customer UI.
- Do not change the verified contact send queue behavior in this plan.
- Keep PowerShell windows hidden for normal startup and restart paths.

---

### Task 1: Electron Service Manager IPC

**Files:**
- Modify: `C:\Users\28293\Desktop\Agent\desktop-client\electron\main.cjs`
- Modify: `C:\Users\28293\Desktop\Agent\desktop-client\electron\preload.cjs`

**Interfaces:**
- Produces: `window.agentDesktop.getServiceStatus(): Promise<ServiceStatus>`
- Produces: `window.agentDesktop.restartServicesAsAdmin(): Promise<{ ok: boolean; message: string }>`

- [ ] **Step 1: Add service status helper in Electron main**

Add a helper that checks backend, sidecar, and renderer URLs and returns booleans plus a Chinese message.

- [ ] **Step 2: Add administrator restart helper in Electron main**

Use `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command Start-Process powershell.exe -Verb RunAs ...` with `-WindowStyle Hidden -File C:\Users\28293\Desktop\Agent\Start-Agent.ps1`.

- [ ] **Step 3: Expose IPC channels**

Register `app:get-service-status` and `app:restart-services-admin`.

- [ ] **Step 4: Expose preload bridge methods**

Add `getServiceStatus` and `restartServicesAsAdmin` to `agentDesktop`.

- [ ] **Step 5: Verify Electron build**

Run: `npm run build` in `C:\Users\28293\Desktop\Agent\desktop-client`.

### Task 2: Customer-Facing Startup UI

**Files:**
- Modify: `C:\Users\28293\Desktop\Agent\desktop-client\src\lib\api.ts`
- Modify: `C:\Users\28293\Desktop\Agent\desktop-client\src\App.tsx`
- Modify: `C:\Users\28293\Desktop\Agent\desktop-client\src\styles\global.css`
- Modify: `C:\Users\28293\Desktop\Agent\desktop-client\tests\static-ui-check.mjs`

**Interfaces:**
- Consumes: `window.agentDesktop.getServiceStatus`
- Consumes: `window.agentDesktop.restartServicesAsAdmin`
- Produces: a customer-readable status card with a single “修复启动” button.

- [ ] **Step 1: Add TypeScript bridge types**

Extend `DesktopBridge` with service status and admin restart methods.

- [ ] **Step 2: Add renderer state and refresh logic**

Poll service status through Electron when available, falling back to HTTP health checks in browser mode.

- [ ] **Step 3: Add customer-readable status card**

Show “软件服务已就绪 / 正在启动 / 需要确认权限 / 启动失败” and a “修复启动” button.

- [ ] **Step 4: Wire button to admin restart**

Clicking “修复启动” asks Windows for permission through Electron and then refreshes status.

- [ ] **Step 5: Update static UI check**

Require “软件服务”, “修复启动”, and forbid PowerShell/customer command copy in the main UI.

- [ ] **Step 6: Verify**

Run: `npm run build` and `npm run test:static` in `C:\Users\28293\Desktop\Agent\desktop-client`.

### Task 3: Launcher Cleanup

**Files:**
- Modify: `C:\Users\28293\Desktop\Agent\启动Agent.bat`

**Interfaces:**
- Produces: double-click launcher that starts `Start-Agent.ps1` hidden and exits without a pause prompt.

- [ ] **Step 1: Replace mojibake launcher text**

Use UTF-8 friendly minimal batch content.

- [ ] **Step 2: Launch PowerShell hidden**

Use `start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Start-Agent.ps1"`.

- [ ] **Step 3: Verify**

Run static checks and inspect the file content.

