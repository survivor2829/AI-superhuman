from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


@dataclass(frozen=True)
class AgentSettings:
    root_dir: Path
    database_url: str
    rpa_sidecar_url: str
    llm_provider: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    wechat_process_name: str
    wechat_window_title: str
    rpa_dry_run: bool
    contact_touch_interval_days: int
    touch_interval_mode: str
    rpa_send_prefix: str
    prompt_docx_path: Path

    @classmethod
    def load(cls, root_dir: Path | None = None) -> "AgentSettings":
        root = root_dir or Path(__file__).resolve().parents[3]
        env_values = _read_env_file(root / ".env")

        def get(name: str, default: str = "") -> str:
            return os.environ.get(name) or env_values.get(name) or default

        return cls(
            root_dir=root,
            database_url=get("DATABASE_URL", "sqlite:///./agent.db"),
            rpa_sidecar_url=get("RPA_SIDECAR_URL", "http://127.0.0.1:8720"),
            llm_provider=get("LLM_PROVIDER", "deepseek"),
            deepseek_api_key=get("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            wechat_process_name=get("WECHAT_PROCESS_NAME", "Weixin"),
            wechat_window_title=get("WECHAT_WINDOW_TITLE", "微信"),
            rpa_dry_run=get("RPA_DRY_RUN", "false").lower() in {"1", "true", "yes"},
            contact_touch_interval_days=int(get("CONTACT_TOUCH_INTERVAL_DAYS", "15")),
            touch_interval_mode=get("TOUCH_INTERVAL_MODE", "production"),
            rpa_send_prefix=get("RPA_SEND_PREFIX", "这是测试说明："),
            prompt_docx_path=Path(get("PROMPT_DOCX_PATH", str(Path.home() / "Desktop" / "搭建提示词_玺联惠创客合伙人版_仅改蓝字.docx"))),
        )

    def public_dict(self) -> dict[str, object]:
        return {
            "database_url": self.database_url,
            "rpa_sidecar_url": self.rpa_sidecar_url,
            "llm_provider": self.llm_provider,
            "deepseek_base_url": self.deepseek_base_url,
            "deepseek_model": self.deepseek_model,
            "deepseek_api_key_configured": bool(self.deepseek_api_key),
            "wechat_process_name": self.wechat_process_name,
            "wechat_window_title": self.wechat_window_title,
            "rpa_dry_run": self.rpa_dry_run,
            "contact_touch_interval_days": self.contact_touch_interval_days,
            "touch_interval_mode": self.touch_interval_mode,
            "rpa_send_prefix": self.rpa_send_prefix,
            "prompt_docx_path": str(self.prompt_docx_path),
        }
