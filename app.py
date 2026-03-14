import streamlit as st
from PIL import Image
import numpy as np
import google.generativeai as genai
import cv2
import tempfile
import os

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

# --- [2. 통합 가이드 및 데이터] ---
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
        "Premium Home Ad (Image)": {
            "specs": {"Main Asset": (640, 200, -1, -1, 0.2)}, # 200KB
            "checklist": ["📍 규격: 640x200px / JPG / 200KB 이하", "📍 배경: 양 끝 1px 단색 처리 필수", "📍 텍스트: 상하좌우 20px Safe Area 준수"]
        },
        "Premium Home Ad (Native)": {
            "specs": {"Main Asset": (750, 200, -1, -1, 0.15)}, # 150KB
            "checklist": ["📍 규격: 750x200px / PNG(투명 배경) 필수", "📍 텍스트 컬러: #000000 또는 #505050 고정", "📍 강조색: 1종만 사용 가능"]
        },
        "Series Home Ad": {
            "specs": {"Main Asset": (750, 160)},
            "checklist": ["📍 하이라이트(누끼) 또는 썸네일형 규격 확인", "📍 배경색: #FFFFFF, #242424 사용 금지"]
        },
        "Viewer-end Ad": {
            "specs": {"Main Asset": (600, 600)},
            "checklist": ["📍 사방 여백 30px 준수", "📍 배경색 명도(B): 15%~90% 권장"]
        },
        "More Tab Ad": {
            "specs": {"Main Asset": (600, 500)},
            "checklist": ["📍 좌우 여백 30px 준수", "📍 버튼 사용 시 하단 배치 권장"]
        },
        "PC Leader Board": {
            "specs": {"Main Asset": (970, 90)},
            "checklist": ["📍 텍스트 상하 10px / 좌우 40px 여백", "📍 텍스트 최대 2줄 제한"]
        }
    },
    "Video Ads": {
        "Interactive Video": {
            "specs": {
                "Premium Image": (750, 230, -1, -1, 0.15),
                "Default Image": (750, 200, -1, -1, 0.15),
                "Video Thumbnail": (640, 360, -1, -1, 0.15),
                "16:9 Video": (1920, 1080, 1, 60, 1024)
            },
            "checklist": ["📍 비디오: 1920x1080 / 최대 60초 / 사운드 필수", "📍 프리미엄 이미지: PNG(투명 배경) 필수"]
        },
        "Full-screen": {
            "specs": {"9:16 Video": (1080, 1920, 30, -1, 50), "End Card": (1080, 1920)},
            "checklist": ["📍 엔드카드: 사방 50px 여백 준수", "📍 비디오: 최소 30초 이상 및 최대 50MB"]
        },
        "Viewer-top": {
            "specs": {"16:9 Video": (1280, 720, 15, 300, 1024), "Thumbnail": (1280, 720), "Logo": (300, 300)},
            "checklist": ["📍 비디오: 15~300초 / 최대 1GB", "📍 로고: 유색 배경 필수 (투명 불가)"]
        },
        "Viewer-end": {
            "specs": {"1:1 Video": (1080, 1080, 1, 15, 30), "Still Image": (600, 600)},
            "checklist": ["📍 비디오: 1:1 비율 / 15초 권장 / 최대 30MB"]
        }
    },
    "Treasure Hunt": {
        "Global Offerwall": {
            "specs": {"List": (720, 360), "Details": (720, 780), "Logo": (144, 144)},
            "checklist": ["📍 디바이스 목업 사용 절대 금지", "📍 배경색: #FFFFFF, #000000, #242424 사용 금지"]
        }
    }
}

# --- [3. 헬퍼 함수] ---
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

def get_video_info(f):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
        tmp.write(f.getvalue())
        tmp_path = tmp.name
    cap = cv2.VideoCapture(tmp_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frames / fps if fps > 0 else 0
    cap.release()
    os.unlink(tmp_path)
    return w, h, duration

def check_visual_ai(image, product, asset):
    prompt = f"네이버웹툰 광고 검수 전문가로서 {product}의 {asset} 에셋을 분석해줘. 목업 사용, 저작권, 가독성, 안전영역 준수 여부를 알려줘."
    try:
        response = model.generate_content([prompt, image])
        return response.text
    except:
        return "⚠️ AI 분석 지연 중..."

# --- [4. UI 구성] ---
st.set_page_config(page_title="WEBTOON Ad Master Inspector v7.0", layout="wide")

with st.sidebar:
    st.header("📂 Category")
    cat = st.selectbox("대분류", list(GUIDE_DATA.keys()))
    prod = st.selectbox("상품명", list(GUIDE_DATA[cat].keys()))
    product_info = GUIDE_DATA[cat][prod]
    specs = product_info["specs"]
    checklist = product_info["checklist"]

st.title(f"🚀 {prod} Inspector")
files = st.file_uploader("검수할 에셋 업로드", accept_multiple_files=True)

if files:
    for f in files:
        is_video = f.type.startswith('video')
        mb = len(f.getvalue()) / (1024 * 1024)
        if is_video:
            w, h, duration = get_video_info(f)
        else:
            img = Image.open(f)
            w, h = img.size

        # 검수 로직
        matched_asset = None
        error_reasons = []

        with st.expander(f"🔍 {f.name}", expanded=True):
            for a_name, a_val in specs.items():
                temp_errors = []
                # 해상도 체크
                res_ok = (w == a_val[0]) and (a_val[1] == -1 or h == a_val[1] or (a_val[1] == 5000 and h <= 5000))
                if not res_ok:
                    temp_errors.append(f"❌ **해상도:** {w}x{h} (권장: {a_val[0]}x{a_val[1]})")
                
                # 영상 조건 체크
                if is_video and len(a_val) >= 5:
                    if a_val[2] != -1 and duration < a_val[2]:
                        temp_errors.append(f"❌ **시간 부족:** {duration:.1f}초 (최소 {a_val[2]}초)")
                    if a_val[3] != -1 and duration > a_val[3]:
                        temp_errors.append(f"❌ **시간 초과:** {duration:.1f}초 (최대 {a_val[3]}초)")
                    if mb > a_val[4]:
                        temp_errors.append(f"❌ **용량 초과:** {mb:.1f}MB (최대 {a_val[4]}MB)")
                
                if not temp_errors:
                    matched_asset = a_name
                    break
                else:
                    error_reasons = temp_errors # 마지막 매칭 시도된 에러 저장

            # 결과 출력
            c1, c2 = st.columns([1, 1.5])
            with c1:
                if is_video: st.video(f)
                else: st.image(img, use_container_width=True)
            with c2:
                if matched_asset:
                    st.success(f"✅ 검수 통과: {matched_asset}")
                    st.write(f"✔️ {w}x{h}px / {mb:.2f}MB" + (f" / {duration:.1f}s" if is_video else ""))
                    if not is_video:
                        if st.button(f"Analyze {f.name[:10]}", key=f.name):
                            st.info(check_visual_ai(img, prod, matched_asset))
                else:
                    st.error("🚨 규격 미준수")
                    for err in error_reasons: st.write(err)

with st.sidebar:
    st.divider()
    st.subheader(f"📝 {prod} 체크리스트")
    for item in checklist: st.write(item)
