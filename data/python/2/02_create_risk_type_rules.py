"""
위험유형 판단기준과 정책 활용방향을 정의한 risk_type_rules.csv를 생성합니다.

권장 실행 환경: Google Colab
출력 파일: risk_type_output/risk_type_rules.csv
"""

from pathlib import Path

import pandas as pd


BASE_DIR = Path("/content/drive/MyDrive/modeling")
OUTPUT_DIR = BASE_DIR / "risk_type_output"
OUTPUT_CSV = OUTPUT_DIR / "risk_type_rules.csv"


def mount_google_drive() -> None:
    try:
        from google.colab import drive

        drive.mount("/content/drive", force_remount=False)
    except ImportError:
        pass


def create_risk_type_rules(output_csv: Path) -> pd.DataFrame:
    common_rule = (
        "82개 행정동 내 위험방향 백분위를 산출하고 "
        "6개 지표 중 최고 백분위를 주위험유형으로 지정"
    )
    common_relation = "기존 K-Means 군집명은 보조 설명으로 유지"
    common_difference = (
        "DLFI 총점이나 군집번호만 제시하지 않고 "
        "정책 대응이 가능한 원인형 라벨 제공"
    )

    rows = [
        {
            "유형ID": "RT01",
            "위험유형": "공동주택 배송집중형",
            "판단지표": "배송수요",
            "원본컬럼": "배송수요점수_최종",
            "위험방향": "값이 높을수록 위험",
            "산출기준": common_rule,
            "정책활용방향": "배송시간 분산·공동배송 운영 검토",
            "기존군집과의관계": common_relation,
            "차별성": common_difference,
        },
        {
            "유형ID": "RT02",
            "위험유형": "상권·교통 혼잡형",
            "판단지표": "교통방해",
            "원본컬럼": "교통방해점수",
            "위험방향": "값이 높을수록 위험",
            "산출기준": common_rule,
            "정책활용방향": "혼잡시간대 하역 회피·탄력 운영",
            "기존군집과의관계": common_relation,
            "차별성": common_difference,
        },
        {
            "유형ID": "RT03",
            "위험유형": "역세권 보행충돌형",
            "판단지표": "보행충돌",
            "원본컬럼": "보행충돌점수_최종",
            "위험방향": "값이 높을수록 위험",
            "산출기준": common_rule,
            "정책활용방향": "출퇴근·보행 피크시간 하역 제한",
            "기존군집과의관계": common_relation,
            "차별성": common_difference,
        },
        {
            "유형ID": "RT04",
            "위험유형": "단속반복형",
            "판단지표": "단속반복",
            "원본컬럼": "단속반복점수",
            "위험방향": "값이 높을수록 위험",
            "산출기준": common_rule,
            "정책활용방향": "탄력 하역권·단속 운영기준 검토",
            "기존군집과의관계": common_relation,
            "차별성": common_difference,
        },
        {
            "유형ID": "RT05",
            "위험유형": "안전취약형",
            "판단지표": "안전취약",
            "원본컬럼": "안전취약점수",
            "위험방향": "값이 높을수록 위험",
            "산출기준": common_rule,
            "정책활용방향": "등하교·취약계층 이동시간 회피",
            "기존군집과의관계": common_relation,
            "차별성": common_difference,
        },
        {
            "유형ID": "RT06",
            "위험유형": "하역공간 부족형",
            "판단지표": "하역부족",
            "원본컬럼": "하역여유점수",
            "위험방향": "값이 낮을수록 위험",
            "산출기준": common_rule,
            "정책활용방향": "임시 하역면·마이크로 거점 우선 검토",
            "기존군집과의관계": common_relation,
            "차별성": common_difference,
        },
    ]

    rules = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[완료] {output_csv} ({len(rules)}개 유형)")
    return rules


if __name__ == "__main__":
    mount_google_drive()
    create_risk_type_rules(OUTPUT_CSV)
