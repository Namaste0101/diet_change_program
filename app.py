import os
import datetime
import calendar
import pandas as pd
import streamlit as st

# =========================
# 고정 정보(요청 반영)
# =========================
VENDOR_NAME = "맘스락"
VENDOR_TEL = "031-238-5502, 010-9280-9292"  # 문자에는 넣지 않음(요청)

SENDER_ORG = "동약 협회"
SENDER_NAME = "신형철"
SENDER_TEL = "010-7101-5871"

DATA_DIR = "data"
MENU_FILE = "menu_options.txt"

st.set_page_config(page_title="식단 변경", layout="wide")
st.title("식단 변경 프로그램")

with st.expander("사용 방법", expanded=True):
    st.markdown(
        """
1. **연도/월**을 선택합니다. (월별 기본식단/변경식단 파일을 읽습니다)
2. 선택한 월의 기본식단 파일이 없으면 **템플릿 다운로드 → 작성 → 업로드**로 등록합니다.
3. 왼쪽에서 날짜를 선택하고, 오른쪽에서 변경 메뉴를 선택(또는 직접 입력)합니다.
4. **[변경 저장]**을 누르면 `data/changes_YYYY-MM.csv`가 갱신됩니다.
5. **문자 내용**은 변경된 날짜에 대해 `MM/DD: (기본)AAA → (변경)BBB` 형식으로 표시합니다.
※ (중요) Streamlit Cloud에서는 저장이 영구적이지 않을 수 있으니 CSV/TXT는 다운로드로 보관하는 것을 권장합니다.
        """
    )

# =========================
# 인코딩 안전 CSV 로더
# =========================
def safe_read_csv(path: str) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def ym_str(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"

def base_path(ym: str) -> str:
    return os.path.join(DATA_DIR, f"base_menu_{ym}.csv")

def changes_path(ym: str) -> str:
    return os.path.join(DATA_DIR, f"changes_{ym}.csv")

def month_date_list(year: int, month: int) -> list[str]:
    last_day = calendar.monthrange(year, month)[1]
    return [f"{year:04d}-{month:02d}-{d:02d}" for d in range(1, last_day + 1)]

def make_base_template_df(year: int, month: int) -> pd.DataFrame:
    dates = month_date_list(year, month)
    return pd.DataFrame({"date": dates, "base_menu": [""] * len(dates)})

def load_menu_options() -> list[str]:
    if os.path.exists(MENU_FILE):
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            opts = [line.strip() for line in f.readlines() if line.strip()]
        if opts:
            return opts
    return ["(직접 입력)"]

def read_base_df(path: str) -> pd.DataFrame:
    df = safe_read_csv(path)
    if "date" not in df.columns or "base_menu" not in df.columns:
        raise ValueError("기본식단 파일은 반드시 'date, base_menu' 컬럼이 있어야 합니다.")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    df["base_menu"] = df["base_menu"].fillna("").astype(str)
    return df[["date_str", "base_menu"]].drop_duplicates("date_str", keep="last")

def read_changes_df(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        pd.DataFrame(columns=["date", "new_menu"]).to_csv(path, index=False, encoding="utf-8")
    df = safe_read_csv(path)
    if "date" not in df.columns:
        df["date"] = ""
    if "new_menu" not in df.columns:
        df["new_menu"] = ""
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    df["new_menu"] = df["new_menu"].fillna("").astype(str)
    df = df.sort_values("date").drop_duplicates(subset=["date_str"], keep="last")
    return df[["date_str", "new_menu"]]

def merge_month(base_df: pd.DataFrame, changes_df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    dates = month_date_list(year, month)
    frame = pd.DataFrame({"date_str": dates})
    m = frame.merge(base_df, on="date_str", how="left").merge(changes_df, on="date_str", how="left")
    m["base_menu"] = m["base_menu"].fillna("").astype(str)
    m["new_menu"] = m["new_menu"].fillna("").astype(str)
    m["final_menu"] = m["new_menu"].where(m["new_menu"].str.strip() != "", m["base_menu"])
    m["is_changed"] = m["new_menu"].str.strip() != ""
    m["mmdd"] = pd.to_datetime(m["date_str"]).dt.strftime("%m/%d")
    return m

# =========================
# 문자 생성(요청 반영)
# - 제목: "맘스락 (  )월 변경 식단 입니다"
# - 본문: "MM/DD: (기본)A → (변경)B"
# - 업체 연락처는 문자에 넣지 않음
# =========================
def build_message(month: int, changed_rows: pd.DataFrame) -> str:
    title = f"{VENDOR_NAME} ( {month} )월 변경 식단 입니다"
    lines = [title, ""]

    if changed_rows.empty:
        lines.append("변경 없음")
    else:
        for _, r in changed_rows.iterrows():
            base = str(r["base_menu"]).strip() if str(r["base_menu"]).strip() else "(미기재)"
            newv = str(r["new_menu"]).strip() if str(r["new_menu"]).strip() else "(미기재)"
            lines.append(f"{r['mmdd']}: (기본){base} → (변경){newv}")

    lines.append("")
    lines.append(f"{SENDER_ORG} / {SENDER_NAME} / {SENDER_TEL}")
    return "\n".join(lines)

# =========================
# 월 선택
# =========================
ensure_data_dir()
today = datetime.date.today()

c1, c2 = st.columns([1, 3])
with c1:
    # ✅ 연도 범위 확장 (요청): 2010 ~ 2040
    years = list(range(2010, 2041))
    default_year_index = years.index(today.year) if today.year in years else 0
    year = st.selectbox("연도", years, index=default_year_index)
    month = st.selectbox("월", list(range(1, 13)), index=today.month - 1)

ym = ym_str(year, month)
BASE_FILE = base_path(ym)
CHANGES_FILE = changes_path(ym)

with c2:
    st.caption(f"현재 선택: {ym} | 기본식단: {BASE_FILE} | 변경식단: {CHANGES_FILE}")

# =========================
# 기본식단 파일이 없을 때: 템플릿/업로드 제공
# =========================
if not os.path.exists(BASE_FILE):
    st.warning(f"이 달의 기본식단 파일이 없습니다: {BASE_FILE}")

    template_df = make_base_template_df(year, month)
    st.download_button(
        "기본식단 템플릿 CSV 다운로드(해당 월)",
        data=template_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"base_menu_{ym}.csv",
        mime="text/csv",
    )

    up = st.file_uploader("작성한 base_menu_YYYY-MM.csv 업로드", type=["csv"])
    if up is None:
        st.stop()

    with open(BASE_FILE, "wb") as f:
        f.write(up.getvalue())

    st.success(f"업로드 완료: {BASE_FILE} (이제 화면이 갱신됩니다)")
    st.rerun()

# =========================
# 데이터 로드
# =========================
try:
    base_df = read_base_df(BASE_FILE)
except Exception as e:
    st.error(f"기본식단 파일 읽기 오류: {e}")
    st.stop()

changes_df = read_changes_df(CHANGES_FILE)
merged = merge_month(base_df, changes_df, year, month)

# =========================
# 표시 옵션
# =========================
opt1, opt2 = st.columns([1, 1])
with opt1:
    st.checkbox("전체 날짜 표시", value=True)  # UI 유지용(현재 필터링엔 사용 안 함)
with opt2:
    changed_only = st.checkbox("변경된 항목만 보기", value=False)

view_df = merged.copy()
if changed_only:
    view_df = view_df[view_df["is_changed"]].copy()

# =========================
# UI: 날짜 선택 + 변경 입력
# =========================
left, right = st.columns([2, 3])

with left:
    st.subheader("선택")
    date_options = view_df["date_str"].tolist()
    if not date_options:
        st.warning("표시할 항목이 없습니다. (변경된 항목만 보기를 해제해 보세요)")
        st.stop()

    selected_date = st.selectbox("날짜", date_options, index=0)
    row = merged[merged["date_str"] == selected_date].iloc[0]

    base_label = row["base_menu"].strip() if row["base_menu"].strip() else "(미기재)"
    chg_label = row["new_menu"].strip() if row["new_menu"].strip() else "(없음)"

    st.markdown(f"- 기본 메뉴: **{base_label}**")
    st.markdown(f"- 현재 변경: **{chg_label}**")

with right:
    st.subheader("변경 입력")
    menu_options = load_menu_options()
    default_choice = "(직접 입력)" if "(직접 입력)" in menu_options else menu_options[0]
    choice = st.selectbox("변경 메뉴(목록)", menu_options, index=menu_options.index(default_choice))

    custom = st.text_input("변경 메뉴 직접 입력(선택)", value="")
    if choice != "(직접 입력)" and custom.strip() == "":
        new_menu = choice.strip()
    else:
        new_menu = custom.strip() if custom.strip() else (choice.strip() if choice else "")

    colA, colB, colC = st.columns([1, 1, 2])
    with colA:
        do_save = st.button("변경 저장")
    with colB:
        do_clear = st.button("해당 날짜 변경 삭제")
    with colC:
        st.caption("※ 저장 후 아래에서 변경 요약/문자 생성이 가능합니다.")

    if do_save:
        tmp = changes_df.copy()
        tmp = tmp[tmp["date_str"] != selected_date].copy()
        tmp2 = pd.DataFrame([{"date_str": selected_date, "new_menu": new_menu}])
        tmp = pd.concat([tmp, tmp2], ignore_index=True)

        out = pd.DataFrame({"date": tmp["date_str"], "new_menu": tmp["new_menu"]}).sort_values("date")
        out.to_csv(CHANGES_FILE, index=False, encoding="utf-8")
        st.success(f"저장 완료: {CHANGES_FILE}")
        st.rerun()

    if do_clear:
        tmp = changes_df.copy()
        tmp = tmp[tmp["date_str"] != selected_date].copy()
        out = pd.DataFrame({"date": tmp["date_str"], "new_menu": tmp["new_menu"]}).sort_values("date")
        out.to_csv(CHANGES_FILE, index=False, encoding="utf-8")
        st.success(f"삭제 완료: {selected_date}")
        st.rerun()

# =========================
# 요약/다운로드/문자 생성
# =========================
st.divider()
st.subheader("변경 요약")

changed_rows = merged[merged["is_changed"]].copy()
summary = changed_rows[["mmdd", "base_menu", "new_menu"]].rename(
    columns={"mmdd": "날짜", "base_menu": "기본메뉴", "new_menu": "변경메뉴"}
)

if summary.empty:
    st.info("변경된 항목이 없습니다.")
else:
    st.dataframe(summary, use_container_width=True)

if os.path.exists(CHANGES_FILE):
    with open(CHANGES_FILE, "rb") as f:
        st.download_button(
            "변경 CSV 다운로드",
            data=f,
            file_name=f"changes_{ym}.csv",
            mime="text/csv"
        )

st.subheader("문자 내용(복사/전송용)")
msg = build_message(month, changed_rows)
st.text_area("아래 내용을 복사해서 업체 매니저에게 전송하세요.", msg, height=240)

st.download_button(
    "문자 TXT 다운로드",
    data=msg.encode("utf-8"),
    file_name=f"message_{ym}.txt",
    mime="text/plain"
)

st.caption(f"보내는 사람: {SENDER_ORG} / {SENDER_NAME} / {SENDER_TEL}")