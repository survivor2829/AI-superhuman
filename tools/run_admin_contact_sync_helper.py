from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one elevated WeChat contact sync and write a public result file.")
    parser.add_argument("--result", required=True, help="Path to the public result JSON file.")
    args = parser.parse_args()

    agent_root = Path(__file__).resolve().parents[1]
    sidecar_root = agent_root / "rpa-sidecar"
    sys.path.insert(0, str(sidecar_root))

    result_path = Path(args.result)
    try:
        from app.services.admin_contact_sync import run_admin_contact_sync

        run_admin_contact_sync(result_path=result_path)
        return 0
    except Exception as exc:
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "success": False,
                    "reason": f"admin_helper_error:{type(exc).__name__}",
                    "message": "管理员同步助手运行失败，请重新点击静默同步通讯录。",
                    "completed_at": datetime.now(UTC).isoformat(),
                    "trace": traceback.format_exc(limit=3),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
