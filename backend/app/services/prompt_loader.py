from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


@dataclass(frozen=True)
class KnowledgeItem:
    question: str
    answer: str


@dataclass(frozen=True)
class HandoffRules:
    intent_tag: str = "意向客户"
    raw_text: str = ""


@dataclass(frozen=True)
class ImportedPrompt:
    source_path: str
    system_prompt: str
    sales_flow: str
    constraints: str
    handoff_rules: HandoffRules
    knowledge_base: list[KnowledgeItem] = field(default_factory=list)

    def knowledge_text(self) -> str:
        return "\n".join(f"问题：{item.question}\n答案：{item.answer}" for item in self.knowledge_base)


class PromptLoader:
    def load(self, path: str | Path) -> ImportedPrompt:
        docx_path = Path(path)
        paragraphs = self._read_docx_text(docx_path)
        return self._parse(docx_path, paragraphs)

    @staticmethod
    def _read_docx_text(path: Path) -> list[str]:
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with ZipFile(path) as docx:
            xml = docx.read("word/document.xml")
        root = ET.fromstring(xml)
        paragraphs: list[str] = []
        for para in root.findall(".//w:p", ns):
            text = "".join(node.text or "" for node in para.findall(".//w:t", ns)).strip()
            if text:
                paragraphs.append(text)
        return paragraphs

    def _parse(self, path: Path, paragraphs: list[str]) -> ImportedPrompt:
        paragraphs = self._select_relevant_section(paragraphs)
        current = ""
        sections: dict[str, list[str]] = {
            "system_prompt": [],
            "sales_flow": [],
            "constraints": [],
            "handoff_rules": [],
            "knowledge": [],
        }
        in_knowledge = False

        for line in paragraphs:
            if "知识库" in line:
                in_knowledge = True
                current = "knowledge"
                continue
            if in_knowledge:
                sections["knowledge"].append(line)
                continue
            if line.startswith("#角色") or "角色设定" in line:
                current = "system_prompt"
                continue
            if line.startswith("#销售流程") or line.startswith("#对话流程"):
                current = "sales_flow"
                continue
            if line.startswith("#限制条件"):
                current = "constraints"
                continue
            if line.startswith("#提醒人工"):
                current = "handoff_rules"
                continue
            if line.startswith("#"):
                current = ""
                continue
            if current:
                sections[current].append(line)

        return ImportedPrompt(
            source_path=str(path),
            system_prompt="\n".join(sections["system_prompt"]),
            sales_flow="\n".join(sections["sales_flow"]),
            constraints="\n".join(sections["constraints"]),
            handoff_rules=HandoffRules(intent_tag="意向客户", raw_text="\n".join(sections["handoff_rules"])),
            knowledge_base=self._parse_knowledge(sections["knowledge"]),
        )

    @staticmethod
    def _select_relevant_section(paragraphs: list[str]) -> list[str]:
        expert_markers = [
            index
            for index, line in enumerate(paragraphs)
            if "AI专家搭建" in line and "提示词" in line
        ]
        if not expert_markers:
            return paragraphs
        start = expert_markers[-1]
        return paragraphs[start:]

    @staticmethod
    def _parse_knowledge(lines: list[str]) -> list[KnowledgeItem]:
        items: list[KnowledgeItem] = []
        question = ""
        for line in lines:
            if line.startswith("问题："):
                if question:
                    items.append(KnowledgeItem(question=question, answer=""))
                question = line.removeprefix("问题：").strip()
            elif line.startswith("答案：") and question:
                items.append(KnowledgeItem(question=question, answer=line.removeprefix("答案：").strip()))
                question = ""
        if question:
            items.append(KnowledgeItem(question=question, answer=""))
        return items
