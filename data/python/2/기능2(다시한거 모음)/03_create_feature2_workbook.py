"""기능 2 결과를 무채색 Excel 통합본으로 생성합니다.

실행:
    python 03_create_feature2_workbook.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import xlsxwriter


TYPE_ORDER = [
    "복합위험형",
    "배송수요 과밀형",
    "하역공간 부족형",
    "단속반복형",
    "보행충돌형",
    "교통방해형",
    "안전취약형",
]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"행정동코드": "string"})


def safe_value(value):
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def write_dataframe(
    workbook: xlsxwriter.Workbook,
    worksheet,
    df: pd.DataFrame,
    start_row: int,
    formats: dict,
) -> None:
    for col_index, column in enumerate(df.columns):
        worksheet.write(start_row, col_index, column, formats["header"])

    for row_offset, row in enumerate(df.itertuples(index=False, name=None), 1):
        row_format = formats["row_even"] if row_offset % 2 == 0 else formats["row_odd"]
        for col_index, value in enumerate(row):
            worksheet.write(
                start_row + row_offset,
                col_index,
                safe_value(value),
                row_format,
            )

    end_row = start_row + len(df)
    end_col = max(len(df.columns) - 1, 0)
    worksheet.autofilter(start_row, 0, end_row, end_col)
    worksheet.freeze_panes(start_row + 1, 0)


def set_column_widths(worksheet, df: pd.DataFrame) -> None:
    for index, column in enumerate(df.columns):
        sample = [str(column)] + [
            str(value) for value in df[column].head(82).fillna("").tolist()
        ]
        width = min(max(max(map(len, sample)) * 1.45, 10), 46)
        worksheet.set_column(index, index, width)


def create_workbook(
    master_csv: Path,
    rules_csv: Path,
    output_xlsx: Path,
) -> None:
    master = read_csv(master_csv)
    rules = read_csv(rules_csv)

    distribution = (
        master["기본위험유형"]
        .value_counts()
        .reindex(TYPE_ORDER, fill_value=0)
        .rename_axis("위험유형")
        .reset_index(name="행정동수")
    )
    integration = pd.DataFrame(
        [
            ["final_modelling.csv", "82행", "기능 2 공식 분류 입력"],
            [
                "logistics_view_timeband_v3.csv",
                "492행",
                "물류기업 82동×6시간대 화면",
            ],
            [
                "driver_view_timeband_v3.csv",
                "492행",
                "배송기사 시간대 등급·실측검증",
            ],
            [
                "driver_facing_policy_text.csv",
                "11행",
                "원본 정책의 기사용 안내문구 변환",
            ],
            [
                "DLFI_탄력주정차_82동_대시보드용_v2.csv",
                "82행",
                "기능 1 화면 연결",
            ],
            [
                "탄력주정차_행정동매핑_DLFI조인_v2.csv",
                "55행",
                "기능 1 기존 지정구간 연결",
            ],
        ],
        columns=["파일", "확인 규모", "사용 목적"],
    )
    dictionary = pd.DataFrame(
        [
            ["위험유형", "대시보드에 노출하는 단일 대표 유형"],
            ["기본위험유형", "6개 기본 유형 또는 복합위험형 분류군"],
            ["복합위험여부", "TOP 3 위험점수가 모두 70점 이상인지 여부"],
            ["복합판정근거", "TOP 3 최저점과 70점 임계값 비교"],
            ["지역특성태그", "실제 세대·상가·승하차 근거가 있을 때만 산출"],
            ["주요위험요인1~3", "6개 표준화 위험점수 중 TOP 3"],
            ["주요위험점수1~3", "82개 행정동 내 위험방향 백분위"],
            ["한줄자동해석", "행정동·유형·TOP 3 자동 설명"],
            ["권장정책", "규칙 기반 우선 검토 정책"],
            ["기존KMeans유형_보조", "기존 군집 결과·최종 판정 미사용"],
            ["SHAP_TOP1~3_변수_보조", "원본 RandomForest 설명 근거"],
            ["모델추천정책_원본", "조원 통합본의 정책 추천 결과"],
        ],
        columns=["컬럼", "설명"],
    )

    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(output_xlsx)
    workbook.set_properties(
        {
            "title": "D-Curb Guardian Feature 2 Risk Type Results",
            "subject": "행정동 위험유형 자동 분류",
            "company": "D-Curb Guardian",
        }
    )

    base_font = "Malgun Gothic"
    formats = {
        "title": workbook.add_format(
            {
                "font_name": base_font,
                "font_size": 20,
                "bold": True,
                "font_color": "#202020",
            }
        ),
        "subtitle": workbook.add_format(
            {
                "font_name": base_font,
                "font_size": 10,
                "font_color": "#666666",
            }
        ),
        "section": workbook.add_format(
            {
                "font_name": base_font,
                "font_size": 12,
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#3B3B3B",
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "metric_label": workbook.add_format(
            {
                "font_name": base_font,
                "font_size": 9,
                "font_color": "#666666",
                "bg_color": "#F2F2F2",
                "border": 1,
                "border_color": "#D0D0D0",
                "align": "center",
            }
        ),
        "metric_value": workbook.add_format(
            {
                "font_name": base_font,
                "font_size": 16,
                "bold": True,
                "font_color": "#202020",
                "bg_color": "#FFFFFF",
                "border": 1,
                "border_color": "#D0D0D0",
                "align": "center",
            }
        ),
        "header": workbook.add_format(
            {
                "font_name": base_font,
                "font_size": 9,
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#444444",
                "border": 1,
                "border_color": "#C6C6C6",
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        ),
        "row_odd": workbook.add_format(
            {
                "font_name": base_font,
                "font_size": 9,
                "font_color": "#252525",
                "bg_color": "#FFFFFF",
                "border": 1,
                "border_color": "#E0E0E0",
                "valign": "vcenter",
            }
        ),
        "row_even": workbook.add_format(
            {
                "font_name": base_font,
                "font_size": 9,
                "font_color": "#252525",
                "bg_color": "#F4F4F4",
                "border": 1,
                "border_color": "#E0E0E0",
                "valign": "vcenter",
            }
        ),
        "note": workbook.add_format(
            {
                "font_name": base_font,
                "font_size": 9,
                "font_color": "#555555",
                "bg_color": "#F2F2F2",
                "border": 1,
                "border_color": "#D0D0D0",
                "text_wrap": True,
                "valign": "top",
            }
        ),
    }

    summary = workbook.add_worksheet("Summary")
    summary.hide_gridlines(2)
    summary.set_tab_color("#555555")
    summary.set_column("A:A", 3)
    summary.set_column("B:H", 16)
    summary.set_row(1, 28)
    summary.write("B2", "D-Curb Guardian · Feature 2", formats["title"])
    summary.write(
        "B3",
        "행정동 위험유형 자동 분류 · 6개 기본유형 + 복합위험형",
        formats["subtitle"],
    )

    metrics = [
        ("분류 행정동", len(master)),
        ("복합위험형", int((master["기본위험유형"] == "복합위험형").sum())),
        ("분류 규칙", len(rules)),
        ("지역특성 태그", int((master["지역특성태그"] != "미산출").sum())),
    ]
    for index, (label, value) in enumerate(metrics):
        column = 1 + index * 2
        summary.merge_range(5, column, 5, column + 1, label, formats["metric_label"])
        summary.merge_range(6, column, 7, column + 1, value, formats["metric_value"])

    summary.merge_range("B10:H10", "위험유형 분포", formats["section"])
    write_dataframe(workbook, summary, distribution, 10, formats)
    summary.set_column("B:B", 24)
    summary.set_column("C:C", 12)

    chart = workbook.add_chart({"type": "bar"})
    chart.add_series(
        {
            "name": "행정동 수",
            "categories": ["Summary", 11, 1, 17, 1],
            "values": ["Summary", 11, 2, 17, 2],
            "fill": {"color": "#555555"},
            "border": {"color": "#555555"},
            "data_labels": {"value": True, "font": {"color": "#333333"}},
        }
    )
    chart.set_title({"name": "기본 위험유형별 행정동 수"})
    chart.set_legend({"none": True})
    chart.set_chartarea({"border": {"none": True}, "fill": {"color": "#FFFFFF"}})
    chart.set_plotarea({"border": {"color": "#D0D0D0"}, "fill": {"color": "#FFFFFF"}})
    chart.set_x_axis({"major_gridlines": {"visible": False}, "min": 0})
    chart.set_y_axis({"reverse": True})
    chart.set_style(10)
    summary.insert_chart("E12", chart, {"x_scale": 1.15, "y_scale": 1.12})

    summary.merge_range("B21:H21", "해석 주의사항", formats["section"])
    summary.merge_range(
        "B22:H25",
        "표준화 위험점수는 82개 행정동 내 상대적 백분위이며 예측확률이 아닙니다.\n"
        "TOP 3가 모두 70점 이상이면 복합위험형으로 판정합니다.\n"
        "공동주택·상권·역세권 명칭은 실제 세대·상가·승하차 근거가 연결될 때만 사용합니다.\n"
        "기존 K-Means 결과는 보조 검증용이며 최종 위험유형 판정에 사용하지 않습니다.",
        formats["note"],
    )

    master_sheet = workbook.add_worksheet("Risk_Type_Master")
    master_sheet.hide_gridlines(2)
    master_sheet.set_tab_color("#6B6B6B")
    write_dataframe(workbook, master_sheet, master, 0, formats)
    set_column_widths(master_sheet, master)
    master_sheet.set_row(0, 32)
    for column_name in [
        "하역공간부족위험점수",
        "보행충돌위험점수",
        "안전취약위험점수",
        "단속반복위험점수",
        "교통방해위험점수",
        "배송수요위험점수",
    ]:
        if column_name in master.columns:
            column_index = master.columns.get_loc(column_name)
            master_sheet.conditional_format(
                1,
                column_index,
                len(master),
                column_index,
                {
                    "type": "data_bar",
                    "bar_color": "#777777",
                    "bar_solid": True,
                    "bar_border_color": "#555555",
                },
            )

    rules_sheet = workbook.add_worksheet("Rules")
    rules_sheet.hide_gridlines(2)
    rules_sheet.set_tab_color("#777777")
    write_dataframe(workbook, rules_sheet, rules, 0, formats)
    set_column_widths(rules_sheet, rules)
    rules_sheet.set_row(0, 32)

    dictionary_sheet = workbook.add_worksheet("Data_Dictionary")
    dictionary_sheet.hide_gridlines(2)
    dictionary_sheet.set_tab_color("#888888")
    write_dataframe(workbook, dictionary_sheet, dictionary, 0, formats)
    dictionary_sheet.set_column("A:A", 30)
    dictionary_sheet.set_column("B:B", 68)
    dictionary_sheet.set_row(0, 32)

    integration_sheet = workbook.add_worksheet("Integration_Files")
    integration_sheet.hide_gridlines(2)
    integration_sheet.set_tab_color("#999999")
    write_dataframe(workbook, integration_sheet, integration, 0, formats)
    integration_sheet.set_column("A:A", 46)
    integration_sheet.set_column("B:B", 18)
    integration_sheet.set_column("C:C", 48)
    integration_sheet.set_row(0, 32)

    workbook.close()
    print(f"[완료] {output_xlsx}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--master",
        type=Path,
        default=Path(__file__).resolve().parent / "risk_type_master.csv",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=Path(__file__).resolve().parent / "risk_type_rules.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "Feature2_Risk_Type_Results.xlsx",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    create_workbook(arguments.master, arguments.rules, arguments.output)

