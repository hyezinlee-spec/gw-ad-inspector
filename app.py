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
        # 사용자 리스트에 확인된 모델명을 그대로 사용합니다.
        model = genai.GenerativeModel('gemini-2.5-flash')
    else:
        st.error("❌ API 키 설정이 필요합니다. Streamlit Secrets를 확인하세요.")
        st.stop()
except Exception as e:
    st.error(f"❌ API 연결 오류: {str(e)}")
    st.stop()

# --- [2. 통합 가이드 및 데이터] ---
# specs 구조: (너비, 높이, [영상일 경우 추가: 최소초, 최대초, 최대용량MB])
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
            "checklist": [
                "📍 규격: 640x200px / JPG / 200KB 이하",
                "📍 배경: 양 끝 1px 단색(Solid) 처리 필수 (배경 확장용)",
                "📍 텍스트: 상하좌우 20px Safe Area 준수",
                "📍 버튼: 높이 45px 고정 / 버튼 내 텍스트 좌우 여백 20px"
            ]
        },
        "Premium Home Ad (Native)": {
            "specs": {"Main Asset": (750, 200, -1, -1, 0.15)}, # 150KB
            "checklist": [
                "📍 규격: 750x200px / PNG(투명 배경) 필수 / 150KB 이하",
                "📍 오브젝트: 260x200px 영역 내 배치 / 좌우 50px 여백 필수",
                "📍 텍스트: 컬러 #000000 또는 #505050 고정 사용",
                "📍 강조: 강조색 1종(문장의 60% 이내) 또는 Bold(1줄만) 제한"
            ]
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
        "Interactive Video": {
            "specs": {
                "Premium Image": (750, 230, -1, -1, 0.15),
                "Default Image": (750, 200, -1, -1, 0.15),
                "Video Thumbnail": (640, 360, -1, -1, 0.15),
                "16:9 Video": (1920, 1080, 1, 60, 1024) # 1GB
            },
            "checklist": [
                "📍 비디오: 1920x1080 / 최대 60초 / 사운드 필수(침묵 불가)",
                "📍 프리미엄 이미지: PNG(투명 배경) / 우측 여백 150px 확보",
                "📍 오브젝트: 260x207px 영역 내 (면적 70% 이내)",
                "📍 텍스트: 최소 14pt~최대 30pt / 행간 10px 이상 준수"
            ]
        },
        "Full-screen": {
            "specs": {"9:16 Video": (1080, 1920, 30, -1, 50), "End Card": (1080, 1920)},
            "checklist": ["📍 엔드카드: 사방 50px 여백 준수", "📍 비디오: 최소 30초 이상 및 최대 50MB", "📍 주요 장면으로 엔드카드 구성"]
        },
        "Viewer-top": {
            "specs": {"16:9 Video": (1280, 720, 15, 300, 1024), "Thumbnail": (1280, 720), "Logo": (300, 300)},
            "checklist": ["📍 비디오: 15~300초 / 최대 1GB", "📍 광고주 로고: 유색 배경 필수 (투명 PNG 불가)", "📍 로고/썸네일 여백 20px/40px 준수"]
        },
        "Viewer-end": {
            "specs": {"1:1 Video": (1080, 1080, 1, 15, 30), "Still Image": (600, 600)},
            "checklist": ["📍 비디오: 1:1 비율 / 15초 권장 / 최대 30MB", "📍 배경색 명도(B): 15%~90% 사이 권장"]
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
st.set_page_config(page_title="WEBTOON Ad Master Inspector v6.5", layout="wide")

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
        # 파일 타입 판별 (영상 여부 확인)
        is_video = f.type.startswith('video')
        w, h, duration = 0, 0, 0
        mb = len(f.getvalue()) / (1024 * 1024)
        
        # [수술 부위: 영상/이미지 분기 처리]
        if is_video:
            w, h, duration = get_video_info(f)
        else:
            img = Image.open(f)
            w, h = img.size

        # 공통 매칭 로직
        matched_asset = None
        for a_name, a_val in specs.items():
            # 해상도 기본 체크
            res_ok = (w == a_val[0]) and (a_val[1] == -1 or h == a_val[1] or (len(a_val)>1 and a_val[1] == 5000 and h <= 5000))
            
            # 영상일 경우 추가 조건(초수, 용량) 체크
            if is_video and len(a_val) >= 5:
                dur_ok = (a_val[2] == -1 or duration >= a_val[2]) and (a_val[3] == -1 or duration <= a_val[3])
                size_ok = (mb <= a_val[4])
                if res_ok and dur_ok and size_ok: matched_asset = a_name; break
            elif not is_video and res_ok:
                matched_asset = a_name; break

with st.expander(f"🔍 {f.name}", expanded=True):
    error_reasons = []  # 미준수 사유 저장 리스트
    
    # 해당 상품의 스펙들 중 가장 유사한 에셋을 찾아 비교 (여기서는 첫 번째 스펙 기준 예시)
    # Full-screen의 경우 '9:16 Video' 스펙을 기준으로 체크 로직 강화
    for a_name, a_val in specs.items():
        # 영상/이미지 타입 일치 여부 확인
        asset_is_video = len(a_val) >= 5
        if is_video != asset_is_video: continue

        # 1. 해상도 체크
        res_ok = (w == a_val[0]) and (a_val[1] == -1 or h == a_val[1] or (a_val[1] == 5000 and h <= 5000))
        if not res_ok:
            error_reasons.append(f"❌ **해상도 불일치:** {w}x{h} (권장: {a_val[0]}x{a_val[1] if a_val[1] != -1 else '자유'})")
        
        # 2. 영상 전용 체크 (시간, 용량)
        if is_video:
            # 시간 체크
            dur_min_ok = (a_val[2] == -1 or duration >= a_val[2])
            dur_max_ok = (a_val[3] == -1 or duration <= a_val[3])
            if not dur_min_ok:
                error_reasons.append(f"❌ **시간 부족:** {duration:.1f}초 (최소 {a_val[2]}초 이상 필요)")
            if not dur_max_ok:
                error_reasons.append(f"❌ **시간 초과:** {duration:.1f}초 (최대 {a_val[3]}초 이하 필요)")
            
            # 용량 체크
            size_ok = (mb <= a_val[4])
            if not size_ok:
                error_reasons.append(f"❌ **용량 초과:** {mb:.2f}MB (최대 {a_val[4]}MB 제한)")
        
        # 모든 조건 만족 시 매칭 성공
        if not error_reasons:
            matched_asset = a_name
            break

    # --- [결과 화면 출력] ---
    c1, c2 = st.columns([1, 1.5])
    with c1:
        if is_video: st.video(f)
        else: st.image(img, use_container_width=True)

    with c2:
        if matched_asset:
            st.success(f"✅ **검수 통과: {matched_asset}**")
            info_text = f"✔️ **규격:** {w}x{h}px  |  **용량:** {mb:.2f}MB"
            if is_video: info_text += f"  |  **시간:** {duration:.1f}초"
            st.write(info_text)
            
            # 배경색 분석 (이미지 전용)
            if not is_video:
                scores = check_bg_safety(img)
                if scores: st.warning(f"⚠️ **배경색 주의:** S+B 수치({max(scores):.1f})가 160을 초과합니다.")
        else:
            st.error("🚨 **검수 결과: 규격 미준수**")
            for reason in error_reasons:
                st.write(reason)
            st.info(f"💡 **현재 파일 정보:** {w}x{h}px, {mb:.2f}MB, {duration:.1f}s")

with st.sidebar:
    st.divider()
    st.subheader(f"📝 {prod} 체크리스트")
    for item in checklist:
        st.write(item)
