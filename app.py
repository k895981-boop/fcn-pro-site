import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import yfinance as yf
import numpy as np
import streamlit.components.v1 as components
from datetime import datetime, date, timedelta
import io, os, glob as _glob
import warnings
warnings.filterwarnings('ignore')
from PIL import Image, ImageDraw, ImageFont

# ── 找 CJK 字型（系統優先，找不到就下載備援）──
_CJK_FONT_FILE = None
_FONT_CACHE    = '/tmp/_noto_cjk.otf'

_FONT_SEARCH = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf',
    '/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf',
] + _glob.glob('/usr/share/fonts/**/*CJK*.otf', recursive=True) \
  + _glob.glob('/usr/share/fonts/**/*CJK*.ttc', recursive=True) \
  + _glob.glob('/usr/share/fonts/**/*CJK*.ttf', recursive=True) \
  + [_FONT_CACHE]

for _fp in _FONT_SEARCH:
    if os.path.exists(_fp):
        _CJK_FONT_FILE = _fp
        break

# 若系統字型不存在，下載一次備援字型（約 12 MB，存 /tmp）
if not _CJK_FONT_FILE:
    try:
        import urllib.request
        _URL = ('https://raw.githubusercontent.com/notofonts/noto-cjk/main'
                '/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf')
        urllib.request.urlretrieve(_URL, _FONT_CACHE)
        if os.path.exists(_FONT_CACHE):
            _CJK_FONT_FILE = _FONT_CACHE
    except Exception:
        pass

def _pil_font(size):
    if _CJK_FONT_FILE:
        try:
            kw = {'index': 0} if _CJK_FONT_FILE.endswith('.ttc') else {}
            return ImageFont.truetype(_CJK_FONT_FILE, size, **kw)
        except Exception:
            pass
    return ImageFont.load_default()

st.set_page_config(page_title="結構商品全能工作站", layout="wide", page_icon="🏦")

# ==========================================
# 🔐 密碼保護
# ==========================================
def check_password():
    def password_entered():
        if st.session_state["password"] == "0000":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("請輸入系統密碼 (Access Code)", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("請輸入系統密碼 (Access Code)", type="password", on_change=password_entered, key="password")
        st.error("❌ 密碼錯誤 (Incorrect Password)")
        return False
    else:
        return True

if not check_password():
    st.stop()

# 防複製保護
st.markdown("""
<style>
* { -webkit-user-select: none; -moz-user-select: none; -ms-user-select: none; user-select: none; }
</style>
<script>
document.addEventListener('contextmenu', function(e) { e.preventDefault(); });
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && ['c','u','s','a','p'].includes(e.key.toLowerCase())) { e.preventDefault(); }
});
document.addEventListener('dragstart', function(e) { e.preventDefault(); });
</script>
""", unsafe_allow_html=True)

st.title("🏦 結構商品全能工作站")
st.markdown("整合回測分析・產品追蹤・配息管理")
st.divider()

# ==========================================
# 側邊欄
# ==========================================
st.sidebar.header("1️⃣ 輸入標的")
st.sidebar.caption("美股直接輸入代碼，台股請加 .TW（如 2330.TW）")
default_tickers = "TSLA, NVDA, GOOG"
tickers_input = st.sidebar.text_area("股票代碼（逗號分隔）", value=default_tickers, height=80)

st.sidebar.divider()
st.sidebar.header("2️⃣ 結構條件 (%)")
st.sidebar.info("以該期「進場價」為 100% 基準：")
ko_pct    = st.sidebar.number_input("KO（敲出價 %）", value=100.0, step=0.5, format="%.1f")
strike_pct= st.sidebar.number_input("Strike（執行價 %）", value=80.0, step=1.0, format="%.1f")
ki_pct    = st.sidebar.number_input("KI（下檔保護 %）", value=65.0, step=1.0, format="%.1f")
ko_memory = st.sidebar.checkbox("KO Memory 模式（記憶型敲出）", value=False)

st.sidebar.divider()
st.sidebar.header("3️⃣ 產品時程設定")
first_obs_date = st.sidebar.date_input("首個比價日", value=None)
last_obs_date  = st.sidebar.date_input("最後比價日", value=None)
guaranteed_months = st.sidebar.number_input("保證配息期（月）", min_value=0, max_value=12, value=1, step=1)

st.sidebar.divider()
st.sidebar.header("4️⃣ 投資與配息設定")
principal  = st.sidebar.number_input("投資本金（USD）", value=100000, step=10000)
coupon_pa  = st.sidebar.number_input("年化配息率（Coupon %）", value=8.00, step=0.01, format="%.2f")
fx_rate    = st.sidebar.number_input("匯率（USD → TWD）", value=31.0, step=0.1, format="%.1f")

# 自動計算每月配息
monthly_coupon_usd = round(principal * coupon_pa / 100 / 12, 2)
monthly_coupon_twd = round(monthly_coupon_usd * fx_rate)
st.sidebar.success(f"預計每月配息：**${monthly_coupon_usd:,.2f} USD**　≈　**{monthly_coupon_twd:,} TWD**")

st.sidebar.divider()
st.sidebar.header("5️⃣ 配息期程設定")
n_periods = st.sidebar.number_input("期數", min_value=1, max_value=24, value=4, step=1)

periods = []
for i in range(int(n_periods)):
    with st.sidebar.expander(f"第 {i+1} 期", expanded=(i == 0)):
        p_pay = st.date_input(f"配息日", value=None, key=f"pp_{i}")
        st.caption(f"預計配息：${monthly_coupon_usd:,.2f} USD ≈ {round(monthly_coupon_usd * fx_rate):,} TWD")
        periods.append({"t": i+1, "start": None, "end": None, "pay": p_pay, "amount_usd": monthly_coupon_usd})

st.sidebar.divider()
st.sidebar.header("6️⃣ 回測參數")
period_months = st.sidebar.number_input("觀察天期（月）", min_value=1, max_value=60, value=6, step=1)

run_btn = st.sidebar.button("🚀 開始分析", type="primary")
if run_btn:
    st.session_state['show_results'] = True

# ==========================================
# 核心函數
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_data(ticker):
    try:
        df = yf.download(ticker, start="2009-01-01", progress=False)
        if df.empty:
            return None, f"找不到 {ticker}"
        df = df.reset_index()
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
        df = df.loc[:, ~df.columns.duplicated()]
        if 'Datetime' in df.columns: df = df.rename(columns={'Datetime': 'Date'})
        if 'Close' not in df.columns: return None, "無收盤價資料"
        df['Date'] = pd.to_datetime(df['Date'])
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df = df.dropna(subset=['Close'])
        df['MA20']  = df['Close'].rolling(20).mean()
        df['MA60']  = df['Close'].rolling(60).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        return df, None
    except Exception as e:
        return None, str(e)

@st.cache_data
def run_backtest(df, ki_pct, strike_pct, months, memory_ko=False):
    trading_days = int(months * 21)
    bt = df[['Date', 'Close']].copy()
    bt.columns = ['Start_Date', 'Start_Price']
    bt['End_Date']    = bt['Start_Date'].shift(-trading_days)
    bt['Final_Price'] = bt['Start_Price'].shift(-trading_days)
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=trading_days)
    bt['Min_Price_During'] = bt['Start_Price'].rolling(window=indexer, min_periods=1).min()
    bt['Max_Price_During'] = bt['Start_Price'].rolling(window=indexer, min_periods=1).max()
    bt = bt.dropna()
    if bt.empty: return None, None

    bt['KI_Level']     = bt['Start_Price'] * (ki_pct / 100)
    bt['Strike_Level'] = bt['Start_Price'] * (strike_pct / 100)
    bt['KO_Level']     = bt['Start_Price'] * (ko_pct / 100)

    bt['Touched_KI']  = bt['Min_Price_During'] < bt['KI_Level']
    bt['Below_Strike']= bt['Final_Price'] < bt['Strike_Level']

    if memory_ko:
        bt['Hit_KO'] = bt['Max_Price_During'] >= bt['KO_Level']
        conditions = [
            bt['Hit_KO'] == True,
            (bt['Touched_KI'] == True) & (bt['Below_Strike'] == True),
            (bt['Touched_KI'] == True) & (bt['Below_Strike'] == False),
            bt['Touched_KI'] == False,
        ]
        choices = ['KO_Exit', 'Loss', 'Safe', 'Safe']
    else:
        conditions = [
            (bt['Touched_KI'] == True) & (bt['Below_Strike'] == True),
            (bt['Touched_KI'] == True) & (bt['Below_Strike'] == False),
            bt['Touched_KI'] == False,
        ]
        choices = ['Loss', 'Safe', 'Safe']

    bt['Result_Type'] = np.select(conditions, choices, default='Unknown')

    loss_indices = bt[bt['Result_Type'] == 'Loss'].index
    recovery_counts, stuck_count = [], 0
    for idx in loss_indices:
        row = bt.loc[idx]
        future = df[(df['Date'] > row['End_Date']) & (df['Close'] >= row['Strike_Level'])]
        if not future.empty:
            recovery_counts.append((future.iloc[0]['Date'] - row['End_Date']).days)
        else:
            stuck_count += 1

    def bar_val(row):
        gap = ((row['Final_Price'] - row['Strike_Level']) / row['Strike_Level']) * 100
        return gap if row['Result_Type'] == 'Loss' else max(0, gap)

    bt['Bar_Value'] = bt.apply(bar_val, axis=1)
    color_map = {'Loss': 'red', 'Safe': 'green', 'KO_Exit': 'blue', 'Unknown': 'gray'}
    bt['Color'] = bt['Result_Type'].map(color_map)

    total      = len(bt)
    safe_count = len(bt[bt['Result_Type'].isin(['Safe', 'KO_Exit'])])
    ko_count   = len(bt[bt['Result_Type'] == 'KO_Exit']) if memory_ko else 0
    stats = {
        'safety_prob':   (safe_count / total) * 100,
        'positive_prob': (len(bt[bt['Final_Price'] > bt['Start_Price']]) / total) * 100,
        'loss_count':    len(loss_indices),
        'ko_count':      ko_count,
        'avg_recovery':  np.mean(recovery_counts) if recovery_counts else 0,
        'stuck_count':   stuck_count,
        'bt':            bt,
    }
    return bt, stats

def plot_price_chart(df, ticker, current_price, p_ko, p_ki, p_st):
    plot_df = df.tail(750).copy()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['Close'], mode='lines', name='股價', line=dict(color='black', width=1.5)))
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['MA20'],  mode='lines', name='月線', line=dict(color='#3498db', width=1)))
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['MA60'],  mode='lines', name='季線', line=dict(color='#f1c40f', width=1)))
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['MA240'], mode='lines', name='年線', line=dict(color='#9b59b6', width=1)))
    for y, color, text, dash in [(p_ko, 'red', f'KO: {p_ko:.2f}', 'dash'), (p_st, 'green', f'Strike: {p_st:.2f}', 'solid'), (p_ki, 'orange', f'KI: {p_ki:.2f}', 'dot')]:
        fig.add_hline(y=y, line_dash=dash, line_color=color, line_width=2)
        fig.add_annotation(x=1, y=y, xref="paper", yref="y", text=text, showarrow=False, xanchor="left", font=dict(color=color))
    all_p = [p_ko, p_ki, p_st, plot_df['Close'].max(), plot_df['Close'].min()]
    fig.update_layout(title=f"{ticker} - 走勢與關鍵價位（近3年）", height=450, margin=dict(r=80),
                      xaxis_title="日期", yaxis_title="價格",
                      yaxis_range=[min(all_p)*0.9, max(all_p)*1.05],
                      hovermode="x unified", legend=dict(orientation="h", y=1.02, x=0))
    return fig

def plot_bar_chart(bt_data, ticker):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=bt_data['Start_Date'], y=bt_data['Bar_Value'], marker_color=bt_data['Color'], name='期末表現'))
    fig.add_hline(y=0, line_width=1, line_color="black")
    fig.update_layout(title=f"{ticker} - 滾動回測損益分佈（2009至今）",
                      xaxis_title="進場日期", yaxis_title="期末距離 Strike (%)",
                      height=350, margin=dict(l=20, r=20, t=40, b=20), showlegend=False, hovermode="x unified")
    return fig

def plot_heatmap(bt_data, ticker):
    bt = bt_data.copy()
    bt['Year']  = pd.to_datetime(bt['Start_Date']).dt.year
    bt['Month'] = pd.to_datetime(bt['Start_Date']).dt.month
    bt['Is_Safe'] = (bt['Result_Type'].isin(['Safe', 'KO_Exit'])).astype(int)
    pivot = bt.groupby(['Year', 'Month'])['Is_Safe'].mean() * 100
    pivot = pivot.unstack(level='Month')
    pivot.columns = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']
    fig = px.imshow(pivot, color_continuous_scale='RdYlGn', zmin=0, zmax=100,
                    labels=dict(color="安全機率(%)"), title=f"{ticker} - 歷史安全機率熱力圖（依年月）",
                    aspect="auto")
    fig.update_layout(height=350)
    return fig

def _hex(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _rect(draw, x0, y0, x1, y1, fill, outline=None, radius=8):
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                            outline=outline, width=1 if outline else 0)

def generate_summary_image(ticker, current_price, p_ko, p_ki, p_st,
                            ko_pct, ki_pct, strike_pct,
                            coupon_pa, monthly_coupon_usd, monthly_coupon_twd, fx_rate,
                            principal, first_obs_date, last_obs_date,
                            safety_prob, positive_prob, period_months):
    W, H = 1100, 860
    img = Image.new('RGB', (W, H), _hex('#f0f4f8'))
    d = ImageDraw.Draw(img)

    f8  = _pil_font(16)
    f9  = _pil_font(18)
    f10 = _pil_font(20)
    f11 = _pil_font(22)
    f13 = _pil_font(26)
    f16 = _pil_font(32)
    f20 = _pil_font(40)
    f28 = _pil_font(56)
    f36 = _pil_font(72)

    PAD = 20

    # ── 標題列 ──
    _rect(d, PAD, PAD, W-PAD, 100, _hex('#1e3a5f'), radius=10)
    d.text((W//2, 55), '結構商品全能工作站  FCN/ELN 分析摘要',
           font=f16, fill=_hex('#ffffff'), anchor='mm')
    d.text((W-PAD-5, 88), f'產出日期：{date.today().strftime("%Y/%m/%d")}',
           font=f8, fill=_hex('#94a3b8'), anchor='rm')

    # ── 標的資訊 ──
    _rect(d, PAD, 110, 540, 225, _hex('#ffffff'), outline='#cbd5e1', radius=8)
    d.text((50, 122), '標的', font=f8, fill=_hex('#64748b'))
    d.text((50, 142), ticker, font=f20, fill=_hex('#1e293b'))
    d.text((50, 195), f'最新股價：{current_price:.2f}', font=f10, fill=_hex('#475569'))
    d.text((350, 195), f'觀察天期：{period_months} 個月', font=f10, fill=_hex('#475569'))

    # ── 關鍵價位 ──
    _rect(d, 550, 110, W-PAD, 225, _hex('#ffffff'), outline='#cbd5e1', radius=8)
    d.text((575, 122), '關鍵價位', font=f8, fill=_hex('#64748b'))
    levels = [
        (f'KO ({ko_pct:.0f}%)', f'{p_ko:.2f}', '#dc2626'),
        (f'Strike ({strike_pct:.0f}%)', f'{p_st:.2f}', '#16a34a'),
        (f'KI ({ki_pct:.0f}%)', f'{p_ki:.2f}', '#d97706'),
    ]
    for idx, (label, val, col) in enumerate(levels):
        x = 575 + idx * 175
        d.text((x, 148), label, font=f8, fill=_hex('#64748b'))
        d.text((x, 172), val, font=f13, fill=_hex(col))

    # ── 配息資訊 ──
    _rect(d, PAD, 235, 540, 360, _hex('#fff7ed'), outline='#fed7aa', radius=8)
    d.text((50, 248), '配息資訊', font=f8, fill=_hex('#64748b'))
    d.text((50, 270), f'年化配息率：{coupon_pa:.2f}%', font=f11, fill=_hex('#1e293b'))
    d.text((50, 305), f'投資本金：${principal:,} USD', font=f10, fill=_hex('#475569'))
    d.text((50, 330), f'每月配息：${monthly_coupon_usd:,.2f} USD  ≈  {monthly_coupon_twd:,} TWD（匯率{fx_rate:.0f}）',
           font=f10, fill=_hex('#c2410c'))

    # ── 比價時程 ──
    _rect(d, 550, 235, W-PAD, 360, _hex('#f0fdf4'), outline='#bbf7d0', radius=8)
    d.text((575, 248), '比價時程', font=f8, fill=_hex('#64748b'))
    if first_obs_date and last_obs_date:
        days_to_first = (first_obs_date - date.today()).days
        status = f'還有 {days_to_first} 天' if days_to_first > 0 else ('比價進行中' if days_to_first >= 0 else '保證期已過')
        d.text((575, 278), f'首個比價日：{first_obs_date.strftime("%Y/%m/%d")}  ({status})', font=f10, fill=_hex('#1e293b'))
        d.text((575, 315), f'最後比價日：{last_obs_date.strftime("%Y/%m/%d")}', font=f10, fill=_hex('#1e293b'))
    else:
        d.text((575, 295), '（未設定比價日期）', font=f10, fill=_hex('#94a3b8'))

    # ── 回測結果 ──
    _rect(d, PAD, 370, W-PAD, 570, _hex('#ffffff'), outline='#cbd5e1', radius=8)
    d.text((50, 382), '歷史回測結果（2009 至今）', font=f8, fill=_hex('#64748b'))

    safe_col = '#16a34a' if safety_prob >= 80 else ('#d97706' if safety_prob >= 60 else '#dc2626')
    pos_col  = '#16a34a' if positive_prob >= 60 else '#d97706'
    loss_pct = 100 - safety_prob

    d.text((185, 415), f'{safety_prob:.1f}%', font=f36, fill=_hex(safe_col), anchor='mm')
    d.text((185, 502), '安全機率', font=f11, fill=_hex('#475569'), anchor='mm')
    d.text((185, 530), '（不觸發接股）', font=f9, fill=_hex('#94a3b8'), anchor='mm')

    d.text((560, 415), f'{positive_prob:.1f}%', font=f36, fill=_hex(pos_col), anchor='mm')
    d.text((560, 502), '正報酬機率', font=f11, fill=_hex('#475569'), anchor='mm')
    d.text((560, 530), '（期末股價高於進場）', font=f9, fill=_hex('#94a3b8'), anchor='mm')

    d.text((940, 430), f'{loss_pct:.1f}%', font=f28, fill=_hex('#dc2626'), anchor='mm')
    d.text((940, 502), '接股機率', font=f11, fill=_hex('#475569'), anchor='mm')

    # ── 配息期程 ──
    filled_periods = [p for p in periods if p['pay']]
    if filled_periods:
        _rect(d, PAD, 580, W-PAD, 720, _hex('#ffffff'), outline='#e2e8f0', radius=8)
        d.text((50, 592), f'配息期程（共 {len(filled_periods)} 期）', font=f8, fill=_hex('#64748b'))
        col_w = (W - 2*PAD - 60) // min(len(filled_periods), 6)
        for idx, p in enumerate(filled_periods[:6]):
            x = 50 + idx * col_w
            twd = round(p['amount_usd'] * fx_rate)
            d.text((x, 618), f'第 {p["t"]} 期', font=f8, fill=_hex('#94a3b8'))
            d.text((x, 640), p['pay'].strftime('%Y/%m/%d'), font=f9, fill=_hex('#1e293b'))
            d.text((x, 670), f'${p["amount_usd"]:,.0f}', font=f9, fill=_hex('#16a34a'))
            d.text((x, 695), f'{twd:,} TWD', font=f8, fill=_hex('#64748b'))

    # ── 免責聲明 ──
    _rect(d, PAD, 730, W-PAD, H-PAD, _hex('#fff1f2'), outline='#fecada', radius=8)
    d.text((50, 742), '⚠ 免責聲明', font=f8, fill=_hex('#dc2626'))
    d.text((50, 765), '本分析摘要僅供參考，不構成投資建議。歷史回測不代表未來績效。', font=f8, fill=_hex('#7f1d1d'))
    d.text((50, 788), 'ELN/FCN 為非保本商品，最大風險為本金全部損失。股價來源：Yahoo Finance。', font=f8, fill=_hex('#7f1d1d'))
    d.text((W-PAD-5, H-PAD-8), '結構商品全能工作站', font=f8, fill=_hex('#94a3b8'), anchor='rm')

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()


def show_tradingview(symbol):
    html_code = f"""
    <div style="transform: scale(1.2); transform-origin: top left; width: 83.3%;">
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-symbol-profile.js" async>
          {{"width": "100%", "height": "300", "colorTheme": "light", "isTransparent": false, "symbol": "{symbol}", "locale": "zh_TW"}}
          </script>
        </div>
    </div>"""
    components.html(html_code, height=370)

# ==========================================
# 主程式
# ==========================================
if st.session_state.get('show_results'):
    ticker_list = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    if not ticker_list:
        st.warning("請輸入股票代碼")
        st.stop()

    # ── 產品概覽卡 ──
    has_dates = first_obs_date and last_obs_date
    if has_dates:
        st.markdown("## 📋 產品概覽")
        today = date.today()
        days_to_first = (first_obs_date - today).days

        if days_to_first > 0:
            status_label = f"⏳ 保證配息期（還有 {days_to_first} 天開始比價）"
            status_color = "#f59e0b"
        elif days_to_first == 0:
            status_label = "🔔 今日為首個比價日"
            status_color = "#3b82f6"
        else:
            status_label = "📊 比價觀察期進行中"
            status_color = "#10b981"

        st.markdown(f"""
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:16px">
            <span style="background:{status_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.9em">{status_label}</span>
            &nbsp;&nbsp;
            <span style="color:#64748b">首個比價日 <b>{first_obs_date.strftime('%Y/%m/%d')}</b></span>
            &nbsp;&nbsp;
            <span style="color:#64748b">最後比價日 <b>{last_obs_date.strftime('%Y/%m/%d')}</b></span>
            &nbsp;&nbsp;
            <span style="color:#64748b">保證配息期（前{guaranteed_months}個月不比價）</span>
            &nbsp;&nbsp;
            <span style="color:#94a3b8;font-size:0.85em">首個比價日前不會觸發提前贖回</span>
        </div>
        """, unsafe_allow_html=True)

        # 配息期程表
        if any(p['pay'] for p in periods):
            st.markdown("### 💰 配息期程")
            rows = []
            total_usd = 0
            for p in periods:
                if p['pay']:
                    twd = round(p['amount_usd'] * fx_rate)
                    total_usd += p['amount_usd']
                    rows.append({
                        "期": p['t'],
                        "配息日": p['pay'].strftime('%Y/%m/%d'),
                        "預計配息 (USD)": f"${p['amount_usd']:,.2f}",
                        f"台幣 (匯率{fx_rate:.0f})": f"{twd:,}",
                    })

            df_periods = pd.DataFrame(rows)

            # 計算當前期數（以配息日判斷最近一期）
            current_period = None
            for p in periods:
                if p['pay'] and p['pay'] >= today:
                    current_period = p['t']
                    break

            # 樣式：目前期高亮
            def highlight_current(row):
                if current_period and row['期'] == current_period:
                    return ['background-color: #f0fdf4; font-weight: bold; color: #15803d'] * len(row)
                return [''] * len(row)

            st.dataframe(df_periods.style.apply(highlight_current, axis=1), use_container_width=True, hide_index=True)

            total_twd = round(total_usd * fx_rate)
            st.markdown(f"""
            <div style="text-align:right;font-size:0.95em;color:#475569;margin-top:4px">
                總計（{len(rows)}期全拿）：
                <b style="color:#dc2626">${total_usd:,} USD</b> ／
                <b style="color:#dc2626">約{total_twd//10000:.1f}萬台幣</b>
                &nbsp;※ 若提前KO，僅累計至觸發當期為止
            </div>
            """, unsafe_allow_html=True)
            st.divider()

    # ── 多標的風險比較表 ──
    comparison_data = []

    for ticker in ticker_list:
        st.markdown(f"---\n### 📌 標的：{ticker}")

        with st.spinner(f"正在分析 {ticker}..."):
            df, err = get_stock_data(ticker)

        if err:
            st.error(f"{ticker} 讀取失敗：{err}")
            continue

        try:
            current_price = float(df['Close'].iloc[-1])
            p_ko = current_price * (ko_pct / 100)
            p_st = current_price * (strike_pct / 100)
            p_ki = current_price * (ki_pct / 100)
        except:
            st.error(f"{ticker} 價格計算錯誤")
            continue

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新股價", f"{current_price:.2f}")
        c2.metric(f"KO ({ko_pct}%)", f"{p_ko:.2f}", help="股價達此提前獲利出場")
        c3.metric(f"KI ({ki_pct}%)", f"{p_ki:.2f}", help="股價跌破此保護消失", delta_color="inverse")
        c4.metric(f"Strike ({strike_pct}%)", f"{p_st:.2f}", help="接股成本")

        monthly_income_usd = principal * (coupon_pa / 100) / 12
        monthly_income_twd = round(monthly_income_usd * fx_rate)
        st.markdown("#### 💵 潛在現金流試算")
        m1, m2, m3 = st.columns(3)
        m1.metric("投資本金", f"${principal:,} USD")
        m2.metric("預估每月配息", f"${monthly_income_usd:,.0f} USD")
        m3.metric(f"台幣配息（匯率{fx_rate:.0f}）", f"{monthly_income_twd//10000:.1f}萬")
        st.divider()

        # 圖表（含下載鈕）
        fig_main = plot_price_chart(df, ticker, current_price, p_ko, p_ki, p_st)
        st.plotly_chart(fig_main, use_container_width=True, config={'toImageButtonOptions': {'format': 'png', 'filename': f'{ticker}_走勢圖', 'scale': 2}})

        # 回測
        bt_data, stats = run_backtest(df, ki_pct, strike_pct, period_months, memory_ko=ko_memory)
        if bt_data is None:
            st.warning("資料不足，無法回測")
            continue

        loss_pct  = 100 - stats['safety_prob']
        stuck_rate= (stats['stuck_count'] / stats['loss_count'] * 100) if stats['loss_count'] > 0 else 0
        ko_note   = f"其中 KO 提前獲利出場：**{stats['ko_count']}** 次 ｜ " if ko_memory else ""

        st.info(f"""
        **📊 長週期回測報告（2009至今，每 {period_months} 個月一期）：**

        1. **獲利潛力（正報酬機率）**：{stats['positive_prob']:.1f}%
        2. **安全性分析（不被換到股票的機率）**：{stats['safety_prob']:.1f}%
           {ko_note}
        3. **恢復力分析**：若發生接股票（機率約 {loss_pct:.1f}%），平均 **{stats['avg_recovery']:.0f} 天** 漲回 Strike
           *（尚未解套比例：{stuck_rate:.1f}%）*
        """)

        # 一鍵產出圖片
        _img_key = f"img_{ticker}_{date.today()}"
        if _img_key not in st.session_state:
            try:
                st.session_state[_img_key] = generate_summary_image(
                    ticker, current_price, p_ko, p_ki, p_st,
                    ko_pct, ki_pct, strike_pct,
                    coupon_pa, monthly_coupon_usd, monthly_coupon_twd, fx_rate,
                    principal, first_obs_date, last_obs_date,
                    stats['safety_prob'], stats['positive_prob'], period_months
                )
            except Exception as e:
                st.session_state[_img_key] = None
                st.warning(f"圖片產出失敗：{e}")
        if st.session_state.get(_img_key):
            import base64 as _b64
            _b64_str = _b64.b64encode(st.session_state[_img_key]).decode()
            _fname   = f"{ticker}_FCN分析摘要_{date.today().strftime('%Y%m%d')}.png"
            st.markdown(
                f'<a href="data:image/png;base64,{_b64_str}" download="{_fname}" '
                f'style="display:block;width:100%;text-align:center;padding:10px;'
                f'background:#1e3a5f;color:white;border-radius:8px;font-weight:bold;'
                f'text-decoration:none;font-size:1em;">📸 一鍵產出分析摘要圖片（{ticker}）</a>',
                unsafe_allow_html=True,
            )

        fig_bar = plot_bar_chart(bt_data, ticker)
        st.plotly_chart(fig_bar, use_container_width=True, config={'toImageButtonOptions': {'format': 'png', 'filename': f'{ticker}_回測圖', 'scale': 2}})

        st.subheader("🗓️ 歷史安全機率熱力圖")
        fig_heat = plot_heatmap(bt_data, ticker)
        st.plotly_chart(fig_heat, use_container_width=True, config={'toImageButtonOptions': {'format': 'png', 'filename': f'{ticker}_熱力圖', 'scale': 2}})

        comparison_data.append({
            "標的": ticker,
            "最新股價": f"{current_price:.2f}",
            f"KO ({ko_pct}%)": f"{p_ko:.2f}",
            f"KI ({ki_pct}%)": f"{p_ki:.2f}",
            f"Strike ({strike_pct}%)": f"{p_st:.2f}",
            "安全機率": f"{stats['safety_prob']:.1f}%",
            "正報酬機率": f"{stats['positive_prob']:.1f}%",
            "平均解套天數": f"{stats['avg_recovery']:.0f}",
        })

    # ── 多標的比較表 ──
    if len(comparison_data) > 1:
        st.divider()
        st.markdown("## 📊 多標的風險比較")
        df_compare = pd.DataFrame(comparison_data)
        st.dataframe(df_compare, use_container_width=True, hide_index=True)

else:
    st.info("👈 請在左側設定參數，按下「開始分析」。")
    if st.sidebar.button("🔄 重置", help="清除分析結果，重新設定參數"):
        st.session_state['show_results'] = False
        st.rerun()

# ── 免責聲明 ──
st.markdown("""
<style>
.disclaimer-box {
    background-color: #fff3f3; border: 1px solid #e0b4b4;
    padding: 15px; border-radius: 5px; color: #8a1f1f;
    font-size: 0.9em; margin-top: 30px;
}
</style>
<div class='disclaimer-box'>
    <strong>⚠️ 免責聲明與投資風險預告</strong><br>
    1. <strong>本工具僅供教學與模擬試算</strong>：數據、圖表與機率僅供參考，不代表投資建議。<br>
    2. <strong>歷史不代表未來</strong>：回測數據基於 2009 年至今之歷史股價。<br>
    3. <strong>非保本商品</strong>：ELN/FCN 最大風險為本金全數虧損。<br>
    4. <strong>實際條款為準</strong>：請以發行機構公開說明書及合約為準。<br>
    5. <strong>資料來源</strong>：股價來源為 Yahoo Finance，可能存在延遲或誤差。
</div>
""", unsafe_allow_html=True)
