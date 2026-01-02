import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# SSL 인증서 문제 해결 (Mac 사용자 필수)
ssl._create_default_https_context = ssl._create_unverified_context

# [1] 페이지 설정
st.set_page_config(layout="wide", page_title="자금 흐름 분석기 v2.2", page_icon="💰")

# [2] 포트폴리오 프로필 (변수 정의를 상단에 배치)
MY_PORTFOLIO = {
    "청팀 - 미래섹터": {
        "양자컴퓨터": ["IONQ", "QBTS", "RGTI"],
        "양자보안": ["PANW", "ARQQ"], 
        "양자통신": ["030200.KS", "NOK", "VZ"],
        "장수과학 & 합성생물학": ["NTLA", "RXRX", "TWST", "DNA", "CRSP", "NVO"],
        "우주경제": ["LMT", "NOC", "RKLB"],
        "우주 쓰레기처리": ["NOC", "RKLB", "186A.T"],
        "무선 전력전송": ["QCOM", "POWI", "WATT"],
        "BCI플랫폼": ["MDT", "ABT", "BSX"],
        "AI 저작권 플랫폼": ["ORCL", "AMZN", "MSFT", "GOOG", "ADBE"],
        "반도체 벨류체인": ["ON", "TER", "TSM", "005930.KS", "ASML"],
        "데이터센터 냉각": ["066570.KS", "SHEL", "096770.KS", "CC", "VRT"],
        "데이터센터 송전": ["FCX", "006260.KS", "CLF", "PKX", "298040.KS", "010120.KS", "267260.KS", "ETN"],
        "해저케이블": ["PRYMY", "TEL", "6701.T", "006260.KS"],
        "SMR": ["OKLO", "SMR", "034020.KS", "BWXT", "CCJ"],
        "수소, 암모니아경제": ["BE", "LIN", "APD", "CF", "KBR"],
        "에너지 핀테크": ["ICE", "ENPH", "STEM"],
        "차세대 배터리": ["TSLA", "FLNC", "STEM", "EOSE", "ALB"],
        "디지털 트윈도시": ["NVDA", "035420.KS", "ADSK"],
        "글로벌 인프라": ["ETN", "PWR", "GEV"],
        "지구 생태 복원": ["WM", "RSG", "TTEK"],
        "해양 미세플라스틱": ["XYL", "WM"],
        "해양 온도제어": ["OXY", "FLR", "XOM"],
        "폐플라스틱 리사이클링": ["EMN", "PCT", "LYB"]
    },
    "백팀 - 자금의 안전금고": {
        "전통에너지": ["XOM", "CVX", "SHEL", "SLB", "COP", "TTE"],
        "미래에너지": ["TSLA", "FSLR", "NEE", "ENPH", "BEP"],
        "데이터인프라": ["MSFT", "AMZN", "AVGO", "ANET", "GOOG", "META", "NVDA"],
        "필수소비재": ["PG", "COST", "WMT", "KO", "PEP", "AMZN"],
        "결제시스템": ["V", "MA", "AXP", "PYPL"],
        "명품소비재": ["RACE", "EL", "LVMUY", "HESAY", "CFRUY"],
        "물과 식량": ["AWK", "XYL", "ECL", "PHO", "ADM", "DE", "CTVA", "CF"]
    }
}

# --------------------------------------------------------------------------
# [3] 데이터 엔진: 시총 합산 및 수익률 역산
# --------------------------------------------------------------------------

@st.cache_data(ttl=86400)
def get_shares_and_info(tickers):
    data = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            mcap = tk.info.get('marketCap')
            if not mcap:
                s = tk.fast_info.get('shares_outstanding')
                p = tk.fast_info.get('last_price')
                mcap = s * p if s and p else 0
            data[t] = mcap
        except: data[t] = 0
    return data

@st.cache_data(ttl=3600)
def get_robust_mcap_data(period_str):
    # MY_PORTFOLIO가 함수 내에서 정상적으로 접근되도록 함
    blue_tickers = list(set([t for sub in MY_PORTFOLIO["청팀 - 미래섹터"].values() for t in sub]))
    white_tickers = list(set([t for sub in MY_PORTFOLIO["백팀 - 자금의 안전금고"].values() for t in sub]))
    all_tickers = list(set(blue_tickers + white_tickers))
    
    # 환율 데이터 수집
    fx = yf.download(["USDKRW=X", "USDJPY=X"], period=period_str)['Close']
    
    # 가격 데이터 수집
    raw_data = yf.download(all_tickers, period=period_str)['Close']
    if raw_data.empty: return pd.DataFrame(), {}
    
    current_mcaps = get_shares_and_info(all_tickers)
    mcap_history = pd.DataFrame(index=raw_data.index)
    
    for team_name, team_tickers in [('Blue Team', blue_tickers), ('White Team', white_tickers)]:
        team_sum = pd.Series(0.0, index=raw_data.index)
        for t in team_tickers:
            if t in raw_data.columns:
                series = raw_data[t].ffill()
                current_p = series.iloc[-1]
                if current_p > 0:
                    mcap_usd = current_mcaps.get(t, 0)
                    if t.endswith('.KS'):
                        mcap_usd = mcap_usd / fx['USDKRW=X'].iloc[-1]
                    elif t.endswith('.T'):
                        mcap_usd = mcap_usd / fx['USDJPY=X'].iloc[-1]
                        
                    # 현재 시총에서 과거 주가 비율만큼 역산
                    team_sum += mcap_usd * (series / current_p)
        mcap_history[team_name] = team_sum
        
    return mcap_history.replace(0, pd.NA).dropna(), current_mcaps

# --------------------------------------------------------------------------
# [4] UI 출력 및 그래프
# --------------------------------------------------------------------------

st.title("💰 팀별 자금 규모 및 지수 분석기")
st.caption("백팀(공룡주)과 청팀(중소형 미래주)의 자금 규모 차이를 반영하여 지수화합니다.")

period_choice = st.selectbox("분석 기간 선택", ["1개월", "3개월", "6개월"])
period_map = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo"}

mcap_history, current_mcaps = get_robust_mcap_data(period_map[period_choice])

if not mcap_history.empty:
    # 지수 산출 (시작일 = 100)
    index_df = (mcap_history / mcap_history.iloc[0]) * 100
    
    # 상단 메트릭
    b_val = mcap_history['Blue Team'].iloc[-1]
    w_val = mcap_history['White Team'].iloc[-1]
    
    col1, col2 = st.columns(2)
    col1.metric("청팀(미래) 총 시총 규모", f"${b_val/1e12:.2f}T", f"{index_df['Blue Team'].iloc[-1]-100:+.2f}%")
    col2.metric("백팀(안전) 총 시총 규모", f"${w_val/1e12:.2f}T", f"{index_df['White Team'].iloc[-1]-100:+.2f}%")

    # 그래프
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=index_df.index, y=index_df['Blue Team'], name="청팀 자금지수", line=dict(color='#ef5350', width=3)))
    fig.add_trace(go.Scatter(x=index_df.index, y=index_df['White Team'], name="백팀 자금지수", line=dict(color='#42a5f5', width=3)))
    fig.add_hline(y=100, line_dash="dash", line_color="gray")
    
    fig.update_layout(
        title=f"자금 흐름 지수 (시작일 {index_df.index[0].date()} = 100)",
        yaxis_title="변화 지수",
        hovermode="x unified",
        template="plotly_white",
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)

    # 데이터 검증용 테이블
    with st.expander("🔍 데이터 검증: 팀별 시총 TOP 10 종목"):
        check_df = pd.DataFrame.from_dict(current_mcaps, orient='index', columns=['Market Cap (USD)'])
        check_df['Billion $'] = check_df['Market Cap (USD)'] / 1e9
        st.write("백팀은 조 단위(Trillion) 기업들이 많아 시총 합계가 훨씬 크게 나타나는 것이 정상입니다.")
        st.dataframe(check_df.sort_values(by='Market Cap (USD)', ascending=False).head(20))

else:
    st.error("데이터 로딩 중입니다. 잠시만 기다려주세요.")