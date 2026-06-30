# Agent MVP 正式交付说明

这份目录不是单个脚本或单份报告，而是一个可继续开发的本地产品包：桌面端、后端、RPA sidecar、接口规格、逆向画像、架构文档和验收说明都已经放在 `C:\Users\28293\Desktop\Agent`。

## 1. 你应该先看什么

建议按这个顺序验收：

1. 打开 `DELIVERY.md`：看本页，确认交付范围。
2. 打开 `docs/reverse-report.md`：看对原软件的逆向画像、模块判断、功能矩阵和接口线索。
3. 打开 `docs/architecture.md`：看新产品架构、数据流、任务流和 RPA 状态机。
4. 打开 `api/openapi.yaml`：看后端和本地 RPA 服务的接口契约。
5. 运行 `Start-Agent.ps1`：启动后端、RPA sidecar 和桌面端 Web 预览。

## 2. 当前已经实现的内容

### 桌面端

路径：`desktop-client`

已实现 Electron + React + TypeScript 桌面控制台基础版，包含：

- 微信账号状态面板
- 联系人/会话托管入口
- AI 自动回复计划
- 群发触达计划
- 朋友圈发布计划
- 自动点赞/评论计划
- 任务中心
- 审计日志摘要
- 设置/护栏状态

当前 Web 预览地址：

- `http://127.0.0.1:5173`

### 后端

路径：`backend`

已实现 FastAPI MVP，包括：

- `/health`
- `/auth/login`
- `/wechat/status`
- `/wechat/contacts/sync`
- `/wechat/contacts`
- `/chat/sessions`
- `/chat/history`
- `/chat/ai-reply`
- `/chat/send`
- `/mass-send/plans`
- `/moments/publish-plans`
- `/moments/marketing-plans`
- `/tasks`
- `/audit/logs`

当前 Swagger 地址：

- `http://127.0.0.1:8710/docs`

### RPA sidecar

路径：`rpa-sidecar`

已实现本地微信自动化服务的可替换骨架，包含：

- `/health`
- `/wechat/status`
- `/wechat/contacts/sync`
- `/wechat/chat/sessions`
- `/wechat/message/send`
- `/wechat/moments/publish`
- `/wechat/moments/like`
- `/wechat/moments/comment`
- `/rpa/stop`

当前 Swagger 地址：

- `http://127.0.0.1:8720/docs`

默认运行模式是 `dry_run`，用于安全验收接口、状态机、白名单、限额和审计链路。接真实微信桌面自动化时，应在 `rpa-sidecar/app/services/automation.py` 里替换 driver 实现。

## 3. 安全与边界

这个版本按“授权环境下的功能复刻与衍生产品”处理，但实现上采用 clean-room 方式：

- 不复用对方线上 token
- 不复用对方密钥
- 不复用对方品牌素材
- 不复用对方打包二进制模块
- 不绕过微信或第三方平台安全机制
- 只为授权测试号、本机桌面微信和白名单客户设计

内置护栏：

- 测试账号白名单
- 客户白名单
- 单计划限额
- 全局暂停
- 时间窗
- 任务失败退避
- 审计日志

## 4. 一键启动

在 PowerShell 里运行：

```powershell
cd C:\Users\28293\Desktop\Agent
.\Start-Agent.ps1
```

脚本会尝试启动：

- 后端：`http://127.0.0.1:8710`
- RPA sidecar：`http://127.0.0.1:8720`
- 桌面端预览：`http://127.0.0.1:5173`

日志位置：

- `backend/backend.log`
- `backend/backend.err.log`
- `rpa-sidecar/sidecar.log`
- `rpa-sidecar/sidecar.err.log`
- `desktop-client/vite.log`
- `desktop-client/vite.err.log`

## 5. 验收命令

后端测试：

```powershell
cd C:\Users\28293\Desktop\Agent\backend
python -m pytest
```

RPA 测试：

```powershell
cd C:\Users\28293\Desktop\Agent\rpa-sidecar
python -m pytest
```

前端构建：

```powershell
cd C:\Users\28293\Desktop\Agent\desktop-client
npm run build
```

接口健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8710/health
Invoke-RestMethod http://127.0.0.1:8720/health
Invoke-WebRequest http://127.0.0.1:5173
```

## 6. 当前验收结果

本次生成后已经完成一次实际验证：

- Backend pytest：4 passed
- RPA pytest：2 passed
- Desktop build：成功
- Backend health：`{"status":"ok","service":"backend"}`
- RPA health：`{"status":"ok","service":"rpa-sidecar","mode":"dry_run"}`
- Desktop preview：HTTP 200

## 7. 下一步开发重点

现在的版本是 MVP 基座。要进入真实业务可用阶段，下一步建议按这个顺序推进：

1. 把 `rpa-sidecar` 的 dry-run driver 替换成 Windows UI Automation / 截图识别 / 窗口句柄控制实现。
2. 接入真实模型供应商：通义千问、豆包、OpenAI 或 Anthropic 兼容接口。
3. 把后端内存存储替换成 SQLite/PostgreSQL。
4. 增加真实微信测试号的 8 小时托管验收。
5. 增加失败截图、任务重试和人工接管台。
6. 做 Electron 打包，形成可安装桌面产品。
