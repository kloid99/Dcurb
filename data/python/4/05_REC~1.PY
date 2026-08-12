# -*- coding: utf-8 -*-
"""
05_recompute_reliability.py
기능4 데이터 신뢰도 레이어 — 신뢰도 산식 확정본(v2) 재계산 스크립트.

변경 이력
- v1(기존 구현): 최신성20 + 직접성20 + 완전성35 + 근거강도25
- 기획서(차별 기능.md): 최신성20 + 매칭률25 + 완전성20 + 직접성20 + 변수일관성15
- v2(확정, 결합안): 최신성20 + 직접성20 + 완전성50 + 근거강도10
  * 최신성·직접성 20%는 기획서대로 유지(데이터셋 기반 상한).
  * 기획서의 '매칭률'은 전처리 로그 부재로 단독 재현 불가 → 이미 완전성에
    '교통수단 확보율'로 포함되어 있으므로 완전성에 통합(20→50%).
  * '근거강도(모델 확신도+SHAP)'는 데이터 품질이 아니라 모델 출력이므로
    25→10%로 낮춰 보조지표로만 유지(저위험 동이 확신도로 신뢰도를
    과대평가받던 왜곡 제거).
  * 기획서의 '변수일관성'은 행정동별 정량화 불가·사실상 상수라 제외.

입력: reliability_master.csv (s_최신성/s_직접성/s_완전성/s_근거 서브점수 포함)
출력: reliability_master_v2.csv (데이터신뢰도/신뢰도등급/정책판단구분 갱신)
권장 실행 환경: Google Colab (Drive 마운트)
"""
from pathlib import Path
import numpy as np
import pandas as pd

# 파일 위치는 환경에 맞게 수정
BASE = Path("/content/drive/MyDrive/logistic/final/python/4")
SRC = BASE / "reliability_master.csv"
DST = BASE / "reliability_master_v2.csv"

# ── 확정 산식 가중치 (합계 1.0) ─────────────────────────────
WEIGHTS = {"s_최신성": 0.20, "s_직접성": 0.20, "s_완전성": 0.50, "s_근거": 0.10}

# 등급 임계 / 교차분류 기준
GRADE_BINS = [(85, "높음"), (70, "보통"), (50, "주의")]  # 그 미만 '낮음'
DLFI_HIGH_RANK = 21   # DLFI 상위 25%(=21개 동)를 'DLFI 높음'으로 간주
REL_HIGH_CUT = 70     # 데이터신뢰도 70 이상을 '신뢰도 높음(보통 이상)'으로 간주


def grade(score: float) -> str:
    for thr, label in GRADE_BINS:
        if score >= thr:
            return label
    return "낮음"


def policy_class(rank: int, rel: float) -> str:
    hi_dlfi, hi_rel = rank <= DLFI_HIGH_RANK, rel >= REL_HIGH_CUT
    if hi_dlfi and hi_rel:
        return "①시범사업우선"
    if hi_dlfi and not hi_rel:
        return "②현장조사우선"
    if not hi_dlfi and hi_rel:
        return "③관찰유지"
    return "④보완조사"


def recompute(src: Path, dst: Path) -> pd.DataFrame:
    df = pd.read_csv(src, dtype={"행정동코드": "string"})

    # 검증 게이트: 구 산식(20/20/35/25)이 기존 값을 재현하는지 확인(데이터 무결성)
    old = (df["s_최신성"] * 0.20 + df["s_직접성"] * 0.20
           + df["s_완전성"] * 0.35 + df["s_근거"] * 0.25).round(2)
    if not (old == df["데이터신뢰도"]).all():
        print("[주의] 구 산식이 기존 데이터신뢰도를 재현하지 못했습니다. 입력 파일을 확인하세요.")

    # 신 산식 적용
    score = sum(df[c] * w for c, w in WEIGHTS.items()).round(2)
    df["데이터신뢰도"] = score
    df["신뢰도등급"] = [grade(s) for s in score]
    df["정책판단구분"] = [policy_class(r, s) for r, s in zip(df["순위"], score)]

    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dst, index=False, encoding="utf-8-sig")
    print(f"[완료] {dst.name}  (행정동 {len(df)}개)")
    print("등급 분포:", df["신뢰도등급"].value_counts().reindex(["높음", "보통", "주의", "낮음"]).to_dict())
    print("정책판단:", df["정책판단구분"].value_counts()
          .reindex(["①시범사업우선", "②현장조사우선", "③관찰유지", "④보완조사"]).to_dict())
    return df


if __name__ == "__main__":
    recompute(SRC, DST)
