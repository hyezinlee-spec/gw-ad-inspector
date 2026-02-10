import streamlit as st
from PIL import Image
import numpy as np
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

# --- [2. 통합 가이드 및 상품별 체크리스트 데이터] ---
GUIDE_DATA = {
    "With Creator Ads": {
        "BEP (Epilogue)": {
            "specs": {"Manuscript": (800, 5000), "Slice": (800, 1280), "Viewer-end": (600, 600)},
            "checklist": ["📍 컷 수: 4~5컷 준수 여부", "📍 원고 높이 최대 5000px 확인", "📍 PSD/Clip Studio 파일 제출 필수"]
        },
        "BES (Episode)": {
            "specs": {"Manuscript": (800, -1), "Slice": (800, 1280), "Thumbnail": (202, 142)},
            "checklist": ["📍 컷 수: 40~60컷 (50컷 권장) 확인", "📍 슬라이스 이미지 높이 1280px 이하", "📍 에피소드 썸네일(202x142) 포함 여부"]
        },
        "BWT (Webtoon)": {
            "specs": {"Manuscript": (800, -1), "Slice": (800, 1280), "Big Banner": (750, 760)},
            "checklist": ["📍 최소 40컷 이상 구성 여부", "📍 인앱/홍보용 에셋 규격(750x760 등) 확인", "📍 레이어 분리된 PSD 제출"]
        }
    },
    "Display Ads": {
        "Splash Ad": {
            "specs": {"Logo": (945, 720), "Bottom Image": (1400, 614)},
            "checklist": ["📍 로고: PNG 투명 배경 필수", "📍 배경색: S+B <= 160 준수", "📍 광고주 로고는 서비스 로고만 사용 가능"]
        },
        "Interactive Video": {
            "specs": {"Premium": (750, 230), "Thumbnail": (640, 360), "Default": (750, 200)},
            "checklist": ["📍 프리미엄 이미지: 오브젝트 컷아웃(누끼) 필수", "📍 텍스트: 상하좌우 150px/20px 여백 확인", "📍 비디오: 16:9 비율 및 최대 60초"]
        },
        "Native Image": {
            "specs": {"Main Asset": (750, 200)},
            "checklist": ["📍 컷아웃/라운딩/서클 형태 규격 확인", "📍 폰트 컬러: #000000 또는 #505050 권장", "📍 텍스트 강조색: 1종만 사용 가능"]
        },
        "Series Home Ad": {
            "specs": {"Main Asset": (750, 160)},
            "checklist": ["📍 하이라이트(누끼) 또는 썸네일형 규격 확인", "📍 배경색: #FFFFFF, #242424 사용 금지", "📍 메인 카피 30px / 서브 26px 고정"]
        },
        "Viewer-end Ad": {
            "specs": {"Main Asset": (600, 600)},
            "checklist": ["📍 사방 여백 30px 준수 (텍스트/버튼)", "📍 배경색 명도(B): 15%~90% 사이 권장", "📍 #FFFFFF, #171717 배경 사용 금지"]
        },
        "More Tab Ad": {
            "specs": {"Main Asset": (600, 500)},
            "checklist": ["📍 좌우 여백 30px 준수", "📍 배경색 명도(B): 15%~90% 사이 권장", "📍 버튼 사용 시 하단 배치 권장"]
        },
        "PC Leader Board": {
            "specs": {"Main Asset": (970, 90)},
            "checklist": ["📍 텍스트 상하 10px / 좌우 40px 여백", "📍 텍스트 최대 2줄 제한", "📍 버튼 높이 35px 고정"]
        }
    },
    "Video Ads": {
        "Full-screen": {
            "specs": {"9:16 Video": (1080, 1920), "End Card": (1080, 1920)},
            "checklist": ["📍 엔드카드: 사방 50px 여백 준수", "📍 비디오: 최소 30초 이상 및 MP4 형식", "📍 주요 장면으로 엔드카드 구성"]
        },
        "Viewer-top": {
            "specs": {"Thumbnail": (1280, 720), "Logo": (300, 300)},
            "checklist": ["📍 광고주 로고: 유색 배경 필수 (투명 PNG 불가)", "📍 로고/썸네일 여백 20px/40px 준수", "📍 광고 카피(28자)/광고주명(19자) 제한"]
        }
    },
    "Treasure Hunt": {
        "Global Offerwall": {
            "specs": {"List": (720, 360), "Details": (720, 780), "Logo": (144, 144)},
            "checklist": ["📍 디바이스 목업 사용 절대 금지", "📍 배경색: #FFFFFF, #000000, #242424 사용 금지", "📍 로고: 좌측 상단 배치 금지"]
        }
    }
}

# --- [3. 검수 로직 함수] ---
def check_bg_safety(img):
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
    prompt = f"""
    너는 네이버웹툰 광고 검수 전문가야. {product}의 {asset} 에셋을 분석하여 아래 양식으로만 답변해.
    각 라인 끝에 스페이스를 두 번 넣어 줄바꿈을 해줘.

    [응답 양식]
    **· 디바이스 목업사용 :** (상태)  
    **· 저작권 및 퀄리티 :** (상태)  
    **· 가독성 및 안전영역 :** (상태)  

    [검수 가이드]
    - 선택된 상품인 {product}의 가이드를 최우선으로 적용해.
    - 여백(Safe Area) 침범 여부와 텍스트 가독성을 중점적으로 봐줘.
    """
    try:
        response = model.generate_content([prompt, image])
        return response.text
    except:
        return "⚠️ AI 사용량 초과로 분석이 지연되고 있습니다. 수동 체크리스트를 확인하세요."

# --- [4. UI 구성] ---
st.set_page_config(page_title="WEBTOON Ad Master Inspector v6.4", layout="wide")

with st.sidebar:
    st.header("📂 Category")
    cat = st.selectbox("대분류", list(GUIDE_DATA.keys()))
    prod = st.selectbox("상품명", list(GUIDE_DATA[cat].keys()))
    product_info = GUIDE_DATA[cat][prod]
    specs = product_info["specs"]
    checklist = product_info["checklist"]

st.title(f"🚀 {prod} Inspector")

files = st.file_uploader("검수할 에셋 업로드 (여러 개 가능)", accept_multiple_files=True)

if files:
    for f in files:
        img = Image.open(f)
        w, h = img.size
        kb = len(f.getvalue()) / 1024
        
        matched_asset = None
        for a_name, a_size in specs.items():
            if w == a_size[0] and (a_size[1] == -1 or h == a_size[1] or (a_size[1] == 5000 and h <= 5000)):
                matched_asset = a_name; break

        with st.expander(f"🔍 {f.name}", expanded=True):
            if matched_asset:
                c1, c2 = st.columns([1, 1.5])
                with c1: st.image(img, use_container_width=True)
                with c2:
                    st.success(f"✅ 규격 확인됨: {matched_asset}")
                    st.write(f"✔️ **사이즈:** {w}x{h}px / **용량:** {kb:.1f}KB")
                    
                    scores = check_bg_safety(img)
                    if scores: st.warning(f"⚠️ **배경색 주의:** S+B 수치({max(scores):.1f})가 160을 초과할 수 있습니다.")
                    
                    if st.button(f"Analyze {f.name[:10]}", key=f.name):
                        with st.spinner("AI 분석 중..."):
                            st.info(check_visual_ai(img, prod, matched_asset))
            else:
                st.error(f"🚨 규격 불일치: {w}x{h}px은 {prod}의 가이드에 없습니다.")

with st.sidebar:
    st.divider()
    st.subheader(f"📝 {prod} 체크리스트")
    for item in checklist:
        st.write(item)