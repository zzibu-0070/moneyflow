import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# [1] 페이지 설정
st.set_page_config(layout="wide", page_title="자금 흐름 분석기", page_icon="💰")

# [2] 포트폴리오 프로필 (기존 데이터 유지)
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
# [3] 데이터 엔진: 시가총액 합산 및 지수 산출
# --------------------------------------------------------------------------

@st.cache_data(ttl=86400)
def get_shares_map_robust(tickers):
    mapping = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            s = tk.fast_info.get('shares_outstanding')
            if not s: s = tk.info.get('sharesOutstanding', 0)
            mapping[t] = s if s else 0
        except: mapping[t] = 0
    return mapping

@st.cache_data(ttl=3600)
def get_team_mcap_index_data(period_str):
    blue_tickers = list(set([t for sub in MY_PORTFOLIO["청팀 - 미래섹터"].values() for t in sub]))
    white_tickers = list(set([t for sub in MY_PORTFOLIO["백팀 - 자금의 안전금고"].values() for t in sub]))
    all_tickers = list(set(blue_tickers + white_tickers))
    
    shares = get_shares_map_robust(all_tickers)
    raw_data = yf.download(all_tickers, period=period_str, interval="1d", group_by='ticker')
    
    if raw_data.empty: return pd.DataFrame()

    mcap_results = pd.DataFrame(index=raw_data.index)
    
    # 각 팀별 단순 시총 합계(Sum of Market Cap) 산출
    for team_name, team_tickers in [('Blue Team', blue_tickers), ('White Team', white_tickers)]:
        team_total_mcap = pd.Series(0.0, index=raw_data.index)
        for t in team_tickers:
            try:
                if t in raw_data.columns.levels[0]:
                    # (개별 종목 종가 * 발행주식수)를 팀 합계에 누적
                    team_total_mcap += raw_data[t]['Close'].ffill().fillna(0) * shares.get(t, 0)
            except: continue
        mcap_results[team_name] = team_total_mcap

    # 휴장일(시총 합계가 0인 날) 제거
    final_df = mcap_results[(mcap_results['Blue Team'] > 0) & (mcap_results['White Team'] > 0)].dropna()
    return final_df

# --------------------------------------------------------------------------
# [4] UI 및 그래프 출력
# --------------------------------------------------------------------------

st.title("💰 팀별 자금 흐름 분석기")
st.caption("시작일의 팀별 전체 시가총액 합계를 '100'으로 설정하여 자금의 규모 변화를 추적합니다.")

period_choice = st.selectbox("분석 기간 선택", ["1개월", "3개월", "6개월"])
period_map = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo"}

with st.spinner(f'{period_choice}간의 자금 흐름을 분석 중입니다...'):
    mcap_history = get_team_mcap_index_data(period_map[period_choice])

if not mcap_history.empty:
    # 지수 산출: (현재 시총 합계 / 시작일 시총 합계) * 100
    index_df = (mcap_history / mcap_history.iloc[0]) * 100
    
    # 상단 지표
    b_start_val, b_end_val = mcap_history['Blue Team'].iloc[0], mcap_history['Blue Team'].iloc[-1]
    w_start_val, w_end_val = mcap_history['White Team'].iloc[0], mcap_history['White Team'].iloc[-1]
    
    m1, m2 = st.columns(2)
    m1.metric("청팀 전체 시총 규모", f"${b_end_val/1e12:.2f}T", f"{((b_end_val/b_start_val)-1)*100:+.2f}%")
    m2.metric("백팀 전체 시총 규모", f"${w_end_val/1e12:.2f}T", f"{((w_end_val/w_start_val)-1)*100:+.2f}%")

    # 그래프 생성 (시총 변화 지수)
    fig = go.Figure()
    
    # 민감도 확대 (1.5배 줌인) 로직
    all_vals = pd.concat([index_df['Blue Team'], index_df['White Team']])
    v_diff, v_mid = all_vals.max() - all_vals.min(), (all_vals.max() + all_vals.min()) / 2
    y_range = [v_mid - (v_diff * 0.75), v_mid + (v_diff * 0.75)] if v_diff > 0 else None

    fig.add_trace(go.Scatter(x=index_df.index, y=index_df['Blue Team'], name='청팀 자금지수', line=dict(color='#ef5350', width=4)))
    fig.add_trace(go.Scatter(x=index_df.index, y=index_df['White Team'], name='백팀 자금지수', line=dict(color='#42a5f5', width=4)))

    fig.update_layout(
        title=f"팀별 시가총액 합계 변화 (시작일 {index_df.index[0].strftime('%Y-%m-%d')} = 100)",
        yaxis_title="시총 변화 지수",
        yaxis_range=y_range,
        template="plotly_white",
        hovermode="x unified",
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

    st.info("""
    **💡 지수 산출 방식 안내 (자금 이동 파악용)**
    * **기준점:** 선택한 기간의 첫 거래일의 '팀별 모든 종목 시총 합계'를 **100**으로 고정합니다.
    * **추적:** 매일 변화하는 '팀별 모든 종목 시총 합계'를 기준점과 비교하여 지수화합니다.
    * **의미:** 종목별 단순 수익률 평균이 아니라, **실제 거대 자본(시가총액)이 어느 팀에서 더 크게 팽창하거나 수축하고 있는지**를 보여줍니다.
    """)

else:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")