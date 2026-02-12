import os
import subprocess
import streamlit as st
import pandas as pd

# -------------------------
# 기본 설정
# -------------------------
st.set_page_config(page_title="식단 변경", layout="wide")
st.title("식단 변경 프로그램")

BASE_FILE = "base_menu.csv"
CHANGES_FILE = "changes.csv"
MENU_FILE = "menu_options.txt"
MAKE_SCRIPT = "make_message.py"

# -------------------------
# CSV 인코딩 자동 로더
# -------------------------
def read_csv_auto(path: str) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path, encoding="cp949", errors="replace")

def safe_str(x) -> str:
    return "" if pd.isna(x) else str(x)

# -------------------------
# 메뉴 목록 로드(menu_options.txt)
# -------------------------
def load_menu_options() -> list[str]:
    # 첫 칸은 '변경 없음' (빈 문자열)
    if os.path.exists(MENU_FILE):
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            items = [line.strip() for line in f.readlines() if line.strip()]
        return [""] + items
    return [""]  # 최소 안전장치

CHANGE_OPTIONS = load_menu_options()

# -------------------------
# base_menu.csv 로드
# -------------------------
if not os.path.exists(BASE_FILE):
    st.error(f"필수 파일이 없습니다: {BASE_FILE}")
    st.stop()

base = read_csv_auto(BASE_FILE)

need_cols = {"date", "base_menu"}
if not need_cols.issubset(set(base.columns)):
    st.error(f"{BASE_FILE}에 필요한 컬럼이 없습니다: {need_cols}")
    st.stop()

base["date"] = pd.to_datetime(base["date"], errors="coerce")
base = base.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
base["date_str"] = base["date"].dt.strftime("%Y-%m-%d")
base["mmdd"] = base["date"].dt.strftime("%m/%d")

# -------------------------
# 기존 changes.csv 로드(선택값 복원)
# -------------------------
prev = {}
if os.path.exists(CHANGES_FILE):
    try:
        ch = read_csv_auto(CHANGES_FILE)
        if "date" in ch.columns and "new_menu" in ch.columns:
            for _, r in ch.iterrows():
                d = safe_str(r["date"]).strip()
                m = safe_str(r["new_menu"]).strip()
                if d and m:
                    prev[d] = m
    except Exception:
        prev = {}

# -------------------------
# 안내/옵션 UI
# -------------------------
with st.expander("사용 방법", expanded=True):
    st.write(
        "1) 변경할 날짜만 오른쪽 드롭다운에서 메뉴를 선택합니다.\n"
        "2) 아래 ‘변경 요약’을 확인한 뒤 [저장] 또는 [저장+문자/PDF 생성]을 누릅니다.\n"
        "3) 메뉴 목록은 menu_options.txt를 수정하면 됩니다.\n"
        "4) [저장+문자/PDF 생성]은 make_message.py를 자동 실행합니다."
    )

cA, cB, cC = st.columns([1, 1, 2])
with cA:
    show_all = st.checkbox("전체 날짜 표시", value=True)
with cB:
    only_changed_view = st.checkbox("변경된 항목만 보기", value=False)
with cC:
    st.caption("※ ‘변경된 항목만 보기’는 저장 후/기존값 확인용입니다.")

# 변경된 항목만 보기 (기존 changes 기준)
if only_changed_view and prev:
    base_view = base[base["date_str"].isin(set(prev.keys()))].copy()
else:
    base_view = base.copy()

if not show_all:
    first_month = base_view["date"].dt.to_period("M").min()
    base_view = base_view[base_view["date"].dt.to_period("M") == first_month].copy()

base_view = base_view.reset_index(drop=True)

# -------------------------
# 선택 UI
# -------------------------
st.subheader("선택")

selections = []  # (date_str, base_menu, new_menu)

for i, row in base_view.iterrows():
    d_str = row["date_str"]
    mmdd = row["mmdd"]
    base_menu = safe_str(row["base_menu"]).strip()

    # 이전 선택값 반영
    default_idx = 0
    if d_str in prev and prev[d_str] in CHANGE_OPTIONS:
        default_idx = CHANGE_OPTIONS.index(prev[d_str])

    col1, col2, col3 = st.columns([1.0, 2.6, 2.6])
    with col1:
        st.write(mmdd)
    with col2:
        st.write(base_menu)
    with col3:
        pick = st.selectbox("변경메뉴", CHANGE_OPTIONS, index=default_idx, key=f"pick_{d_str}_{i}")

    selections.append((d_str, base_menu, pick.strip() if pick else ""))

# -------------------------
# 변경 요약(저장 전 최종 확인)
# -------------------------
st.subheader("변경 요약(저장 전 최종 확인)")

preview_rows = []
for d_str, base_menu, new_menu in selections:
    if new_menu:
        preview_rows.append([d_str, base_menu, new_menu])

if preview_rows:
    df_preview = pd.DataFrame(preview_rows, columns=["date", "base_menu", "new_menu"])
    st.success(f"현재 변경 {len(df_preview)}건")
    st.dataframe(df_preview, use_container_width=True)
else:
    st.info("현재 변경 내역이 없습니다. (변경할 날짜만 드롭다운에서 선택하세요)")

# -------------------------
# 저장 함수
# -------------------------
def save_changes(preview_rows: list[list[str]]) -> int:
    df_out = pd.DataFrame(preview_rows, columns=["date", "base_menu", "new_menu"])
    # make_message.py는 date,new_menu만 사용하므로 2개 컬럼만 저장
    df_out[["date", "new_menu"]].to_csv(CHANGES_FILE, index=False, encoding="cp949")
    return len(df_out)

# -------------------------
# 저장/삭제/자동생성 버튼
# -------------------------
btn1, btn2, btn3, btn4 = st.columns([1.2, 1.2, 1.6, 3])

with btn1:
    if st.button("저장: changes.csv 생성", type="primary"):
        n = save_changes(preview_rows)
        st.success(f"저장 완료: {CHANGES_FILE} (변경 {n}건)")

with btn2:
    if st.button("변경내역 전체 삭제", type="secondary"):
        pd.DataFrame([], columns=["date", "new_menu"]).to_csv(CHANGES_FILE, index=False, encoding="cp949")
        st.warning("changes.csv를 비웠습니다. (변경 0건)")
        st.info("브라우저 새로고침(F5)하면 선택값이 초기화됩니다.")

with btn3:
    if st.button("저장 + 문자/PDF 생성", type="primary"):
        n = save_changes(preview_rows)

        if not os.path.exists(MAKE_SCRIPT):
            st.error(f"{MAKE_SCRIPT} 파일이 없습니다. 같은 폴더에 있어야 합니다.")
        else:
            # make_message.py 실행 (현재 폴더 기준)
            try:
                # Windows에서 py 런처 사용
                result = subprocess.run(
                    ["py", f".\\{MAKE_SCRIPT}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                st.success(f"저장 완료: {CHANGES_FILE} (변경 {n}건)")
                st.info("make_message.py 실행 결과(요약):")

                # 결과 출력(너무 길면 일부만)
                out = (result.stdout or "").strip()
                err = (result.stderr or "").strip()

                if out:
                    st.code(out[:4000])
                if err:
                    st.error("에러 출력:")
                    st.code(err[:4000])

                if result.returncode == 0:
                    st.success("✅ message.txt 및 PDF 생성이 완료되었습니다. (폴더에서 확인)")
                else:
                    st.warning("⚠️ 실행은 되었지만 오류가 있습니다. 위 에러 내용을 확인하세요.")

            except Exception as e:
                st.error("실행 중 예외가 발생했습니다.")
                st.code(str(e))

with btn4:
    st.caption(
        f"메뉴 목록 수정: {MENU_FILE}\n"
        f"자동 생성 스크립트: {MAKE_SCRIPT}\n"
        "팁) 메뉴를 추가/삭제하면 새로고침(F5) 시 드롭다운에 반영됩니다."
    )