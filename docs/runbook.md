# Runbook

## Start

After cloning, fetch the bundled decrypt helper submodule:

```powershell
git submodule update --init --recursive
```

```powershell
cd C:\Users\28293\Desktop\Agent
.\Start-Agent.ps1
```

Services:

- Backend: `http://127.0.0.1:8710/docs`
- RPA sidecar: `http://127.0.0.1:8720/docs`
- Desktop preview: `http://127.0.0.1:5173`

## Configuration

Real secrets live in `.env`. `.env.example` must contain placeholders only.

Important values:

- `LLM_PROVIDER=deepseek`
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_MODEL=deepseek-v4-flash`
- `WECHAT_PROCESS_NAME=Weixin`
- `WECHAT_WINDOW_TITLE=微信`
- `RPA_DRY_RUN=false`
- `CONTACT_TOUCH_INTERVAL_DAYS=15`
- `RPA_SEND_PREFIX=这是测试说明：`

## Checks

```powershell
Invoke-RestMethod http://127.0.0.1:8710/settings
Invoke-RestMethod http://127.0.0.1:8710/wechat/window/probe
Invoke-RestMethod http://127.0.0.1:8720/wechat/window/probe
```

## Prompt Import

The console has two prompt import modes:

- `导入提示词`: imports the default docx path from `.env` / backend settings.
- `选择文件导入`: opens a file picker and uploads a selected `.docx` into `C:\Users\28293\Desktop\Agent\prompts\uploads`.

Browser access from `http://127.0.0.1:5173` and `http://localhost:5173` is allowed by backend CORS middleware.

## Evidence

Screenshots and placeholder evidence are written under:

```text
C:\Users\28293\Desktop\Agent\evidence
```

Each outbound action should also create:

- `task_runs`
- `task_events`
- `audit_logs`
- `evidence_files`

## Stop

Use PowerShell to stop the listening processes if needed:

```powershell
Get-NetTCPConnection -LocalPort 8710,8720,5173 | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }
```
