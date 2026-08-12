"""
risk_type_master.csv와 risk_type_rules.csv를 이용해 무채색 Excel 결과 파일을 생성합니다.

권장 실행 환경: Google Colab
입력 파일: risk_type_master.csv, risk_type_rules.csv
출력 파일: Administrative_Dong_Risk_Type_Classification.xlsx
"""

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.styles.table import TableStyleList
from openpyxl.utils import get_column_letter
from openpyxl.writer.theme import theme_xml


BASE_DIR = Path("/content/drive/MyDrive/modeling")
OUTPUT_DIR = BASE_DIR / "risk_type_output"
MASTER_CSV = OUTPUT_DIR / "risk_type_master.csv"
RULES_CSV = OUTPUT_DIR / "risk_type_rules.csv"
OUTPUT_XLSX = OUTPUT_DIR / "Administrative_Dong_Risk_Type_Classification.xlsx"

TYPE_ORDER = [
    "공동주택 배송집중형",
    "상권·교통 혼잡형",
    "역세권 보행충돌형",
    "단속반복형",
    "안전취약형",
    "하역공간 부족형",
]

# 파란색을 포함하지 않는 무채색 팔레트
CHARCOAL = "262626"
DARK_GRAY = "595959"
MID_GRAY = "BFBFBF"
LIGHT_GRAY = "E7E6E6"
VERY_LIGHT_GRAY = "F2F2F2"
WHITE = "FFFFFF"
TEXT = "262626"

THIN_GRAY = Side(style="thin", color="D9D9D9")


def mount_google_drive() -> None:
    try:
        from google.colab import drive

        drive.mount("/content/drive", force_remount=False)
    except ImportError:
        pass


def read_csv_auto(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding, dtype={"행정동코드": "string"})
        except UnicodeDecodeError:
            continue
    raise ValueError(f"CSV 인코딩을 확인할 수 없습니다: {path}")


def set_neutral_theme(workbook: Workbook) -> None:
    """Excel 기본 테마와 내부 색상표까지 무채색으로 교체합니다."""
    neutral_theme = theme_xml
    replacements = {
        "1F497D": CHARCOAL,
        "EEECE1": LIGHT_GRAY,
        "4F81BD": DARK_GRAY,
        "C0504D": "7F7F7F",
        "9BBB59": "A6A6A6",
        "8064A2": MID_GRAY,
        "4BACC6": "D9D9D9",
        "F79646": VERY_LIGHT_GRAY,
        "0000FF": DARK_GRAY,
        "800080": "7F7F7F",
    }
    for before, after in replacements.items():
        neutral_theme = neutral_theme.replace(before, after).replace(
            before.lower(), after.lower()
        )
    workbook.loaded_theme = neutral_theme.encode("utf-8")

    # openpyxl이 자동으로 저장하는 64색 기본 팔레트에도 파랑·초록·빨강이
    # 포함되므로, 실제 사용 여부와 관계없이 전체를 무채색으로 교체합니다.
    grayscale_palette = (
        "00000000",
        "00FFFFFF",
        "00262626",
        "00404040",
        "00595959",
        "007F7F7F",
        "00A6A6A6",
        "00BFBFBF",
        "00D9D9D9",
        "00E7E6E6",
        "00F2F2F2",
    )
    workbook._colors = tuple(
        grayscale_palette[index % len(grayscale_palette)] for index in range(64)
    )
    workbook._table_styles = TableStyleList(
        defaultTableStyle="TableStyleLight1",
        defaultPivotStyle="PivotStyleLight1",
    )


def apply_header(cell) -> None:
    cell.fill = PatternFill("solid", fgColor=CHARCOAL)
    cell.font = Font(name="맑은 고딕", bold=True, color=WHITE)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = Border(bottom=THIN_GRAY)


def apply_banded_rows(worksheet, min_row: int, max_row: int, max_col: int) -> None:
    """표 객체를 사용하지 않고 흰색·연회색 행만 직접 적용합니다."""
    for row in range(min_row, max_row + 1):
        fill_color = WHITE if row % 2 == 0 else VERY_LIGHT_GRAY
        for column in range(1, max_col + 1):
            cell = worksheet.cell(row=row, column=column)
            cell.fill = PatternFill("solid", fgColor=fill_color)
            cell.font = Font(name="맑은 고딕", color=TEXT)
            cell.border = Border(bottom=THIN_GRAY)
            cell.alignment = Alignment(vertical="center")


def write_dataframe(worksheet, dataframe: pd.DataFrame) -> None:
    for column_index, column_name in enumerate(dataframe.columns, start=1):
        worksheet.cell(row=1, column=column_index, value=column_name)
        apply_header(worksheet.cell(row=1, column=column_index))

    for row_index, values in enumerate(dataframe.itertuples(index=False, name=None), start=2):
        for column_index, value in enumerate(values, start=1):
            if pd.isna(value):
                value = None
            worksheet.cell(row=row_index, column=column_index, value=value)

    apply_banded_rows(
        worksheet,
        min_row=2,
        max_row=len(dataframe) + 1,
        max_col=len(dataframe.columns),
    )


def set_column_widths(worksheet, widths: dict[str, float]) -> None:
    for column, width in widths.items():
        worksheet.column_dimensions[column].width = width


def create_summary_sheet(workbook: Workbook, master: pd.DataFrame) -> None:
    worksheet = workbook.active
    worksheet.title = "요약"
    worksheet.sheet_view.showGridLines = False
    worksheet.freeze_panes = "A4"

    worksheet.merge_cells("A1:H2")
    title = worksheet["A1"]
    title.value = "행정동 위험유형 자동 분류"
    title.fill = PatternFill("solid", fgColor=CHARCOAL)
    title.font = Font(name="맑은 고딕", size=18, bold=True, color=WHITE)
    title.alignment = Alignment(horizontal="left", vertical="center")
    for row in worksheet["A1:H2"]:
        for cell in row:
            cell.fill = PatternFill("solid", fgColor=CHARCOAL)

    worksheet.merge_cells("A3:H3")
    subtitle = worksheet["A3"]
    subtitle.value = (
        "6개 DLFI 세부지표를 행정동 백분위로 변환해 "
        "주위험·보조위험 유형과 정책 관리방향을 산출"
    )
    subtitle.fill = PatternFill("solid", fgColor=VERY_LIGHT_GRAY)
    subtitle.font = Font(name="맑은 고딕", italic=True, color=DARK_GRAY)
    subtitle.alignment = Alignment(vertical="center", wrap_text=True)

    kpi_headers = {
        "A5": "분석 행정동",
        "B5": "고위험 행정동",
        "D5": "위험유형 수",
        "E5": "입력 지표 수",
    }
    kpi_values = {
        "A6": len(master),
        "B6": int(pd.to_numeric(master["고위험여부"], errors="coerce").fillna(0).sum()),
        "D6": master["주위험유형"].nunique(),
        "E6": 6,
    }
    for address, value in kpi_headers.items():
        cell = worksheet[address]
        cell.value = value
        cell.fill = PatternFill("solid", fgColor=DARK_GRAY)
        cell.font = Font(name="맑은 고딕", bold=True, color=WHITE)
        cell.alignment = Alignment(horizontal="center")
    for address, value in kpi_values.items():
        cell = worksheet[address]
        cell.value = value
        cell.fill = PatternFill("solid", fgColor=WHITE)
        cell.font = Font(name="맑은 고딕", size=14, bold=True, color=TEXT)
        cell.alignment = Alignment(horizontal="center")
        cell.border = Border(left=THIN_GRAY, right=THIN_GRAY, top=THIN_GRAY, bottom=THIN_GRAY)

    summary_headers = ["위험유형", "행정동 수", "평균 DLFI"]
    for column, value in enumerate(summary_headers, start=1):
        cell = worksheet.cell(row=9, column=column, value=value)
        apply_header(cell)

    for row, risk_type in enumerate(TYPE_ORDER, start=10):
        subset = master[master["주위험유형"] == risk_type]
        values = [risk_type, len(subset), round(float(subset["DLFI"].mean()), 2)]
        for column, value in enumerate(values, start=1):
            cell = worksheet.cell(row=row, column=column, value=value)
            cell.fill = PatternFill(
                "solid", fgColor=WHITE if row % 2 == 0 else VERY_LIGHT_GRAY
            )
            cell.font = Font(name="맑은 고딕", color=TEXT)
            cell.border = Border(bottom=THIN_GRAY)
            cell.alignment = Alignment(
                horizontal="right" if column > 1 else "left", vertical="center"
            )

    worksheet.merge_cells("E9:H9")
    principle_header = worksheet["E9"]
    principle_header.value = "산출 원칙"
    apply_header(principle_header)

    worksheet.merge_cells("E10:H15")
    principle = worksheet["E10"]
    principle.value = (
        "① 원점수 범위 차이를 제거하기 위해 행정동 백분위로 변환\n"
        "② 하역여유는 낮을수록 위험하도록 방향을 반전\n"
        "③ 최고 백분위는 주위험유형, 차순위는 보조위험유형으로 지정\n"
        "④ 기존 K-Means 군집은 지역군 설명용 보조정보로 유지\n"
        "⑤ 분류명확도는 예측확률이 아닌 주·보조 위험의 상대적 차이"
    )
    principle.fill = PatternFill("solid", fgColor=WHITE)
    principle.font = Font(name="맑은 고딕", color=TEXT)
    principle.alignment = Alignment(vertical="top", wrap_text=True)
    principle.border = Border(left=THIN_GRAY, right=THIN_GRAY, top=THIN_GRAY, bottom=THIN_GRAY)

    worksheet.merge_cells("A18:H18")
    note = worksheet["A18"]
    note.value = (
        "주의: 본 분류는 대전 행정동 내부 상대평가이며, 위험 원인의 인과관계를 "
        "확정하거나 DLFI 원점수를 변경하지 않습니다."
    )
    note.fill = PatternFill("solid", fgColor=LIGHT_GRAY)
    note.font = Font(name="맑은 고딕", bold=True, color=TEXT)
    note.alignment = Alignment(vertical="center", wrap_text=True)

    worksheet.row_dimensions[1].height = 24
    worksheet.row_dimensions[2].height = 24
    worksheet.row_dimensions[3].height = 32
    worksheet.row_dimensions[10].height = 24
    worksheet.row_dimensions[18].height = 36
    set_column_widths(
        worksheet,
        {"A": 25, "B": 14, "C": 14, "D": 5, "E": 18, "F": 18, "G": 18, "H": 18},
    )


def create_result_sheet(workbook: Workbook, master: pd.DataFrame) -> None:
    worksheet = workbook.create_sheet("위험유형결과")
    worksheet.sheet_view.showGridLines = False
    worksheet.freeze_panes = "D2"
    write_dataframe(worksheet, master)
    worksheet.auto_filter.ref = worksheet.dimensions

    widths = {
        "A": 15,
        "B": 12,
        "C": 12,
        "D": 11,
        "E": 12,
        "F": 11,
        "G": 11,
        "H": 20,
        "I": 23,
        "J": 23,
        "K": 14,
        "L": 14,
        "M": 14,
        "N": 14,
        "O": 14,
        "P": 14,
        "Q": 14,
        "R": 32,
        "S": 16,
        "T": 16,
        "U": 16,
        "V": 16,
        "W": 16,
        "X": 16,
        "Y": 34,
        "Z": 22,
    }
    set_column_widths(worksheet, widths)

    # 분류명확도 열은 연회색만 사용합니다.
    clarity_column = master.columns.get_loc("분류명확도") + 1
    for row in range(2, len(master) + 2):
        cell = worksheet.cell(row=row, column=clarity_column)
        cell.fill = PatternFill("solid", fgColor=LIGHT_GRAY)
        cell.font = Font(name="맑은 고딕", bold=True, color=TEXT)

    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="center", wrap_text=cell.column >= 8)


def create_rules_sheet(workbook: Workbook, rules: pd.DataFrame) -> None:
    worksheet = workbook.create_sheet("분류기준")
    worksheet.sheet_view.showGridLines = False
    worksheet.freeze_panes = "A2"
    write_dataframe(worksheet, rules)
    worksheet.auto_filter.ref = worksheet.dimensions

    set_column_widths(
        worksheet,
        {
            "A": 10,
            "B": 24,
            "C": 18,
            "D": 22,
            "E": 18,
            "F": 40,
            "G": 34,
            "H": 34,
            "I": 42,
        },
    )
    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        worksheet.row_dimensions[row[0].row].height = 58


def create_excel(master_csv: Path, rules_csv: Path, output_xlsx: Path) -> None:
    master = read_csv_auto(master_csv)
    rules = read_csv_auto(rules_csv)

    workbook = Workbook()
    set_neutral_theme(workbook)
    create_summary_sheet(workbook, master)
    create_result_sheet(workbook, master)
    create_rules_sheet(workbook, rules)

    # 활성 시트를 요약으로 고정하고 일반 보기로 저장합니다.
    workbook.active = 0
    for worksheet in workbook.worksheets:
        worksheet.sheet_view.view = "normal"
        worksheet.sheet_view.zoomScale = 90

    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_xlsx)
    print(f"[완료] {output_xlsx}")


if __name__ == "__main__":
    mount_google_drive()
    create_excel(MASTER_CSV, RULES_CSV, OUTPUT_XLSX)
