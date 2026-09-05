"""导入解析器：把用户手写的设定文档（故事圣经/人物卡/故事大纲 markdown）解析为系统数据。

解析约定（与 Brother/*.md 的写作规范对齐）：
- 故事圣经：含「基本信息」表格（书名/题材/风格/一句话简介/目标字数）
- 人物卡：每张卡以「## N. 角色名(身份说明)」开头，字段为顶层「- **字段**:」，子条目为缩进的「  - ...」
- 故事大纲：含「一、小说简介」「二、全书总纲」「三、分卷大纲」，分卷以「### 卷X《卷名》(起-止 章)」开头
"""
import re

_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn_num(s: str) -> int:
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in _CN_NUM:
        return _CN_NUM[s]
    return 0


def parse_bible(text: str) -> dict:
    """故事圣经：提取「基本信息」表字段，其余整篇作为设定铁律原文"""
    fields = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*([^\s|]+?)\s*\|\s*(.+?)\s*\|\s*$", line)
        if not m:
            continue
        key, value = m.group(1).strip(), m.group(2).strip()
        if key == "书名" and not fields.get("title"):
            fields["title"] = re.sub(r"[（(].*?[）)]", "", value).strip() or value
        elif key == "题材" and not fields.get("genre"):
            fields["genre"] = value.split("·")[0].strip()
        elif key == "风格" and not fields.get("style"):
            fields["style"] = value.split(";")[0].strip()
        elif key == "一句话简介" and not fields.get("synopsis"):
            fields["synopsis"] = value
        elif key == "目标字数" and "target_word_count" not in fields:
            m2 = re.search(r"(\d+)\s*万", value)
            if m2:
                fields["target_word_count"] = int(m2.group(1)) * 10000
            else:
                m3 = re.search(r"(\d+)", value)
                if m3:
                    fields["target_word_count"] = int(m3.group(1))
    return {"novel_fields": fields, "bible_text": text}


def parse_outline(text: str) -> dict:
    """故事大纲：拆出 小说简介 / 全书总纲 / 分卷（卷号+卷名+卷大纲）"""
    sections, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            cur = m.group(1).strip()
            sections[cur] = []
            continue
        if cur:
            sections[cur].append(line)

    def sec_text(name: str) -> str:
        for k, v in sections.items():
            if k.startswith(name):  # 标题可能带"(作品页用)"等后缀
                return "\n".join(v).strip()
        return ""

    # 小说简介：去掉引用说明行与分隔线
    syn_lines = [
        l for l in sec_text("一、小说简介").splitlines()
        if not l.strip().startswith(">") and l.strip() != "---"
    ]
    synopsis = "\n".join(syn_lines).strip()
    book_rules = sec_text("二、全书总纲")

    volumes = []
    for m in re.finditer(
        r"^###\s*卷([一二三四五六七八九十\d]+)\s*[《「]?(.*?)[》」]?\s*[（(]?\d+-\d+\s*章",
        text,
        re.M,
    ):
        vol_no = _cn_num(m.group(1))
        if vol_no <= 0:
            continue
        title = m.group(2).strip()
        start = m.end()
        nxt = re.search(r"^###\s*卷", text[start:], re.M)
        end = start + nxt.start() if nxt else len(text)
        outline = text[start:end].strip()
        if not outline:
            continue
        volumes.append({"volume_no": vol_no, "title": title or f"第{vol_no}卷", "outline": outline})
    return {"synopsis": synopsis, "book_rules": book_rules, "volumes": volumes}


def parse_characters(text: str) -> list[dict]:
    """人物卡：按「## N. 角色名(...)」切分；跳过 N=0 的总览章节；
    顶层「- **字段**:」为结构化字段，缩进「  - ...」为子条目并入上一字段；
    整段原文保留为 raw_profile（人设约束）。"""
    chars = []
    for m in re.finditer(r"^##\s*(\d+)\.\s*(.+)$", text, re.M):
        num = int(m.group(1))
        if num == 0:
            continue
        heading = m.group(2).strip()
        start = m.end()
        nxt = re.search(r"^##\s*\d+\.", text[start:], re.M)
        end = start + nxt.start() if nxt else len(text)
        section = text[start:end].strip()
        if not section.strip():
            continue
        name = re.split(r"[（(]", heading)[0].strip()
        if not name:
            continue
        role = "配角"
        if "主角" in heading:
            role = "主角"
        elif "反派" in heading:
            role = "反派"

        fields, cur_key = {}, None
        for raw in section.splitlines():
            if raw.startswith("- "):  # 顶层字段
                fm = re.match(r"^-\s*\*\*(.+?)\*\*\s*[:：]?\s*(.*)$", raw.strip())
                if fm:
                    cur_key = fm.group(1).strip()
                    fields[cur_key] = fm.group(2).strip()
            elif raw.startswith("  - ") and cur_key:  # 缩进子条目，并入当前字段
                fields[cur_key] = fields.get(cur_key, "") + "\n" + raw.strip()[2:].strip()

        card = {}
        for k, ck in (("外貌", "外貌"), ("性格", "性格"), ("目标", "目标"), ("关系", "关系")):
            if fields.get(k):
                card[ck] = fields[k]
        if fields.get("当前状态"):
            card["位置"] = fields["当前状态"]
        chars.append({"name": name, "role": role, "card": card, "raw_profile": section})
    return chars
