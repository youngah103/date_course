import streamlit as st
import google.generativeai as genai
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import json
import time
import urllib.parse

# API 키 검증
if not st.secrets["GEMINI_API_KEY"]:
    st.error("""
    ⚠️ Gemini API 키가 설정되지 않았습니다!
    
    1. Google AI Studio(https://makersuite.google.com/app/apikey)에서 API 키를 발급받으세요.
    2. `.streamlit/secrets.toml` 파일을 열어주세요.
    3. `GEMINI_API_KEY = "여기에_API_키_입력"` 형식으로 API 키를 입력해주세요.
    4. 앱을 다시 실행해주세요.
    """)
    st.stop()

if not st.secrets.get("OPENWEATHER_API_KEY"):
    st.error("""
    ⚠️ OpenWeather API 키가 설정되지 않았습니다!
    
    1. OpenWeather(https://openweathermap.org/api)에서 API 키를 발급받으세요.
    2. `.streamlit/secrets.toml` 파일을 열어주세요.
    3. `OPENWEATHER_API_KEY = "여기에_API_키_입력"` 형식으로 API 키를 입력해주세요.
    4. 앱을 다시 실행해주세요.
    """)
    st.stop()

# Gemini API 설정
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# 활동별 기본 소요 시간 (분)
DEFAULT_DURATIONS = {
    "식사": 90,
    "디너": 90,
    "런치": 60,
    "브런치": 60,
    "카페": 60,
    "술집": 90,
    "바": 90,
    "산책": 45,
    "전시": 90,
    "영화": 120,
    "공연": 120,
    "쇼핑": 90,
    "default": 60
}

# 시스템 프롬프트 수정
context = """
당신은 데이트 코스를 추천해주는 전문 챗봇입니다. 

역할:
- 사용자의 자연어 입력을 분석하여 맞춤형 데이트 코스를 추천합니다.
- 코스의 순서는 사용자의 요청에 따라 자유롭게 구성할 수 있습니다.
- 각 장소는 반드시 아래 형식으로 추천해주세요:

### **[코스 1] 가게명**

🎯 내용: [구체적인 활동 설명 - 예: 이탈리안 파인다이닝, 디저트 카페, 루프탑 바 등]

✨ 추천 이유: [그 장소만의 특별한 특징이나 대표 메뉴의 특징을 구체적으로 설명]

⭐ 별점: [네이버 플레이스 별점과 리뷰 수]

💰 가격대: [1인당 예상 비용]

🔗 네이버 링크: [네이버 플레이스 URL]

### **[코스 2] 가게명**
...

추천 시 주의사항:
1. 모든 장소는 실제 존재하는 곳이어야 합니다.
2. 각 장소의 링크는 반드시 실제 네이버 플레이스 URL을 포함해야 합니다.
3. 별점과 리뷰 수는 네이버 플레이스의 데이터를 정확히 표시합니다.
4. 추천 이유는 그 장소만의 고유한 특징이나 대표 메뉴를 구체적으로 설명해주세요.
5. 가격대는 구체적인 금액으로 표시해주세요.
6. 사용자가 특정 장소나 활동에 대해 피드백을 주면, 해당 부분만 수정하고 나머지는 유지해주세요.
7. 날씨와 관계없이 실내/실외 활동을 적절히 섞어서 추천해주세요.
8. 정보를 찾지 못했다는 등의 부정적인 멘트는 하지 마세요.
9. 모든 정보는 실제로 존재하는 정확한 정보여야 합니다.
10. 별점이나 리뷰에 대한 부가 설명은 하지 마세요.
"""

def get_weather_info(date_str, time_str):
    """특정 날짜와 시간의 날씨 정보를 가져옵니다."""
    try:
        # 서울의 위도/경도 (기본값)
        lat = 37.5665
        lon = 126.9780
        
        # API 키
        api_key = st.secrets["OPENWEATHER_API_KEY"]
        
        # 날짜와 시간 파싱
        target_date = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        current_date = datetime.now()
        
        # 현재부터 5일 이내의 날씨만 조회 가능
        if (target_date - current_date).days > 5:
            return "날짜가 너무 멀어 날씨 정보를 가져올 수 없습니다."
        
        # API 엔드포인트 (5일/3시간 간격 예보)
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=kr"
        
        response = requests.get(url)
        data = response.json()
        
        # 가장 가까운 시간의 날씨 정보 찾기
        closest_forecast = None
        min_time_diff = float('inf')
        
        for item in data['list']:
            forecast_time = datetime.fromtimestamp(item['dt'])
            time_diff = abs((target_date - forecast_time).total_seconds())
            
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                closest_forecast = item
        
        if closest_forecast:
            weather = closest_forecast['weather'][0]['description']
            temp = closest_forecast['main']['temp']
            feels_like = closest_forecast['main']['feels_like']
            humidity = closest_forecast['main']['humidity']
            
            return f"""
날씨: {weather}
기온: {temp:.1f}°C
체감온도: {feels_like:.1f}°C
습도: {humidity}%
"""
        return "날씨 정보를 가져올 수 없습니다."
        
    except Exception as e:
        return f"날씨 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"

def extract_date_time(prompt):
    """사용자 입력에서 날짜와 시간을 추출"""
    # 날짜 패턴
    date_patterns = [
        r'(\d{4}년\s*)?(\d{1,2})월\s*(\d{1,2})일',  # 2024년 3월 15일, 3월 15일
        r'오늘',
        r'내일',
        r'모레',
        r'다음주\s*(월|화|수|목|금|토|일)요일',
        r'이번주\s*(월|화|수|목|금|토|일)요일',
    ]
    
    # 시간 패턴
    time_patterns = [
        r'(\d{1,2})시\s*(\d{1,2})?분?',  # 17시 30분, 17시
        r'(\d{1,2}):(\d{2})',  # 17:30
        r'(\d{1,2})[시:](\d{2})',  # 17시30분, 17:30
        r'오전\s*(\d{1,2})시',  # 오전 11시
        r'오후\s*(\d{1,2})시',  # 오후 5시
    ]
    
    # 기본값 설정
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    time_str = "17:00"
    
    # 날짜 추출
    for pattern in date_patterns:
        if match := re.search(pattern, prompt):
            if "오늘" in match.group():
                date_str = today.strftime("%Y-%m-%d")
            elif "내일" in match.group():
                date_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
            elif "모레" in match.group():
                date_str = (today + timedelta(days=2)).strftime("%Y-%m-%d")
            elif "다음주" in match.group() or "이번주" in match.group():
                weekday_map = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
                target_weekday = weekday_map[match.group(1)]
                current_weekday = today.weekday()
                
                if "다음주" in match.group():
                    days_until = target_weekday - current_weekday + 7
                else:  # 이번주
                    days_until = target_weekday - current_weekday
                    if days_until <= 0:
                        days_until += 7
                
                target_date = today + timedelta(days=days_until)
                date_str = target_date.strftime("%Y-%m-%d")
            else:
                year = match.group(1)[:-1] if match.group(1) else today.year
                month = int(match.group(2))
                day = int(match.group(3))
                date_str = f"{year}-{month:02d}-{day:02d}"
    
    # 시간 추출
    for pattern in time_patterns:
        if match := re.search(pattern, prompt):
            if "오전" in pattern:
                hour = int(match.group(1))
            elif "오후" in pattern:
                hour = int(match.group(1)) + 12
            else:
                hour = int(match.group(1))
                if hour < 12 and "오후" in prompt:
                    hour += 12
            
            minute = int(match.group(2)) if len(match.groups()) > 1 and match.group(2) else 0
            time_str = f"{hour:02d}:{minute:02d}"
    
    return date_str, time_str

def create_timeline(recommendations, start_time):
    """추천 장소들로 시간표 생성"""
    try:
        current_time = datetime.strptime(start_time, "%H:%M")
        timeline = []
        
        # 테이블 헤더 추가
        timeline.append("| 시간 | 활동 | 장소 | 링크 |")
        timeline.append("|------|------|------|------|")
        
        # 코스 정보 추출을 위한 정규식 패턴 수정
        pattern = r'\[코스 \d+\]\s*([^\n]+).*?🎯\s*내용:\s*([^\n]+).*?🔗\s*네이버 링크:\s*([^\n]+)'
        places = re.findall(pattern, recommendations, re.DOTALL)
        
        if not places:
            # 백업 패턴: URL이 없는 경우를 위한 처리
            pattern = r'\[코스 \d+\]\s*([^\n]+).*?🎯\s*내용:\s*([^\n]+)'
            places = re.findall(pattern, recommendations, re.DOTALL)
            places = [(p[0], p[1], "#") for p in places]
        
        for name, activity, link in places:
            name = name.strip()
            activity = activity.strip()
            link = link.strip()
            
            # 활동 시간 계산
            duration = 0
            for key, value in DEFAULT_DURATIONS.items():
                if key in activity.lower():
                    duration = value
                    break
            if duration == 0:
                duration = DEFAULT_DURATIONS["default"]
            
            # 시간표 항목을 테이블 행으로 추가
            timeline.append(f"| {current_time.strftime('%H:%M')} | {activity} | {name} | [🔗]({link}) |")
            
            current_time += timedelta(minutes=duration)
        
        return "\n".join(timeline)
    except Exception as e:
        st.error(f"시간표 생성 중 오류가 발생했습니다: {str(e)}")
        return "시간표를 생성할 수 없습니다."

def create_download_content(last_recommendation_only=False):
    """대화 내용을 텍스트 파일로 변환"""
    if last_recommendation_only and st.session_state.last_recommendations:
        # 마지막 추천 내용만 포함
        content = ["🎈 추천 데이트 코스\n"]
        content.append(st.session_state.last_recommendations)
        
        # 시간표 추가
        start_time = "17:00"  # 기본값
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "user":
                start_time = extract_date_time(msg["content"])[1]
                break
        
        timeline = create_timeline(st.session_state.last_recommendations, start_time)
        content.append("\n📅 예상 시간표")
        content.append(timeline)
        
        return "\n".join(content)
    else:
        # 전체 대화 내용 포함
        content = []
        for msg in st.session_state.messages:
            role = "👤 사용자" if msg["role"] == "user" else "🤖 챗봇"
            content.append(f"{role}:\n{msg['content']}\n")
        return "\n".join(content)

def get_filename():
    """현재 시간을 기반으로 파일명 생성"""
    now = datetime.now()
    return f"date_course_{now.strftime('%Y%m%d_%H%M%S')}.txt"

def get_place_info(url):
    """네이버 플레이스에서 별점과 리뷰 수를 가져옵니다."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # URL이 유효한지 확인
        if not url.startswith('https://place.naver.com/'):
            return None
            
        # 페이지 요청
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 별점 정보 찾기
        rating_element = soup.select_one('span[class*="rating"]')
        review_count_element = soup.select_one('span[class*="review_count"]')
        
        if rating_element and review_count_element:
            rating = rating_element.get_text().strip()
            review_count = review_count_element.get_text().strip()
            return f"{rating}/5.0 ({review_count})"
        
        return None
        
    except Exception as e:
        print(f"Error fetching place info: {str(e)}")
        return None

def update_place_ratings(recommendations):
    """추천된 장소들의 별점 정보를 업데이트합니다."""
    try:
        # 코스 정보 찾기
        courses = re.findall(r'(### \*\*\[코스 \d+\].*?)(?=### \*\*\[코스 \d+\]|$)', recommendations, re.DOTALL)
        
        updated_recommendations = []
        for course in courses:
            # URL 찾기
            url_match = re.search(r'🔗 네이버 링크: (https://place\.naver\.com/[^\n]+)', course)
            if url_match:
                url = url_match.group(1).strip()
                # 별점 정보 가져오기
                rating_info = get_place_info(url)
                
                if rating_info:
                    # 기존 별점 정보 교체
                    course = re.sub(
                        r'⭐ 별점: [^\n]+',
                        f'⭐ 별점: {rating_info}',
                        course
                    )
            
            updated_recommendations.append(course)
            # 네이버 서버 부하 방지를 위한 딜레이
            time.sleep(1)
        
        return ''.join(updated_recommendations)
        
    except Exception as e:
        print(f"Error updating ratings: {str(e)}")
        return recommendations

def search_place(query):
    """네이버 지도 검색 URL을 생성합니다."""
    try:
        # 검색어에서 불필요한 문자 제거
        clean_query = re.sub(r'\([^)]*\)\**', '', query).strip()
        
        # URL 인코딩
        encoded_name = urllib.parse.quote(clean_query)
        
        # 네이버 지도 검색 URL 생성
        search_url = f"https://map.naver.com/p/search/{encoded_name}"
        print(f"Generated search URL for {clean_query}: {search_url}")  # 디버깅용 로그
        return search_url
        
    except Exception as e:
        print(f"Error generating search URL: {str(e)}")
        return None

def update_place_links(recommendations):
    """추천된 장소들의 네이버 지도 검색 링크를 업데이트합니다."""
    try:
        # 코스 정보 찾기
        courses = re.findall(r'(### \*\*\[코스 \d+\].*?)(?=### \*\*\[코스 \d+\]|$)', recommendations, re.DOTALL)
        
        updated_recommendations = []
        for course in courses:
            # 가게명 찾기
            name_match = re.search(r'\[코스 \d+\]\s*([^\n]+)', course)
            if name_match:
                place_name = name_match.group(1).strip()
                print(f"Processing place: {place_name}")  # 디버깅용 로그
                
                # 네이버 지도 검색 링크 생성
                search_url = search_place(place_name)
                
                if search_url:
                    # 기존 링크 정보 교체
                    course = re.sub(
                        r'🔗 네이버 링크:.*?\n',
                        f'🔗 네이버 링크: {search_url}\n',
                        course
                    )
                    print(f"Updated link for {place_name}: {search_url}")  # 디버깅용 로그
            
            updated_recommendations.append(course)
        
        result = ''.join(updated_recommendations)
        return result
        
    except Exception as e:
        print(f"Error updating links: {str(e)}")
        return recommendations

# 페이지 설정
st.set_page_config(
    page_title="데이트 코스 추천 챗봇",
    layout="centered"
)

# 메인 타이틀
st.title("🎈 데이트 코스 추천 챗봇")

# 설명 추가
st.markdown("""
### 아래 내용을 자유롭게 말씀해주세요!

1️⃣ **분위기**
   로맨틱 / 캐주얼 / 활동적 / 조용한 분위기

2️⃣ **시간/날짜**
   오늘 저녁 7시 / 내일 오후 2시 30분 / 주말 점심

3️⃣ **지역**
   특정 지역구 / 역 근처 / 랜드마크 주변

4️⃣ **데이트 스타일**
   맛집 탐방 / 문화생활 / 야외활동 / 실내활동

💡 **피드백도 자유롭게 해주세요!**
- "식당이 너무 비싸요"
- "다른 카페로 바꿔주세요"
- "실내 장소가 좋겠어요"
""")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.last_recommendations = None

# 이전 대화 내용 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 처리
if prompt := st.chat_input("데이트 코스를 추천해드릴게요! 어떤 데이트를 계획하시나요?"):
    # 사용자 메시지 표시
    st.chat_message("user").markdown(prompt)
    # 사용자 메시지 저장
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 날짜와 시간 추출
    date_str, time_str = extract_date_time(prompt)
    
    # 날씨 정보 가져오기
    weather_info = get_weather_info(date_str, time_str)
    
    # Gemini 모델에 전송할 프롬프트 구성
    if st.session_state.last_recommendations and any(keyword in prompt.lower() for keyword in ["바꿔", "교체", "다른", "비싸", "너무", "별로"]):
        # 피드백 처리를 위한 프롬프트
        full_prompt = f"""
{context}

이전 추천 코스:
{st.session_state.last_recommendations}

사용자 피드백: {prompt}

위 피드백을 반영하여 필요한 부분만 수정한 새로운 코스를 추천해주세요.
이전 추천에서 피드백 받지 않은 장소들은 그대로 유지해주세요.
"""
    else:
        # 새로운 코스 추천을 위한 프롬프트
        full_prompt = f"{context}\n\n사용자: {prompt}\n\n위 사용자의 요청에 맞는 데이트 코스를 추천해주세요."
    
    # Gemini 모델 호출
    response = model.generate_content(full_prompt)
    
    # 네이버 지도 링크 업데이트
    response_with_links = update_place_links(response.text)
    
    # 별점 정보 업데이트
    updated_response = update_place_ratings(response_with_links)
    
    # 어시스턴트 응답 표시
    with st.chat_message("assistant"):
        st.markdown(updated_response)
        
        # 시간표 생성 및 표시
        st.markdown("\n### 📅 예상 시간표")
        timeline = create_timeline(updated_response, time_str)
        st.markdown(timeline)
        
        # 시간표 아래에 참고 사항 추가
        st.markdown("""
        > 💡 **참고**
        > - 각 활동의 소요 시간은 예상 시간이며, 실제와 다를 수 있습니다.
        > - 🔗를 클릭하면 네이버 지도로 이동합니다.
        """)
    
    # 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": updated_response + "\n\n### 📅 예상 시간표\n" + timeline})
    st.session_state.last_recommendations = updated_response

# 버튼 컨테이너를 대화 맨 아래에 배치
if st.session_state.messages:  # 대화가 있을 때만 버튼들 표시
    st.divider()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 다시 짜기", use_container_width=True):
            st.session_state.messages = []
            st.session_state.last_recommendations = None
            st.rerun()
    
    with col2:
        if st.session_state.last_recommendations:
            st.download_button(
                label="💾 최종 코스 저장하기",
                data=create_download_content(last_recommendation_only=True),
                file_name=get_filename(),
                mime="text/plain",
                use_container_width=True
            )
        else:
            st.button("💾 최종 코스 저장하기", disabled=True, use_container_width=True)
    
    with col3:
        if st.session_state.last_recommendations:
            if st.button("🔗 코스 공유하기", use_container_width=True):
                st.info("추후 업데이트될 예정입니다! 현재는 데이트 코스를 저장하여 공유해주세요. 😊")
        else:
            st.button("🔗 코스 공유하기", disabled=True, use_container_width=True)
