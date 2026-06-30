# Architecture

## Overview

Agent MVP has three cooperating services:

```mermaid
flowchart LR
  Operator["Desktop Client<br/>Electron + React"] --> Backend["Backend API<br/>FastAPI"]
  Backend --> Queue["Task Queue<br/>in-process MVP / Redis-ready"]
  Backend --> DB["SQLite MVP<br/>PostgreSQL-ready schema"]
  Backend --> LLM["LLM Provider<br/>DashScope / Doubao"]
  Backend --> Sidecar["RPA Sidecar<br/>FastAPI local service"]
  Sidecar --> WeChat["WeChat Desktop<br/>test account"]
  Sidecar --> AuditMedia["Screenshots / local evidence"]
```

## Components

### Desktop Client

The client is an operator console, not a hidden automation implant. It shows account state, contacts, plans, task runs, and audit records. It talks only to the backend and never directly executes WeChat actions.

### Backend

The backend owns data and policy:

- plan creation and validation;
- whitelist and quota enforcement;
- LLM provider routing;
- task state transitions;
- audit log persistence;
- sidecar orchestration.

### RPA Sidecar

The sidecar owns local UI automation:

- process/window detection;
- dry-run simulation;
- guarded message, moment, like, and comment endpoints;
- evidence capture hooks;
- stop signal support.

## Task Flow

```mermaid
sequenceDiagram
  participant UI as Desktop Client
  participant API as Backend
  participant LLM as LLM Provider
  participant RPA as RPA Sidecar
  participant WX as WeChat Desktop

  UI->>API: Create automation plan
  API->>API: Validate whitelist, quota, time window
  API->>LLM: Generate reply/copy if needed
  API->>API: Create TaskRun
  API->>RPA: Execute local action
  RPA->>WX: Desktop automation
  RPA-->>API: ActionResult
  API->>API: Persist AuditLog
  API-->>UI: WebSocket task event
```

## RPA State Machine

```mermaid
stateDiagram-v2
  [*] --> IDLE
  IDLE --> CHECKING_WECHAT
  CHECKING_WECHAT --> READY: account detected and whitelisted
  CHECKING_WECHAT --> BLOCKED: missing window or unapproved account
  READY --> EXECUTING
  EXECUTING --> VERIFYING
  VERIFYING --> SUCCEEDED
  VERIFYING --> RETRY_WAIT
  RETRY_WAIT --> EXECUTING
  RETRY_WAIT --> FAILED
  EXECUTING --> STOPPED: kill switch
  SUCCEEDED --> IDLE
  FAILED --> IDLE
  BLOCKED --> IDLE
  STOPPED --> IDLE
```

## Guardrail Policy

Every outbound action must pass:

1. account whitelist;
2. contact whitelist or plan target whitelist;
3. quota check;
4. time-window check;
5. global kill switch check.

The sidecar also supports `dry_run=true` so the full backend flow can be verified without touching WeChat.
