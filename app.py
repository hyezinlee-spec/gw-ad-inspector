import streamlit as st
from PIL import Image
import numpy as np
import easyocr
import google.generativeai as genai

# --- [1. Google AI API 설정] ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
    else:
        st.error("❌ API 키 설정이 필요합니다. Streamlit Secrets를 확인하세요.")
        st.stop()
except Exception as e:
    st.error(f"❌ API 연결 오류: {str(e)}")
    st.stop()

# --- [2. 통합 가이드 데이터 세팅] ---
GUIDE_DATA = {
    "With Creator Ads": {
        "BEP (Epilogue)": {"Manuscript": (800, 5000), "Slice": (800, 1280), "Viewer-end": (600, 600)},
        "BES (Episode)": {"Manuscript": (800, -1), "Slice": (800, 1280), "Thumbnail": (202, 142)},
        "BWT (Webtoon)": {"Manuscript": (800, -1), "Slice": (800, 1280), "Big Banner": (750, 760)}
    },
    "Display Ads": {
        "Splash Ad": {"Logo": (945, 720), "Bottom Image": (1400, 614)},
        "Interactive Video": {"Premium": (750, 230), "Thumbnail": (640, 360), "Default": (750, 200)},
        "Native Image": {"Main": (750, 200)},
        "Image Banner": {"Main": (640, 200)},
        "Series Home Ad": {"Main": (750, 160)},
        "PC Leader Board": {"Main": (970, 90)}
    },
    "Video Ads": {
        "Full-screen": {"9:16 Video": (1080, 1920), "End Card": (1080, 1920)},
        "Viewer-top": {"Thumbnail": (1280, 720), "Logo": (300, 300)},
        "Viewer-end": {"Still Image": (600, 600)}
    },
    "Treasure Hunt": {
        "Global Offerwall": {"List": (720, 360), "Details": (720, 780), "Logo": (144, 144)}
    }
}

# --- [3. 검수 로직 함수] ---
def check_bg_safety(img):
    """S+B <= 160 및 배경색 규정 검사"""
    img_rgb = img.convert('RGB')
    pixels = np.array(img_rgb)
    samples = [pixels[0,0], pixels[0,-1], pixels[-1,0], pixels[-1,-1]]
    results = []
    for p in samples:
        r, g, b = p / 255.0
        mx, mn = max(r, g, b), min(r, g, b)
        v, s = mx, (mx - mn) / mx if mx != 0 else 0
        if (s*100 + v*100) > 160: results.append(s*100 + v*100)
    return results

def check_visual_ai(image, product, asset):
    # 각 상품별 맞춤 프롬프트 생성
    prompt = f"""
    너는 네이버웹툰 광고 검수 전문가야. {product}의 {asset} 에셋을 분석하여 아래 양식으로만 답변해.
    각 라인 끝에 스페이스를 두 번 넣어 줄바꿈을 해줘.

    [응답 양식]
    **· 디바이스 목업사용 :** (의심됩니다 / 의심되지 않습니다)  
    **· 저작권 및 퀄리티 :** (문제 되지 않습니다 / 확인 필요)  
    **· 가독성 및 안전영역 :** (문제 되지 않습니다 / 수정 권장)  

    [검수 가이드]
    1. Treasure Hunt/Splash: 디바이스 목업 절대 금지.
    2. Video Ads: 로고는 반드시 유색 배경이어야 함.
    3. Safe Area: 텍스트가 사방 여백(30~50px)을 침범하는지 확인.
    """
    try:
        response = model.generate_content([prompt, image])
        return response.text
    except:
        return "⚠️ AI 사용량 초과로 분석이 지연되고 있습니다. 수동 체크리스트를 확인하세요."

# --- [4. UI 구성] ---
st.set_page_config(page_title="WEBTOON Ad Master Inspector", layout="wide")

with st.sidebar:
    st.header("📂 Category")
    cat = st.selectbox("대분류", list(GUIDE_DATA.keys()))
    prod = st.selectbox("상품명", list(GUIDE_DATA[cat].keys()))
    specs = GUIDE_DATA[cat][prod]

st.title(f"🚀 {prod} Inspector")

files = st.file_uploader("검수할 에셋 업로드 (여러 개 가능)", accept_multiple_files=True)

if files:
    for f in files:
        img = Image.open(f)
        w, h = img.size
        kb = len(f.getvalue()) / 1024
        
        # 에셋 타입 자동 매칭
        matched = "미분류 에셋"
        for a_name, a_size in specs.items():
            if w == a_size[0] and (a_size[1] == -1 or h == a_size[1] or (a_size[1] == 5000 and h <= 5000)):
                matched = a_name; break

        with st.expander(f"🔍 {f.name} ({matched})", expanded=True):
            c1, c2 = st.columns([1, 1.5])
            with c1: st.image(img, use_container_width=True)
            with c2:
                st.write(f"✔️ **규격:** {w}x{h}px")
                st.write(f"✔️ **용량:** {kb:.1f}KB")
                
                # 배경색 규정 체크
                scores = check_bg_safety(img)
                if scores: st.warning(f"⚠️ **배경색 주의:** S+B 수치({max(scores):.1f})가 160을 초과합니다.")
                
                if st.button(f"Analyze {f.name[:10]}", key=f.name):
                    with st.spinner("AI 분석 중..."):
                        st.info(check_visual_ai(img, prod, matched))

with st.sidebar:
    st.divider()
    st.subheader("📝 필수 체크리스트")
    st.write("📍 원본 **PSD/Clip Studio** 파일 포함 여부")
    st.write("📍 **#FFFFFF, #000000** 배경 사용 가능 여부 재확인")
    st.write("📍 텍스트 **Safe Area** 준수 여부")