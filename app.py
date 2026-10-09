"""읽기 가속기 — Streamlit 껍데기.

리더 본체는 reader.html 의 HTML/JS 다. RSVP 는 200ms 단위로 화면을 바꾸므로
재생 루프를 Streamlit 위젯으로 돌리면(매 상호작용마다 서버 재실행) 쓸 수 없다.
그래서 Streamlit 은 호스팅과 파일 업로드만 맡고, 재생은 전부 브라우저 안에서 돈다.
덕분에 지하철에서 신호가 끊겨도 재생은 멈추지 않는다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
READER = APP_DIR / "reader.html"

st.set_page_config(
    page_title="읽기 가속기",
    page_icon="📖",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Streamlit 기본 장식을 걷어내 폰 화면을 리더에 다 준다.
st.markdown(
    """
    <style>
      #MainMenu, footer, [data-testid="stDecoration"]{display:none}
      header[data-testid="stHeader"]{height:2.4rem;background:transparent}
      .block-container{padding:0.2rem 0.5rem 0.5rem;max-width:960px}
      [data-testid="stSidebarContent"]{padding-top:2rem}
      @media (max-width:640px){ .block-container{padding-inline:0.2rem} }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------- 지문 읽기
def tidy_pdf_text(raw: str) -> str:
    """PDF 는 줄마다 개행이 박혀 나온다. 문장 단위 단락으로 되돌린다."""
    t = raw.replace("\r", "")
    t = re.sub(r"-\n(?=[a-z])", "", t)            # 영문 하이픈 줄바꿈 복원
    t = re.sub(r"[ \t]*\n[ \t]*\n+", "\n\n", t)   # 빈 줄은 단락으로 보존
    # 문장이 끝난 자리의 개행만 단락으로 남기고, 나머지 개행은 공백으로.
    t = re.sub(r"(?<=[.!?。])\n(?!\n)", "\n\n", t)
    t = re.sub(r"(?<=다\.)\n(?!\n)", "\n\n", t)
    t = re.sub(r"(?<![.!?。\n])\n(?!\n)", " ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def read_upload(upload) -> tuple[str, str | None]:
    """업로드 파일에서 본문을 뽑는다. (본문, 오류메시지)"""
    name = (upload.name or "").lower()
    data = upload.getvalue()

    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            return "", "PDF 를 읽으려면 `pip install pypdf` 가 필요합니다."
        import io as _io

        try:
            pages = PdfReader(_io.BytesIO(data)).pages
        except Exception as exc:  # 암호 걸린 PDF, 깨진 파일 등
            return "", f"PDF 를 열지 못했습니다 — {exc}"
        chunks = [(p.extract_text() or "").strip() for p in pages]
        text = tidy_pdf_text("\n\n".join(c for c in chunks if c))
        if not text:
            return "", "본문 텍스트가 없습니다. 스캔 이미지 PDF 는 글자를 뽑을 수 없습니다."
        return text, None

    for enc in ("utf-8", "cp949", "utf-16"):
        try:
            return data.decode(enc).strip(), None
        except UnicodeDecodeError:
            continue
    return "", "글자 인코딩을 알 수 없습니다. UTF-8 로 저장해 다시 올려 주세요."


with st.sidebar:
    st.markdown("### 지문 올리기")
    st.caption("집에서 올려 두고, 이동 중엔 재생만 누르세요.")
    upload = st.file_uploader(
        "txt · md · pdf",
        type=["txt", "md", "markdown", "pdf"],
        label_visibility="collapsed",
    )
    if upload is not None:
        text, err = read_upload(upload)
        if err:
            st.error(err)
        else:
            st.session_state["text"] = text
            st.success(f"{upload.name} — {len(text):,}자")

    if st.session_state.get("text"):
        if st.button("올린 지문 내리기", use_container_width=True):
            st.session_state.pop("text", None)
            st.rerun()

    st.divider()
    st.caption(
        "올린 지문은 리더로 바로 넘어갑니다. 읽던 위치·속도·굵기 설정은 "
        "브라우저에 저장되므로 다음에 열면 그 자리에서 이어집니다. "
        "지문을 올리지 않으면 리더 아래 칸에 직접 붙여넣어도 됩니다."
    )


# ----------------------------------------------------------------- 리더 띄우기
def build_page(body: str, inject: str, self_size: bool = False) -> str:
    """reader.html 은 <head> 없는 본문 조각이다. 문서 껍데기를 입혀 iframe 에 넣는다.

    self_size 는 구버전 폴백(st.components.v1.html)용. st.iframe 은 내용 높이를
    직접 재므로 높이 보고 스크립트가 필요 없다.
    """
    sizer = SIZER if self_size else ""
    payload = json.dumps(inject or "").replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
  :root{{color-scheme:light dark;
        padding-top:env(safe-area-inset-top,0px);
        padding-bottom:env(safe-area-inset-bottom,0px)}}
  body{{margin:0;font:14px system-ui,-apple-system,sans-serif}}
  img{{max-width:100%}}
  [hidden]{{display:none!important}}
</style>
<script>window.__ACCEL_TEXT__ = {payload};</script>
</head>
<body>
{body}
{sizer}
</body>
</html>"""


SIZER = """<script>
// 구버전 폴백용 — iframe 높이를 내용에 맞춰 부모에 알린다.
(function(){
  var last = 0;
  function report(){
    var h = Math.ceil(document.documentElement.scrollHeight);
    if (Math.abs(h - last) < 2) return;
    last = h;
    window.parent.postMessage({type:"streamlit:setFrameHeight", height:h}, "*");
  }
  if (window.ResizeObserver) new ResizeObserver(report).observe(document.documentElement);
  window.addEventListener("load", report);
  [60, 300, 900, 2000].forEach(function(ms){ setTimeout(report, ms); });
})();
</script>"""


if not READER.exists():
    st.error(f"reader.html 을 찾을 수 없습니다 — {READER}")
    st.stop()

# st.iframe 은 1.65 부터. st.components.v1.html 은 폐기 예정이라 폴백으로만 쓴다.
_modern = hasattr(st, "iframe")
_page = build_page(
    READER.read_text(encoding="utf-8"),
    st.session_state.get("text", ""),
    self_size=not _modern,
)

if _modern:
    st.iframe(_page, height="content", width="stretch")
else:
    import streamlit.components.v1 as components

    components.html(_page, height=1180, scrolling=False)
