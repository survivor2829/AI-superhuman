from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.main import app


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    body = "".join(
        f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with ZipFile(path, "w") as docx:
        docx.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        docx.writestr("word/document.xml", document)


def test_prompt_import_allows_local_browser_preflight():
    client = TestClient(app)

    response = client.options(
        "/prompts/import-docx",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_prompt_import_accepts_uploaded_docx(tmp_path):
    docx_path = tmp_path / "prompt.docx"
    _write_docx(
        docx_path,
        [
            "AI专家搭建——提示词：",
            "#角色设定",
            "你是玺联惠会员超市的创客合伙人。",
            "#销售流程",
            "1. 热情问候",
            "#提醒人工",
            "当客户问报价、问会员、问售后、预约上海展厅时给客户打标签为意向客户。",
            "AI专家搭建——知识库：",
            "问题：怎么合作",
            "答案：先了解客户城市和客户类型。",
        ],
    )
    client = TestClient(app)

    with docx_path.open("rb") as file_handle:
        response = client.post(
            "/prompts/import-docx/file",
            files={
                "file": (
                    "prompt.docx",
                    file_handle,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["knowledge_count"] == 1
    assert "创客合伙人" in payload["system_prompt_preview"]
    assert payload["source_path"].endswith(".docx")
