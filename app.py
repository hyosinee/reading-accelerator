"""읽기 가속기 — 로컬에서 띄워 볼 때 쓰는 Streamlit 껍데기 (선택).

배포는 정적 호스팅(GitHub Pages)으로 한다. 이 파일은 필수가 아니다.
리더 본체는 reader.html 의 HTML/JS 이고, 재생 루프는 전부 브라우저 안에서 돈다
(RSVP 는 200ms 단위라 Streamlit 재실행 모델로는 돌릴 수 없다).

    streamlit run app.py
"""

from __future__ import annotations

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

# Streamlit 기본 장식을 걷어내 화면을 리더에 다 준다.
st.markdown(
    """
    <style>
      #MainMenu, footer, [data-testid="stDecoration"]{display:none}
      header[data-testid="stHeader"]{height:2.4rem;background:transparent}
      .block-container{padding:0.2rem 0.5rem 0.5rem;max-width:960px}
      @media (max-width:640px){ .block-container{padding-inline:0.2rem} }
    </style>
    """,
    unsafe_allow_html=True,
)

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


def build_page(body: str, self_size: bool = False) -> str:
    """reader.html 은 <head> 없는 본문 조각이다. 문서 껍데기를 입혀 iframe 에 넣는다."""
    sizer = SIZER if self_size else ""
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
</head>
<body>
{body}
{sizer}
</body>
</html>"""


if not READER.exists():
    st.error(f"reader.html 을 찾을 수 없습니다 — {READER}")
    st.stop()

# st.iframe 은 1.65 부터. st.components.v1.html 은 폐기 예정이라 폴백으로만 쓴다.
_modern = hasattr(st, "iframe")
_page = build_page(READER.read_text(encoding="utf-8"), self_size=not _modern)

if _modern:
    st.iframe(_page, height="content", width="stretch")
else:
    import streamlit.components.v1 as components

    components.html(_page, height=1180, scrolling=False)
