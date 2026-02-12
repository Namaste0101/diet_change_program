import csv
import io
from datetime import datetime

# PDF 생성용
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

def read_text_csv(path: str) -> io.StringIO:
    data = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            text = data.decode(enc)
            return io.StringIO(text, newline="")
        except UnicodeDecodeError:
            continue
    text = data.decode("cp949", errors="replace")
    return io.StringIO(text, newline="")

def load_base(path: str) -> dict:
    f = read_text_csv(path)
    reader = csv.DictReader(f)
    base = {}
    for row in reader:
        base[row["date"].strip()] = row["base_menu"].strip()
    return base

def load_changes(path: str) -> list[dict]:
    f = read_text_csv(path)
    reader = csv.DictReader(f)
    changes = []
    for row in reader:
        date = (row.get("date") or "").strip()
        new_menu = (row.get("new_menu") or "").strip()
        if date and new_menu:
            changes.append({"date": date, "new_menu": new_menu})
    changes.sort(key=lambda x: x["date"])
    return changes

def format_korean_date(iso_date: str) -> str:
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    return f"{d.month:02d}/{d.day:02d}({['월','화','수','목','금','토','일'][d.weekday()]})"

def build_message(base: dict, changes: list[dict]) -> str:
    lines = []
    lines.append("[맘스락 2월 식단 변경 요청]")
    lines.append("회사명: 동약협회")
    lines.append("")
    lines.append("■ 변경 내역")
    for c in changes:
        date = c["date"]
        new_menu = c["new_menu"]
        base_menu = base.get(date, "(기본메뉴 미등록)")
        lines.append(f"- {format_korean_date(date)}  {base_menu} → {new_menu}")

    lines.append("")
    lines.append("■ (짧은 버전) 날짜-변경메뉴")
    for c in changes:
        lines.append(f"- {format_korean_date(c['date'])}: {c['new_menu']}")
    return "\n".join(lines)

def save_text(path: str, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def make_pdf(pdf_path: str, title: str, company: str, rows: list[list[str]]):
    # 한글 폰트 등록(윈도우 기본 폰트 사용)
    # 맑은고딕이 없으면 굴림으로 시도
    font_candidates = [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\gulim.ttc",
    ]
    font_name = None
    for fp in font_candidates:
        try:
            pdfmetrics.registerFont(TTFont("KFont", fp))
            font_name = "KFont"
            break
        except Exception:
            continue

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()

    # 제목 스타일(한글폰트 적용)
    if font_name:
        styles["Title"].fontName = font_name
        styles["Normal"].fontName = font_name

    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Paragraph(f"회사명: {company}", styles["Normal"]))
    story.append(Spacer(1, 12))

    table = Table(rows, colWidths=[90, 190, 190])
    ts = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("FONTNAME", (0,0), (-1,-1), font_name or "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (0,-1), "CENTER"),
    ])
    table.setStyle(ts)
    story.append(table)
    doc.build(story)

def main():
    base = load_base("base_menu.csv")
    changes = load_changes("changes.csv")

    if not changes:
        print("변경 내역이 없습니다.")
        return

    # 1) 콘솔 출력 + message.txt 저장
    msg = build_message(base, changes)
    print(msg)
    save_text("message.txt", msg)

    # 2) PDF 생성(표)
    header = ["날짜", "기본메뉴", "변경메뉴"]
    body = []
    for c in changes:
        d = c["date"]
        body.append([
            format_korean_date(d),
            base.get(d, "(기본메뉴 미등록)"),
            c["new_menu"]
        ])
    rows = [header] + body

    # 파일명: changes_YYYY-MM.pdf (첫 변경 날짜 기준)
    y, m, _ = changes[0]["date"].split("-")
    pdf_name = f"changes_{y}-{m}.pdf"
    make_pdf(pdf_name, "맘스락 식단 변경 내역", "동약협회", rows)

    print("")
    print(f"✅ 저장 완료: message.txt, {pdf_name}")

if __name__ == "__main__":
    main()