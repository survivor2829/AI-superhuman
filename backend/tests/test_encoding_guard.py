from pathlib import Path


def test_customer_facing_source_has_no_common_mojibake_markers():
    root = Path(__file__).resolve().parents[2]
    checked_paths = [
        root / "backend" / "app",
        root / "desktop-client" / "src",
        root / "rpa-sidecar" / "app",
    ]
    markers = ["?????", "�", "å¾®", "æ", "çº", "é", "è¯", "ä½"]
    offenders: list[str] = []

    for checked_path in checked_paths:
        for path in checked_path.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".css"}:
                continue
            text = path.read_text(encoding="utf-8")
            if any(marker in text for marker in markers):
                offenders.append(str(path))

    assert offenders == []
