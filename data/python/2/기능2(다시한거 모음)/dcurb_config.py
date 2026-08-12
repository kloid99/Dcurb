"""D-Curb Guardian 공통 경로 설정.

Colab, 로컬 PC, Streamlit Cloud에서 같은 경로 규칙을 사용합니다.
환경변수 ``DCURB_PROJECT_ROOT``를 지정하면 프로젝트 루트만 교체할 수 있습니다.
"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(
    os.getenv("DCURB_PROJECT_ROOT", "/content/drive/MyDrive/modeling")
)
FINAL_DATA_DIR = PROJECT_ROOT / "logistic" / "final"
FEATURE2_DIR = FINAL_DATA_DIR / "feature2"

FINAL_MODELLING_CSV = FINAL_DATA_DIR / "final_modelling.csv"
REGIONAL_CONTEXT_CSV = FINAL_DATA_DIR / "regional_context.csv"
LOGISTICS_TIMEBAND_CSV = FINAL_DATA_DIR / "logistics_view_timeband_v3.csv"
DRIVER_TIMEBAND_CSV = FINAL_DATA_DIR / "driver_view_timeband_v3.csv"
DRIVER_POLICY_TEXT_CSV = FINAL_DATA_DIR / "driver_facing_policy_text.csv"
FLEXIBLE_PARKING_DASHBOARD_CSV = (
    FINAL_DATA_DIR / "DLFI_탄력주정차_82동_대시보드용_v2.csv"
)
FLEXIBLE_PARKING_JOIN_CSV = (
    FINAL_DATA_DIR / "탄력주정차_행정동매핑_DLFI조인_v2.csv"
)

RISK_TYPE_MASTER_CSV = FEATURE2_DIR / "risk_type_master.csv"
RISK_TYPE_RULES_CSV = FEATURE2_DIR / "risk_type_rules.csv"
