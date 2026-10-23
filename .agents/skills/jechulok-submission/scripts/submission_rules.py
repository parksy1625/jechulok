"""Conservative, offline Korean/English submission-requirement parser.

Deterministic rules, not an LLM. Unknown, conflicting, or non-exact rules
must never authorize edits.
"""
from __future__ import annotations

import math
import re
from typing import Any

MAX_TEXT_CHARS = 5000
_FORMATS = re.compile(r"(?<![A-Za-z0-9])\.?\b(jpe?g|jfif|png|webp|gif|pdf|heic|heif|avif)\b", re.I)
_SIZE = re.compile(r"(?P<before>최대\s*|\bmax(?:imum)?\s*[:=]?\s*)?(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>KiB|MiB|KB|MB|킬로바이트|메가바이트)\s*(?P<after>이하|이내|까지|미만|이상|초과|내외|정도|~)?", re.I)
_PAIR = re.compile(r"(?<!\d)(\d{1,5})\s*[xX×*＊]\s*(\d{1,5})\s*(px|픽셀|pixels?|cm|mm)?", re.I)
_AXIS = re.compile(r"(가로|세로|너비|높이|width|height)\s*[:=]?\s*(\d{1,5})\s*(px|픽셀|pixels?|cm|mm)?", re.I)
_PAGES = re.compile(r"(?P<before>최대\s*|\bmax(?:imum)?\s*[:=]?\s*)?(?P<count>\d{1,5})\s*(?P<unit>페이지|쪽|pages?)\s*(?P<after>이하|이내|까지|미만|이상|초과|정도|내외)?", re.I)
_UNSUPPORTED = [
    (r"\b\d+(?:\.\d+)?\s*(?:dpi|ppi)\b|해상도\s*\d+", "DPI/PPI 해상도는 검증하지 않습니다"),
    (r"흰(?:색)?\s*배경|백색\s*배경|배경색|배경\s*제거", "배경색이나 배경 제거 여부는 검증하지 않습니다"),
    (r"얼굴\s*(?:크기|비율|위치|중심)|정수리|턱\s*끝|상반신|어깨\s*선|여권\s*사진|증명사진\s*규정", "인물 구도 및 신분증·증명사진 요건은 검증하지 않습니다"),
    (r"전자\s*서명|디지털\s*서명|워터마크|OCR|텍스트\s*인식|서명\s*유효", "전자서명·OCR·워터마크 요건은 검증하지 않습니다"),
    (r"\b(?:docx?|xlsx?|pptx?|zip)\b|한글\s*파일|hwp", "오피스·압축파일 형식은 지원하지 않습니다"),
    (r"스캔\s*\d|흑백\s*스캔|파일\s*개수|첨부\s*개수", "스캔 설정·파일 개수 조건은 검증하지 않습니다"),
]


def parse_requirements(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("제출 규정 문장을 입력하세요.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("제출 조건 텍스트는 5,000자 이하로 입력하세요.")
    original = text
    text = re.sub(r"[\u00a0\u200b]", " ", text)
    extracted: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    unsupported: list[str] = []
    fields: dict[str, Any] = {"expected_format": None, "allowed_formats": [], "max_kb": None, "width": None, "height": None, "max_pages": None}
    values: dict[str, list[tuple[int, str]]] = {"max_kb": [], "width": [], "height": [], "max_pages": []}

    def issue(code: str, message: str) -> None:
        if not any(x["code"] == code and x["message"] == message for x in issues):
            issues.append({"code": code, "message": message})

    def put(key: str, value: int, evidence: str) -> None:
        values[key].append((value, evidence))
        extracted.append({"field": key, "value": value, "evidence": evidence})

    formats = []
    for match in _FORMATS.finditer(text):
        fmt = match.group(1).lower()
        fmt = {"jpeg": "jpg", "jfif": "jpg", "heif": "heic"}.get(fmt, fmt)
        if fmt not in formats:
            formats.append(fmt)
        extracted.append({"field": "format", "value": fmt, "evidence": match.group(0)})
    fields["allowed_formats"] = formats
    if len(formats) == 1:
        fields["expected_format"] = formats[0]
    elif len(formats) > 1:
        issue("multiple_formats", "형식이 여러 개 언급되었습니다. 허용 형식인지 변환 전후 형식인지 확인하세요.")
    if any(x not in {"jpg", "png", "webp", "gif", "pdf"} for x in formats):
        issue("unsupported_format", "HEIC/AVIF는 자동 변환하지 않습니다.")

    spans = []
    for m in _PAIR.finditer(text):
        a, b, unit = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
        spans.append(m.span())
        if unit in {"cm", "mm"}:
            issue("physical_dimensions", "cm/mm는 픽셀로 자동 변환하지 않습니다.")
        elif not unit:
            issue("missing_pixel_unit", f"'{m.group(0)}'의 단위가 픽셀인지 확인하세요.")
        else:
            put("width", a, m.group(0))
            put("height", b, m.group(0))
            if re.match(r"\s*(?:이상|이하|미만|초과|정도|내외|가변)", text[m.end():m.end()+9]):
                issue("dimension_relation", "픽셀 크기가 정확한 값인지 상한/하한인지 구분해야 합니다.")
    for m in _AXIS.finditer(text):
        if any(m.start() >= a and m.end() <= b for a,b in spans):
            continue
        unit = (m.group(3) or "").lower()
        if unit in {"cm", "mm"}:
            issue("physical_dimensions", "cm/mm는 픽셀로 자동 변환하지 않습니다.")
        elif not unit:
            issue("missing_pixel_unit", f"'{m.group(0)}'에 픽셀 단위가 없습니다.")
        else:
            axis = m.group(1).lower()
            put("width" if axis in {"가로", "너비", "width"} else "height", int(m.group(2)), m.group(0))
            if re.match(r"\s*(?:이상|이하|미만|초과|정도|내외|가변)", text[m.end():m.end()+9]):
                issue("dimension_relation", "픽셀 크기가 정확한 값인지 확인하세요.")

    for m in _SIZE.finditer(text):
        before = (m.group("before") or "").strip()
        after = (m.group("after") or "").strip()
        raw = float(m.group("value"))
        unit = m.group("unit").lower()
        if not math.isfinite(raw) or raw <= 0:
            issue("invalid_size", "허용 용량은 양수여야 합니다.")
            continue
        if after in {"이상", "초과", "미만", "정도", "내외", "~"}:
            issue("size_operator", f"'{m.group(0)}'는 지원하는 최대 용량 이하 조건과 다릅니다.")
            continue
        if not (before or after in {"이하", "이내", "까지"}):
            issue("size_relation", f"'{m.group(0)}'는 최대 허용 용량인지 명확하지 않습니다.")
            continue
        kb = math.floor(raw * (1024 if unit in {"mb", "mib", "메가바이트"} else 1))
        if kb <= 0 or kb > 51200:
            issue("size_limit", "용량은 1 KiB~50 MiB 사이에서 처리합니다.")
            continue
        put("max_kb", kb, m.group(0))

    for m in _PAGES.finditer(text):
        before = (m.group("before") or "").strip()
        after = (m.group("after") or "").strip()
        count = int(m.group("count"))
        if after in {"이상", "초과", "미만", "정도", "내외"}:
            issue("page_operator", f"'{m.group(0)}'는 최대 페이지 이하 조건과 다릅니다.")
            continue
        if not (before or after in {"이하", "이내", "까지"}):
            issue("page_relation", f"'{m.group(0)}'는 페이지 수 상한인지 명확하지 않습니다.")
            continue
        if count < 1 or count > 5000:
            issue("page_limit", "페이지 제한이 허용 범위를 벗어났습니다.")
            continue
        put("max_pages", count, m.group(0))

    for key, items in values.items():
        different = {v for v, _ in items}
        if len(different) == 1:
            fields[key] = items[0][0]
        elif len(different) > 1:
            issue("conflicting_" + key, f"'{key}'에 서로 다른 값이 있습니다.")
    if fields["width"] and fields["height"] and fields["width"] * fields["height"] > 24_000_000:
        issue("image_limit", "출력 이미지가 2,400만 픽셀을 넘습니다.")
    if fields["max_pages"] is not None and fields["expected_format"] not in {"pdf", None}:
        issue("mixed_rules", "이미지 파일 형식과 PDF 페이지 제한을 같이 적용할 수 없습니다.")
    if (fields["width"] is not None or fields["height"] is not None) and fields["expected_format"] == "pdf":
        issue("mixed_rules", "PDF에 이미지 픽셀 조건을 직접 적용할 수 없습니다.")
    for pattern, description in _UNSUPPORTED:
        if re.search(pattern, text, re.I):
            unsupported.append(description)
    if unsupported:
        issue("nontechnical_conditions", "자동 검증할 수 없는 제출 조건이 있습니다.")

    has_rules = bool(formats or any(fields[k] is not None for k in values))
    status = "needs_review" if issues else "parsed" if has_rules else "no_rules"
    auto = status == "parsed" and fields["expected_format"] == "jpg" and any(fields[k] is not None for k in ("width", "height", "max_kb"))
    return {
        "status": status, "rules": fields, "extracted": extracted, "issues": issues,
        "unsupported_conditions": list(dict.fromkeys(unsupported)), "auto_prepare_image": auto,
        "notes": [
            "KB/MB는 KiB(1,024바이트)/MiB(1,048,576바이트)로 해석합니다.",
            "명시된 기술 조건만 검증하며 기관의 접수 성공을 보장하지 않습니다.",
            "PDF 페이지 선택 범위는 제출 규격과 다르므로 사용자가 직접 지정해야 합니다."
        ],
        "length": len(original),
    }
