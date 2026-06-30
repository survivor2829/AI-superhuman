from pathlib import Path
from zipfile import ZipFile

from app.services.prompt_loader import PromptLoader


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


def test_prompt_loader_extracts_sales_prompt_sections(tmp_path):
    docx_path = tmp_path / "prompt.docx"
    _write_docx(
        docx_path,
        [
            "AI专家搭建——提示词：",
            "#角色设定",
            "你是玺联惠会员超市的创客合伙人。",
            "#销售流程",
            "1. 热情问候",
            "2. 询问客户需求和预算",
            "#限制条件",
            "不使用过长的段落回复。",
            "#提醒人工",
            "当客户愿意留需求、要报价、问会员、问售后、预约上海展厅或希望人工对接时给客户打标签为意向客户。",
            "AI专家搭建——知识库：",
            "问题：会员权益有哪些？",
            "答案：会员权益有198、980、1980、9800、19800几种。",
        ],
    )

    imported = PromptLoader().load(docx_path)

    assert "玺联惠会员超市" in imported.system_prompt
    assert "热情问候" in imported.sales_flow
    assert "不使用过长" in imported.constraints
    assert imported.handoff_rules.intent_tag == "意向客户"
    assert imported.knowledge_base[0].question == "会员权益有哪些？"
    assert "19800" in imported.knowledge_base[0].answer


def test_prompt_loader_prefers_ai_expert_section_when_document_has_multiple_configs(tmp_path):
    docx_path = tmp_path / "multi.docx"
    _write_docx(
        docx_path,
        [
            "抖音客服",
            "AI客服配置——提示词：",
            "#角色",
            "这是抖音客服配置。",
            "AI客服配置——知识库：",
            "问题：怎么联系",
            "答案：由于平台规则限制，不能自己发。",
            "AI专家搭建",
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

    imported = PromptLoader().load(docx_path)

    assert "创客合伙人" in imported.system_prompt
    assert "抖音客服配置" not in imported.system_prompt
    assert "报价" in imported.handoff_rules.raw_text
    assert imported.knowledge_base[0].question == "怎么合作"
