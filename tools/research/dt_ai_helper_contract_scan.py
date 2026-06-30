from __future__ import annotations

import argparse
import json
import marshal
import re
import struct
import types
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


DEFAULT_TARGET = Path(r"C:\Users\28293\AppData\Local\Programs\dt-ai-helper")
SENSITIVE_RE = re.compile(
    r"(?i)(authorization|bearer\s+[a-z0-9._-]+|cookie|token|secret|api[_-]?key|password|passwd|sk-[a-z0-9_-]+)"
)
LONG_VALUE_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z0-9_./+=-]{72,}(?![A-Za-z0-9_])")
INTERESTING_MARKERS = (
    "wechat",
    "weixin",
    "message",
    "send",
    "contact",
    "moment",
    "task",
    "rpa",
    "agent",
    "ipc",
    "socket",
    "websocket",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "flask",
    "route",
    "uvicorn",
    "waitress",
    "朋友圈",
    "发送",
    "触达",
    "群发",
)

INTERESTING_FILE_RE = re.compile(
    r"(?i)(wechat|weixin|message|send|contact|moment|task|rpa|agent|ipc|socket|ws|api|route|flask|main\.exe)"
)
LOCAL_URL_RE = re.compile(r"(?i)\b(?:https?|ws)://(?:127\.0\.0\.1|localhost|0\.0\.0\.0)(?::\d+)?[A-Za-z0-9_./?=&:-]*")
ROUTE_RE = re.compile(r"(?i)(?<![A-Za-z0-9_])/[A-Za-z0-9_./{}:-]*(?:wechat|weixin|wx|message|send|contact|moment|task|rpa|agent|chat|api)[A-Za-z0-9_./{}:-]*")
IPC_RE = re.compile(r"(?i)[A-Za-z0-9_./:-]*(?:ipcMain|ipcRenderer|ipc-|invoke|handle|sendSync|WebSocket|socket\.io|postMessage)[A-Za-z0-9_./:-]*")
PY_SERVER_RE = re.compile(r"(?i)[A-Za-z0-9_./:@-]*(?:Flask|Blueprint|waitress|uvicorn|fastapi|websocket|app\.route|add_url_rule|127\.0\.0\.1|localhost)[A-Za-z0-9_./:@-]*")
SEND_RE = re.compile(r"(?i)[A-Za-z0-9_./:-]*(?:sendMessage|send_message|messageSend|massSend|群发|发送|触达|朋友圈|moment|like|comment)[A-Za-z0-9_./:-]*")
PYINSTALLER_MAGIC = b"MEI\x0c\x0b\x0a\x0b\x0e"
SELECTED_PYZ_MODULES = (
    "scripts.automation.actions.MassSendWechatManagerV2",
    "scripts.automation.actions.MomentMarketingManager",
    "scripts.automation.actions.MomentPublishManager",
    "scripts.automation.actions.MomentCommentReplyManager",
    "scripts.wechat.WechatAutomation",
    "scripts.wechat.ContactManager",
    "scripts.http.wechat_api",
    "scripts.ws.automation_control",
)
CONTRACT_PYZ_MODULE_PREFIXES = (
    "scripts.http.",
    "scripts.ws.",
    "scripts.task.",
    "scripts.automation.",
    "scripts.wechat.",
    "scripts.wechat_ocr.",
)
STATUS_RE = re.compile(
    r"(?i)(pending|running|success|succeed|failed|blocked|paused|cancel|stopped|dispatch|progress|client_lost|waiting|completed|taskstatus)"
)
EVENT_RE = re.compile(
    r"(?i)(task[._:-]|message[._:-]|client[._:-]|automation[._:-]|progress|heartbeat|connect|disconnect|pause|resume|callback|notify|event)"
)
SCREEN_AUTOMATION_RE = re.compile(
    r"(?i)(uiautomation|ocr|screenshot|click|sendkeys|movewindow|input_msg|wechatocr|safe_click|window_handle|get_wx_controls)"
)


def redact(value: str) -> str:
    value = value.replace("\x00", "").strip()
    value = SENSITIVE_RE.sub("<redacted-sensitive-marker>", value)
    value = LONG_VALUE_RE.sub("<redacted-long-value>", value)
    if len(value) > 220:
        value = value[:217] + "..."
    return value


def unique_limited(values: Iterable[str], *, limit: int = 80) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for raw in values:
        value = redact(raw)
        if not value or value in seen:
            continue
        if "<redacted-sensitive-marker>" in value:
            continue
        seen.add(value)
        rows.append(value)
        if len(rows) >= limit:
            break
    return rows


def is_interesting(value: str) -> bool:
    lower = value.lower()
    return any(marker in lower for marker in INTERESTING_MARKERS)


def marker_bytes() -> list[bytes]:
    rows: list[bytes] = []
    for marker in INTERESTING_MARKERS:
        rows.append(marker.encode("utf-8", "ignore").lower())
        if marker.isascii():
            rows.append(marker.encode("utf-16le", "ignore").lower())
    return [row for row in rows if row]


def printable_window(data: bytes, center: int, *, radius: int = 220) -> str:
    start = max(0, center - radius)
    end = min(len(data), center + radius)
    window = data[start:end]
    text = window.decode("utf-8", "ignore")
    if len(text.strip()) < 8:
        text = window.decode("utf-16le", "ignore")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_strings(path: Path, *, max_bytes: int | None = None, limit: int = 12_000) -> list[str]:
    if not path.exists():
        return []
    data = path.read_bytes()
    if max_bytes is not None:
        data = data[:max_bytes]
    lower = data.lower()
    snippets: list[str] = []
    seen_positions: set[int] = set()
    for marker in marker_bytes():
        start = 0
        per_marker = 0
        while len(snippets) < limit and per_marker < 700:
            index = lower.find(marker, start)
            if index < 0:
                break
            bucket = index // 120
            if bucket not in seen_positions:
                seen_positions.add(bucket)
                snippet = printable_window(data, index)
                if snippet and is_interesting(snippet):
                    snippets.append(snippet)
                    per_marker += 1
            start = index + max(1, len(marker))
    return snippets


def matching_strings(strings: Iterable[str], pattern: re.Pattern[str], *, limit: int = 80) -> list[str]:
    matches: list[str] = []
    for value in strings:
        for match in pattern.finditer(value):
            matches.append(match.group(0))
    return unique_limited(matches, limit=limit)


def walk_code_objects(code: types.CodeType) -> Iterable[types.CodeType]:
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from walk_code_objects(const)


def string_constants_from_code(code: types.CodeType) -> tuple[list[str], list[str], list[str]]:
    strings: list[str] = []
    names: list[str] = []
    code_object_names: list[str] = []
    for item in walk_code_objects(code):
        code_object_names.append(item.co_name)
        names.extend(str(name) for name in item.co_names if isinstance(name, str))
        for const in item.co_consts:
            if isinstance(const, str):
                strings.append(const)
    return strings, names, code_object_names


def summarize_module_contract(module_data: bytes) -> dict[str, object]:
    try:
        code = marshal.loads(module_data)
    except Exception as exc:
        return {"marshal_parse_error": type(exc).__name__}
    if not isinstance(code, types.CodeType):
        return {"marshal_type": type(code).__name__}

    strings, names, code_object_names = string_constants_from_code(code)
    text_pool = strings + names
    slash_constants = [value for value in strings if value.startswith("/") and 3 <= len(value) <= 180]
    interesting_names = [
        value
        for value in names
        if any(term in value.lower() for term in ("route", "task", "event", "send", "message", "contact", "moment", "wechat", "status", "pause", "resume"))
    ]
    return {
        "code_objects": unique_limited(code_object_names, limit=70),
        "interesting_names": unique_limited(interesting_names, limit=90),
        "route_constants": unique_limited(slash_constants + matching_strings(strings, ROUTE_RE, limit=80), limit=90),
        "local_urls": matching_strings(strings, LOCAL_URL_RE, limit=30),
        "task_status_terms": unique_limited([value for value in text_pool if STATUS_RE.search(value)], limit=90),
        "event_terms": unique_limited([value for value in text_pool if EVENT_RE.search(value)], limit=90),
        "send_terms": matching_strings(text_pool, SEND_RE, limit=80),
        "screen_automation_terms": unique_limited([value for value in text_pool if SCREEN_AUTOMATION_RE.search(value)], limit=80),
        "interesting_constants": unique_limited([value for value in strings if is_interesting(value)], limit=80),
    }


def asar_list(asar_path: Path) -> list[str]:
    if not asar_path.exists():
        return []
    try:
        with asar_path.open("rb") as handle:
            prefix = handle.read(16)
            if len(prefix) != 16:
                return []
            json_size = struct.unpack("<I", prefix[12:16])[0]
            header = json.loads(handle.read(json_size).decode("utf-8", "ignore"))
    except Exception:
        return []

    def walk(node: dict[str, object], prefix: str = "") -> Iterable[str]:
        files = node.get("files")
        if not isinstance(files, dict):
            return
        for name, child in files.items():
            path = f"{prefix}\\{name}" if prefix else f"\\{name}"
            if isinstance(child, dict) and "files" in child:
                yield path
                yield from walk(child, path)
            else:
                yield path

    rows: list[str] = []
    for value in walk(header):
        if not value:
            continue
        if value.startswith("\\node_modules") and not INTERESTING_FILE_RE.search(value):
            continue
        rows.append(value)
    return rows


def summarize_config(config_path: Path) -> dict[str, object]:
    if not config_path.exists():
        return {"exists": False}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"exists": True, "parse_error": type(exc).__name__}
    return {
        "exists": True,
        "keys": sorted(data.keys()),
        "client_name": data.get("clientName"),
        "has_theme_config": "themeConfig" in data,
    }


def scan_unpacked_resources(resources_dir: Path) -> dict[str, object]:
    internal = resources_dir / "_internal"
    script_dir = internal / "scripts"
    wechat_icon_dir = script_dir / "wechat_ocr" / "wechat_icon"
    deps = []
    if internal.exists():
        deps = sorted(
            child.name
            for child in internal.iterdir()
            if child.is_dir()
            and child.name.lower()
            in {
                "flask-3.1.1.dist-info",
                "apscheduler-3.11.0.dist-info",
                "patchright",
                "playwright",
                "selenium",
                "cv2",
                "pil",
                "sqlcipher3",
                "websockets",
                "win32",
                "psutil",
            }
        )
    relevant_files: list[str] = []
    if resources_dir.exists():
        for path in resources_dir.rglob("*"):
            if path.is_file():
                rel = str(path.relative_to(resources_dir))
                if INTERESTING_FILE_RE.search(rel):
                    relevant_files.append(rel)
    icon_count = len(list(wechat_icon_dir.rglob("*.png"))) if wechat_icon_dir.exists() else 0
    return {
        "known_dependency_dirs": deps,
        "wechat_ocr_icon_count": icon_count,
        "relevant_resource_files": relevant_files[:160],
        "relevant_resource_file_count": len(relevant_files),
    }


def parse_pyinstaller_archive(exe_path: Path) -> dict[str, object]:
    if not exe_path.exists():
        return {"exists": False, "cookie_found": False}
    data = exe_path.read_bytes()
    cookie_pos = data.rfind(PYINSTALLER_MAGIC)
    if cookie_pos < 0:
        return {"exists": True, "cookie_found": False}
    try:
        _, pkg_len, toc_pos, toc_len, py_version, pylib = struct.unpack("!8sIIii64s", data[cookie_pos : cookie_pos + 88])
    except Exception as exc:
        return {"exists": True, "cookie_found": True, "parse_error": type(exc).__name__}
    pkg_start = cookie_pos + 88 - pkg_len
    cursor = pkg_start + toc_pos
    toc_end = cursor + toc_len
    carchive_entries: list[dict[str, object]] = []
    while cursor < toc_end:
        if cursor + 18 > toc_end:
            break
        entry_len, offset, compressed_len, uncompressed_len, compressed, type_code = struct.unpack("!iIIIBc", data[cursor : cursor + 18])
        name = data[cursor + 18 : cursor + entry_len].split(b"\0", 1)[0].decode("utf-8", "ignore")
        carchive_entries.append(
            {
                "name": name,
                "type": type_code.decode("latin1"),
                "offset": offset,
                "compressed_len": compressed_len,
                "uncompressed_len": uncompressed_len,
                "compressed": bool(compressed),
            }
        )
        cursor += entry_len

    pyz_summary: dict[str, object] = {
        "module_count": 0,
        "interesting_modules": [],
        "selected_module_terms": {},
        "module_contracts": {},
    }
    pyz_entry = next((entry for entry in carchive_entries if entry["name"] == "PYZ.pyz"), None)
    if pyz_entry:
        pyz = data[pkg_start + int(pyz_entry["offset"]) : pkg_start + int(pyz_entry["offset"]) + int(pyz_entry["compressed_len"])]
        try:
            toc_offset = struct.unpack("!I", pyz[8:12])[0]
            pyz_toc = marshal.loads(pyz[toc_offset:])
            module_index = {name: entry for name, entry in pyz_toc if isinstance(name, str)}
            interesting_modules = [
                name
                for name in sorted(module_index)
                if name.startswith("scripts.")
                and any(term in name.lower() for term in ("wechat", "send", "moment", "contact", "automation", "message", "ws", "http", "db", "task"))
            ]
            selected_terms: dict[str, list[str]] = {}
            module_contracts: dict[str, object] = {}
            contract_modules = [
                name
                for name in sorted(module_index)
                if name in SELECTED_PYZ_MODULES or any(name.startswith(prefix) for prefix in CONTRACT_PYZ_MODULE_PREFIXES)
            ]
            for module_name in contract_modules:
                entry = module_index.get(module_name)
                if not entry:
                    continue
                _, offset, length = entry
                try:
                    module_data = zlib.decompress(pyz[offset : offset + length])
                except Exception:
                    continue
                module_strings = [
                    item.decode("utf-8", "ignore")
                    for item in re.findall(rb"[\x20-\x7e]{4,}", module_data)
                    if any(
                        term in item.decode("utf-8", "ignore").lower()
                        for term in ("send", "wechat", "message", "contact", "moment", "window", "uia", "ocr", "click", "input", "receipt", "chat", "wx")
                    )
                ]
                if module_name in SELECTED_PYZ_MODULES:
                    selected_terms[module_name] = unique_limited(module_strings, limit=40)
                contract = summarize_module_contract(module_data)
                has_signal = any(
                    contract.get(key)
                    for key in (
                        "route_constants",
                        "task_status_terms",
                        "event_terms",
                        "send_terms",
                        "screen_automation_terms",
                    )
                )
                if has_signal or module_name in SELECTED_PYZ_MODULES or module_name.startswith(("scripts.http.", "scripts.ws.", "scripts.task.")):
                    module_contracts[module_name] = contract
            pyz_summary = {
                "module_count": len(module_index),
                "interesting_modules": interesting_modules[:240],
                "interesting_module_count": len(interesting_modules),
                "selected_module_terms": selected_terms,
                "module_contracts": module_contracts,
                "module_contract_count": len(module_contracts),
            }
        except Exception as exc:
            pyz_summary = {"parse_error": type(exc).__name__}

    main_terms: list[str] = []
    main_entry = next((entry for entry in carchive_entries if entry["name"] == "main"), None)
    if main_entry:
        raw = data[pkg_start + int(main_entry["offset"]) : pkg_start + int(main_entry["offset"]) + int(main_entry["compressed_len"])]
        try:
            main_data = zlib.decompress(raw) if main_entry["compressed"] else raw
            main_terms = matching_strings([printable_window(main_data, match.start(), radius=140) for match in re.finditer(rb"scripts|wechat|flask|waitress|port|host", main_data, re.I)], PY_SERVER_RE, limit=80)
        except Exception:
            main_terms = []

    return {
        "exists": True,
        "cookie_found": True,
        "python_version": py_version,
        "python_runtime": pylib.split(b"\0", 1)[0].decode("utf-8", "ignore"),
        "carchive_entries": carchive_entries,
        "main_entry_terms": main_terms,
        "pyz": pyz_summary,
    }


def scan(target_root: Path) -> dict[str, object]:
    resources_dir = target_root / "resources"
    asar_path = resources_dir / "app.asar"
    unpacked_resources = resources_dir / "app.asar.unpacked" / "resources"
    main_exe = unpacked_resources / "main.exe"
    config_path = unpacked_resources / "config.json"

    asar_files = asar_list(asar_path)
    interesting_asar_files = [path for path in asar_files if not path.startswith("\\node_modules") and INTERESTING_FILE_RE.search(path)]

    asar_strings = extract_strings(asar_path)
    main_strings = extract_strings(main_exe)
    all_strings = asar_strings + main_strings

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "target_root": str(target_root),
        "artifacts": {
            "asar_exists": asar_path.exists(),
            "asar_size": asar_path.stat().st_size if asar_path.exists() else 0,
            "main_exe_exists": main_exe.exists(),
            "main_exe_size": main_exe.stat().st_size if main_exe.exists() else 0,
            "config": summarize_config(config_path),
        },
        "asar": {
            "file_count": len(asar_files),
            "interesting_files": interesting_asar_files[:220],
            "interesting_file_count": len(interesting_asar_files),
            "local_urls": matching_strings(asar_strings, LOCAL_URL_RE, limit=80),
            "routes": matching_strings(asar_strings, ROUTE_RE, limit=120),
            "ipc_or_ws_terms": matching_strings(asar_strings, IPC_RE, limit=120),
            "send_terms": matching_strings(asar_strings, SEND_RE, limit=120),
        },
        "sidecar": {
            **scan_unpacked_resources(unpacked_resources),
            "pyinstaller": parse_pyinstaller_archive(main_exe),
            "local_urls": matching_strings(main_strings, LOCAL_URL_RE, limit=80),
            "python_server_terms": matching_strings(main_strings, PY_SERVER_RE, limit=120),
            "routes": matching_strings(main_strings, ROUTE_RE, limit=120),
            "send_terms": matching_strings(main_strings, SEND_RE, limit=120),
        },
        "contract_assessment": {
            "non_screen_send_verified": False,
            "safe_to_enable_auto_send": False,
            "reason": "Static scan found automation assets and candidate names, but no verified non-screen send channel or receipt contract.",
            "no_send_policy": "Scanner only reads local files and does not start dt-ai-helper or call any candidate endpoint.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="No-send static contract scanner for dt-ai-helper.")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = scan(args.target)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "non_screen_send_verified": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
