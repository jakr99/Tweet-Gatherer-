from __future__ import annotations

import html
import zipfile
from pathlib import Path
from typing import Any


def write_workbook(path: str | Path, sheets: dict[str, list[dict[str, Any]]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_names = list(sheets)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", _content_types(len(sheet_names)))
        workbook.writestr("_rels/.rels", _root_relationships())
        workbook.writestr("xl/workbook.xml", _workbook_xml(sheet_names))
        workbook.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships(sheet_names))
        workbook.writestr("xl/styles.xml", _styles_xml())
        for index, rows in enumerate(sheets.values(), start=1):
            workbook.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))


def _content_types(sheet_count: int) -> str:
    sheets = "\n".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
{sheets}
</Types>"""


def _root_relationships() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "\n".join(
        f'<sheet name="{html.escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>
{sheets}
</sheets>
</workbook>"""


def _workbook_relationships(sheet_names: list[str]) -> str:
    rels = "\n".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index, _ in enumerate(sheet_names, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{rels}
</Relationships>"""


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="1"><fill><patternFill patternType="none"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>"""


def _sheet_xml(rows: list[dict[str, Any]]) -> str:
    headers = list(rows[0].keys()) if rows else []
    table = [headers] + [[row.get(header, "") for header in headers] for row in rows]
    xml_rows = "\n".join(
        f'<row r="{row_index}">'
        + "".join(
            _cell_xml(row_index, column_index, value)
            for column_index, value in enumerate(row_values, start=1)
        )
        + "</row>"
        for row_index, row_values in enumerate(table, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>
{xml_rows}
</sheetData>
</worksheet>"""


def _cell_xml(row_index: int, column_index: int, value: Any) -> str:
    reference = f"{_column_letter(column_index)}{row_index}"
    if isinstance(value, int | float):
        return f'<c r="{reference}"><v>{value}</v></c>'
    escaped = html.escape(str(value), quote=False)
    return f'<c r="{reference}" t="inlineStr"><is><t>{escaped}</t></is></c>'


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
