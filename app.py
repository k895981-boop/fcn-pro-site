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
# 公版產品資料（對應監控網站）
# ==========================================
FCN_PRODUCTS = {
    "BBVA FCN・AMD+ARM+TSLA・20萬USD": {
        "tickers": "AMD, ARM, TSLA",
        "ko_pct": 100.0, "strike_pct": 70.0, "ki_pct": 60.0,
        "coupon_pa": 27.74, "principal": 200000, "fx_rate": 31.0,
        "first_ko_date": date(2026, 7, 6), "last_ko_date": date(2026, 10, 5),
        "guaranteed_months": 1, "period_months": 6,
        "periods": [
            {"t": 1, "pay": date(2026, 7, 8),  "amount_usd": 4623},
            {"t": 2, "pay": date(2026, 8, 7),  "amount_usd": 4623},
            {"t": 3, "pay": date(2026, 9, 10), "amount_usd": 4623},
            {"t": 4, "pay": date(2026, 10, 7), "amount_usd": 4623},
        ],
    },
    "Goldman Sachs FCN・TSM+MU+NVDA・5萬USD": {
        "tickers": "TSM, MU, NVDA",
        "ko_pct": 100.0, "strike_pct": 60.0, "ki_pct": 50.0,
        "coupon_pa": 23.61, "principal": 50000, "fx_rate": 31.0,
        "first_ko_date": date(2026, 7, 23), "last_ko_date": date(2026, 12, 23),
        "guaranteed_months": 1, "period_months": 6,
        "periods": [
            {"t": 1, "pay": date(2026, 7, 27),  "amount_usd": 984},
            {"t": 2, "pay": date(2026, 8, 26),  "amount_usd": 984},
            {"t": 3, "pay": date(2026, 9, 25),  "amount_usd": 984},
            {"t": 4, "pay": date(2026, 10, 27), "amount_usd": 984},
            {"t": 5, "pay": date(2026, 11, 25), "amount_usd": 984},
            {"t": 6, "pay": date(2026, 12, 28), "amount_usd": 984},
        ],
    },
    "Goldman Sachs FCN・TSM+MU+NVDA・10萬USD": {
        "tickers": "TSM, MU, NVDA",
        "ko_pct": 100.0, "strike_pct": 60.0, "ki_pct": 50.0,
        "coupon_pa": 23.61, "principal": 100000, "fx_rate": 31.0,
        "first_ko_date": date(2026, 7, 23), "last_ko_date": date(2026, 12, 23),
        "guaranteed_months": 1, "period_months": 6,
        "periods": [
            {"t": 1, "pay": date(2026, 7, 27),  "amount_usd": 1968},
            {"t": 2, "pay": date(2026, 8, 26),  "amount_usd": 1968},
            {"t": 3, "pay": date(2026, 9, 25),  "amount_usd": 1968},
            {"t": 4, "pay": date(2026, 10, 27), "amount_usd": 1968},
            {"t": 5, "pay": date(2026, 11, 25), "amount_usd": 1968},
            {"t": 6, "pay": date(2026, 12, 28), "amount_usd": 1968},
        ],
    },
}

# ==========================================
# 工具函數（必須在 sidebar 之前定義）
# ==========================================

def _gen_fcn_html(tickers, ko_pct, strike_pct, ki_pct, coupon_pa,
                  principal, fx_rate, first_obs_date, last_obs_date,
                  filled_periods, monthly_coupon_usd, monthly_coupon_twd, prices,
                  period_months=6):
    today_str = date.today().strftime('%Y/%m/%d')
    _wan = int(principal // 10000) if principal >= 10000 else f'{int(principal):,}'
    title = f'FCN {"/".join(tickers)}/{int(period_months)}個月/{_wan}萬USD'

    period_rows_html = ''
    for p in filled_periods:
        pay_str = p['pay'].strftime('%Y/%m/%d') if p.get('pay') else '—'
        twd = round(p['amount_usd'] * fx_rate)
        period_rows_html += f'''
        <tr>
          <td>第 {p["t"]} 期</td>
          <td>{pay_str}</td>
          <td style="color:#4ade80">${p["amount_usd"]:,.0f}</td>
          <td style="color:#4ade80">{twd:,} TWD</td>
        </tr>'''

    stock_cards_html = ''
    for t in tickers:
        cp = prices.get(t)
        if cp:
            ko_p = cp * ko_pct / 100
            st_p = cp * strike_pct / 100
            ki_p = cp * ki_pct / 100
            rng_lo = ki_pct * 0.75; rng_hi = ko_pct * 1.25; rng = rng_hi - rng_lo
            ki_pos  = (ki_pct     - rng_lo) / rng * 100
            st_pos  = (strike_pct - rng_lo) / rng * 100
            ko_pos  = (ko_pct     - rng_lo) / rng * 100
            cur_pos = (100.0      - rng_lo) / rng * 100
            price_display = f'${cp:.2f}'
        else:
            price_display = '載入中…'
            ki_pos = st_pos = ko_pos = cur_pos = ko_p = st_p = ki_p = 0

        stock_cards_html += f'''
        <div class="stock-card">
          <div class="stock-ticker">{t}</div>
          <div class="stock-price">{price_display}</div>
          <div class="bar-wrap">
            <div class="bar-danger"  style="left:0;width:{ki_pos:.1f}%"></div>
            <div class="bar-warning" style="left:{ki_pos:.1f}%;width:{(st_pos-ki_pos):.1f}%"></div>
            <div class="bar-safe"    style="left:{st_pos:.1f}%;width:{(ko_pos-st_pos):.1f}%"></div>
            <div class="bar-ko"      style="left:{ko_pos:.1f}%;width:{max(0,100-ko_pos):.1f}%"></div>
            <div class="bar-cursor"  style="left:{cur_pos:.1f}%"></div>
          </div>
          <div class="level-row">
            <span style="color:#f59e0b">▼ KI {ki_pct:.0f}%  ${ki_p:.2f}</span>
            <span style="color:#4ade80">— Strike {strike_pct:.0f}%  ${st_p:.2f}</span>
            <span style="color:#f87171">▲ KO {ko_pct:.0f}%  ${ko_p:.2f}</span>
          </div>
        </div>'''

    first_str = first_obs_date.strftime('%Y/%m/%d') if first_obs_date else '—'
    last_str  = last_obs_date.strftime('%Y/%m/%d')  if last_obs_date  else '—'
    days_txt  = ''
    if first_obs_date:
        d2f = (first_obs_date - date.today()).days
        days_txt = f'（還有 {d2f} 天）' if d2f > 0 else '（比價進行中）'

    periods_block = (
        '<div class="section"><div class="section-title">🗓️ 配息期程</div>'
        '<table><thead><tr><th>期數</th><th>配息日</th><th>配息 (USD)</th><th>配息 (TWD)</th></tr></thead>'
        f'<tbody>{period_rows_html}</tbody></table></div>'
    ) if filled_periods else ''

    stocks_block = (
        '<div class="section"><div class="section-title">📈 個股詳細卡片</div>'
        f'<div class="stock-grid">{stock_cards_html}</div></div>'
    ) if any(prices.get(t) for t in tickers) else ''

    return f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:"Noto Sans TC",system-ui,sans-serif;background:#0f172a;color:#f1f5f9;padding:20px;min-height:100vh}}
  .header{{background:linear-gradient(135deg,#1e3a5f,#1e4080);padding:28px 24px;border-radius:14px;margin-bottom:16px}}
  .header-sub{{color:#94a3b8;font-size:.85em;margin-bottom:8px}}
  .header-title{{font-size:1.7em;font-weight:700;margin-bottom:12px;line-height:1.3}}
  .header-info{{display:flex;flex-wrap:wrap;gap:16px;color:#cbd5e1;font-size:.9em}}
  .header-info span::before{{content:"｜";margin-right:8px;color:#475569}}
  .header-info span:first-child::before{{content:""}}
  .levels{{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}}
  .level-chip{{padding:8px 16px;border-radius:8px;font-weight:600;font-size:.95em}}
  .level-ko{{background:#450a0a;color:#f87171;border:1px solid #7f1d1d}}
  .level-st{{background:#052e16;color:#4ade80;border:1px solid #14532d}}
  .level-ki{{background:#451a03;color:#fb923c;border:1px solid #7c2d12}}
  .section{{margin-bottom:16px}}
  .section-title{{color:#94a3b8;font-size:.8em;letter-spacing:.1em;margin-bottom:8px;padding-left:4px}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:10px;overflow:hidden}}
  th{{background:#0f172a;color:#94a3b8;font-size:.85em;padding:10px 16px;text-align:center}}
  td{{padding:10px 16px;text-align:center;border-bottom:1px solid #334155;font-size:.95em}}
  tr:last-child td{{border-bottom:none}}
  .stock-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}
  .stock-card{{background:#1e293b;border-radius:12px;padding:20px}}
  .stock-ticker{{color:#94a3b8;font-size:.85em;margin-bottom:4px}}
  .stock-price{{font-size:2em;font-weight:700;margin-bottom:14px}}
  .bar-wrap{{position:relative;height:14px;border-radius:7px;overflow:hidden;background:#334155;margin-bottom:10px}}
  .bar-danger,.bar-warning,.bar-safe,.bar-ko{{position:absolute;top:0;height:100%}}
  .bar-danger{{background:#7f1d1d}}.bar-warning{{background:#78350f}}
  .bar-safe{{background:#14532d}}.bar-ko{{background:#166534}}
  .bar-cursor{{position:absolute;top:-3px;width:4px;height:20px;background:#f1f5f9;border-radius:2px;transform:translateX(-50%)}}
  .level-row{{display:flex;justify-content:space-between;font-size:.78em;flex-wrap:wrap;gap:4px}}
  .legend-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}
  .legend-card{{padding:18px;border-radius:10px}}
  .legend-ko{{background:#450a0a;border:1px solid #7f1d1d}}
  .legend-st{{background:#052e16;border:1px solid #14532d}}
  .legend-ki{{background:#451a03;border:1px solid #7c2d12}}
  .legend-label{{font-size:.78em;color:#94a3b8;margin-bottom:4px}}
  .legend-badge{{font-size:1.1em;font-weight:700;margin-bottom:8px}}
  .legend-text{{font-size:.82em;color:#cbd5e1;line-height:1.5}}
  .footer{{text-align:center;color:#475569;font-size:.78em;margin-top:24px;padding-top:16px;border-top:1px solid #1e293b}}
</style>
</head>
<body>
<div class="header">
  <div class="header-sub">FCN 結構商品分析摘要　產出日期：{today_str}</div>
  <div class="header-title">{title}</div>
  <div class="header-info">
    <span>年化率 {coupon_pa:.2f}%</span>
    <span>月息 ${monthly_coupon_usd:,.0f} USD ≈ {monthly_coupon_twd:,} TWD</span>
    <span>匯率 {fx_rate:.0f}</span>
    <span>首比價日 {first_str} {days_txt}</span>
    <span>末比價日 {last_str}</span>
  </div>
</div>
<div class="levels">
  <div class="level-chip level-ko">出場價 {ko_pct:.0f}%</div>
  <div class="level-chip level-st">— Strike 執行 {strike_pct:.0f}%</div>
  <div class="level-chip level-ki">▼ KI 保護 {ki_pct:.0f}%</div>
</div>
{periods_block}
{stocks_block}
<div class="section">
  <div class="section-title">📝 條件說明</div>
  <div class="legend-grid">
    <div class="legend-card legend-ko">
      <div class="legend-label">KO 自動提前回固</div>
      <div class="legend-badge" style="color:#f87171">出場價 {ko_pct:.0f}%</div>
      <div class="legend-text">三檔標的皆超標，產品自動結束，拿回本金＋已累積配息。只要有一檔未達標，當天就不解構。</div>
    </div>
    <div class="legend-card legend-st">
      <div class="legend-label">Strike 執行價</div>
      <div class="legend-badge" style="color:#4ade80">— Strike {strike_pct:.0f}%</div>
      <div class="legend-text">到期時若最差標的低於此值，將以此價格買進最差標的股票，用以返還本金。</div>
    </div>
    <div class="legend-card legend-ki">
      <div class="legend-label">KI 保護價</div>
      <div class="legend-badge" style="color:#fb923c">▼ KI 保護 {ki_pct:.0f}%</div>
      <div class="legend-text">若任一比價日任一檔低於 KI 值，到期時將以執行價（Strike）買進最差標的股票，到期日前若未跌破，不在此限。</div>
    </div>
  </div>
</div>
<div class="footer">本摘要僅供參考，不構成投資建議。ELN/FCN 為非保本商品，最大風險為本金全部損失。</div>
</body>
</html>'''


# ==========================================
# 側邊欄
# ==========================================

# ── 1️⃣ 輸入標的 ──
st.sidebar.header("1️⃣ 輸入標的")
st.sidebar.caption("美股直接輸入代碼，台股請加 .TW（如 2330.TW）")
tickers_input = st.sidebar.text_area(
    "股票代碼（逗號分隔）",
    value=st.session_state.get('w_tickers', "TSLA, NVDA, GOOG"),
    key='w_tickers', height=80,
)

st.sidebar.divider()
st.sidebar.header("2️⃣ 結構條件 (%)")
st.sidebar.info("以該期「進場價」為 100% 基準：")
ko_pct     = st.sidebar.number_input("KO 出廠價（%）",      key='w_ko_pct',     value=st.session_state.get('w_ko_pct',     100.0), step=0.5,  format="%.1f")
strike_pct = st.sidebar.number_input("Strike 執行價（%）",  key='w_strike_pct', value=st.session_state.get('w_strike_pct', 80.0),  step=1.0,  format="%.1f")
ki_pct     = st.sidebar.number_input("KI 保護價（%）",      key='w_ki_pct',     value=st.session_state.get('w_ki_pct',     65.0),  step=1.0,  format="%.1f")
ko_memory  = st.sidebar.checkbox("KO Memory 模式（記憶型敲出）", value=False)

st.sidebar.divider()
st.sidebar.header("3️⃣ 產品時程設定")
_first_days = st.sidebar.number_input("首個比價日（距今天數）", min_value=0, max_value=730,
                                       value=int(st.session_state.get('w_first_days', 12)), step=1, key='w_first_days')
_last_days  = st.sidebar.number_input("最後比價日（距今天數）", min_value=0, max_value=730,
                                       value=int(st.session_state.get('w_last_days', 103)), step=1, key='w_last_days')
first_obs_date = date.today() + timedelta(days=int(_first_days))
last_obs_date  = date.today() + timedelta(days=int(_last_days))
st.sidebar.caption(f"首個比價日：{first_obs_date.strftime('%Y/%m/%d')}　最後：{last_obs_date.strftime('%Y/%m/%d')}")
guaranteed_months = st.sidebar.number_input("保證配息期（月）", min_value=0, max_value=12,
                                             value=int(st.session_state.get('w_guar_months', 1)), step=1, key='w_guar_months')

st.sidebar.divider()
st.sidebar.header("4️⃣ 投資與配息設定")
principal = st.sidebar.number_input("投資本金（USD）",
                                     value=float(st.session_state.get('w_principal', 100000.0)),
                                     step=10000.0, key='w_principal')
coupon_pa = st.sidebar.number_input("年化配息率（Coupon %）",
                                     value=float(st.session_state.get('w_coupon_pa', 8.00)),
                                     step=0.01, format="%.2f", key='w_coupon_pa')
fx_rate   = st.sidebar.number_input("匯率（USD → TWD）",
                                     value=float(st.session_state.get('w_fx_rate', 31.0)),
                                     step=0.1, format="%.1f", key='w_fx_rate')

# 自動計算每月配息
monthly_coupon_usd = round(principal * coupon_pa / 100 / 12, 2)
monthly_coupon_twd = round(monthly_coupon_usd * fx_rate)
st.sidebar.success(f"預計每月配息：**${monthly_coupon_usd:,.2f} USD**　≈　**{monthly_coupon_twd:,} TWD**")

st.sidebar.divider()
st.sidebar.header("5️⃣ 配息期程設定")
n_periods = st.sidebar.number_input("期數", min_value=1, max_value=24,
                                     value=int(st.session_state.get('w_n_periods', 4)), step=1, key='w_n_periods')

periods = []
for i in range(int(n_periods)):
    with st.sidebar.expander(f"第 {i+1} 期", expanded=(i == 0)):
        _pay_days = st.number_input(f"配息日（距今天數）", min_value=0, max_value=730,
                                    value=int(st.session_state.get(f'pp_days_{i}', (i+1)*30)),
                                    step=1, key=f"pp_days_{i}")
        p_pay = date.today() + timedelta(days=int(_pay_days))
        st.caption(f"配息日：{p_pay.strftime('%Y/%m/%d')}　預計配息：${monthly_coupon_usd:,.2f} USD ≈ {round(monthly_coupon_usd * fx_rate):,} TWD")
        periods.append({"t": i+1, "start": None, "end": None, "pay": p_pay, "amount_usd": monthly_coupon_usd})

filled_periods = [p for p in periods if p.get('pay')]

st.sidebar.divider()
st.sidebar.header("6️⃣ 回測參數")
period_months = st.sidebar.number_input("觀察天期（月）", min_value=1.0, max_value=60.0,
                                         value=float(st.session_state.get('w_period_months', 6.0)),
                                         step=1.0, key='w_period_months')

run_btn = st.sidebar.button("🚀 開始分析", type="primary")

st.sidebar.divider()
st.sidebar.header("7️⃣ 生成")
if st.sidebar.button("🌐 生成", type="primary", use_container_width=True):
    _tlist  = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    _prices = {}
    for _t in _tlist:
        try:
            _prices[_t] = float(yf.Ticker(_t).fast_info.last_price)
        except Exception:
            _prices[_t] = None
    _filled = [p for p in periods if p.get('pay')]
    st.session_state['fcn_page_html'] = _gen_fcn_html(
        _tlist, ko_pct, strike_pct, ki_pct, coupon_pa,
        principal, fx_rate, first_obs_date, last_obs_date,
        _filled, monthly_coupon_usd, monthly_coupon_twd, _prices,
        period_months=period_months
    )
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

def _th(font):
    """取得字型行高（含行距）"""
    bb = font.getbbox('Ag字')
    return bb[3] - bb[1] + 6

def _tw(font, text):
    bb = font.getbbox(text)
    return bb[2] - bb[0]

def generate_fcn_image(
    tickers, ko_pct, ki_pct, strike_pct,
    coupon_pa, monthly_coupon_usd, monthly_coupon_twd, fx_rate,
    principal, first_obs_date, last_obs_date,
    filled_periods, ticker_data=None, sections=None, period_months=6,
):
    """
    ticker_data: list of {ticker, current_price, safety_prob, positive_prob} — optional
    sections:    dict with keys header/periods/status/stocks/legend
    """
    if sections is None:
        sections = {k: True for k in ['header','periods','status','stocks','legend']}

    fSM  = _pil_font(17)
    fMD  = _pil_font(21)
    fLG  = _pil_font(27)
    fXL  = _pil_font(34)
    fTIC = _pil_font(46)
    fHDR = _pil_font(24)

    W, PAD, GAP, IP = 1200, 24, 12, 16
    hSM  = _th(fSM); hMD = _th(fMD); hLG = _th(fLG)
    hXL  = _th(fXL); hTIC = _th(fTIC); hHDR = _th(fHDR)

    DARK, WHITE = '#1e3a5f', '#ffffff'

    img = Image.new('RGB', (W, 3600), _hex('#f0f4f8'))
    d   = ImageDraw.Draw(img)
    y   = PAD

    def sec_title(title):
        nonlocal y
        d.rectangle([PAD, y, W-PAD, y+hHDR+IP*2], fill=_hex(DARK))
        d.text((PAD+IP, y+IP), title, font=fHDR, fill=_hex(WHITE))
        y += hHDR + IP*2 + 6

    # ── 1. 產品標題 & 基本資訊 ──
    if sections.get('header', True):
        _wan = int(principal // 10000) if principal >= 10000 else f'{int(principal):,}'
        title = f'FCN {"/".join(tickers)}/{int(period_months)}個月/{_wan}萬USD'

        hdr_h = IP + hSM + 8 + hXL + 10 + hMD + IP
        d.rectangle([PAD, y, W-PAD, y+hdr_h], fill=_hex(DARK), outline=None)
        d.text((PAD+IP, y+IP), '結構商品全能工作站  FCN/ELN 分析摘要', font=fSM, fill=_hex('#94a3b8'))
        d.text((PAD+IP, y+IP+hSM+8), title, font=fXL, fill=_hex(WHITE))
        info_parts = []
        if first_obs_date: info_parts.append(f'首比價日 {first_obs_date.strftime("%Y/%m/%d")}')
        if last_obs_date:  info_parts.append(f'末比價日 {last_obs_date.strftime("%Y/%m/%d")}')
        info_parts += [f'年化率 {coupon_pa:.2f}%',
                       f'月息 {monthly_coupon_usd:,.0f} USD ≈ {monthly_coupon_twd:,} TWD（匯率{fx_rate:.0f}）']
        d.text((PAD+IP, y+IP+hSM+8+hXL+10), '   ｜   '.join(info_parts), font=fMD, fill=_hex('#cbd5e1'))
        y += hdr_h + GAP

        # KO / Strike / KI 一行
        bar_h = IP + hLG + 6 + hSM + IP
        _rect(d, PAD, y, W-PAD, y+bar_h, _hex('#eff6ff'), outline='#bfdbfe', radius=8)
        ky = y + IP
        for offset, label, col in [
            (0,   f'出場價 {ko_pct:.0f}%',           '#dc2626'),
            (360, f'— Strike 執行  {strike_pct:.0f}%', '#16a34a'),
            (720, f'▼ KI 保護  {ki_pct:.0f}%',      '#d97706'),
        ]:
            d.text((PAD+IP+offset, ky), label, font=fLG, fill=_hex(col))
        d.text((PAD+IP, ky+hLG+4), '以進場價為 100% 基準，Worst-of（最差標的）決定結果', font=fSM, fill=_hex('#64748b'))
        y += bar_h + GAP

    # ── 2. 配息期程表 ──
    if sections.get('periods', True) and filled_periods:
        sec_title('🗓️  配息期程表')
        n_cols = min(len(filled_periods), 6)
        cw = (W - PAD*2) // n_cols
        row_h = IP + hMD + IP

        # header
        _rect(d, PAD, y, W-PAD, y+row_h, _hex('#1e293b'), outline=None, radius=6)
        for ci, h in enumerate(['期數', '配息日', '配息 USD', '配息 TWD'][:4] if n_cols <= 4
                                else ['期', '配息日', 'USD', 'TWD', '期', '配息日'][:n_cols]):
            d.text((PAD + ci*cw + cw//2 - _tw(fMD, h)//2, y+IP), h, font=fMD, fill=_hex(WHITE))
        y += row_h

        for idx, p in enumerate(filled_periods):
            row_bg = '#f8fafc' if idx % 2 == 0 else '#ffffff'
            _rect(d, PAD, y, W-PAD, y+row_h, _hex(row_bg), outline='#e2e8f0', radius=0)
            twd_amt = round(p['amount_usd'] * fx_rate)
            pay_str = p['pay'].strftime('%Y/%m/%d') if p.get('pay') else '—'
            vals = [f'第 {p["t"]} 期', pay_str, f'${p["amount_usd"]:,.0f}', f'{twd_amt:,}']
            for ci, v in enumerate(vals):
                vx = PAD + ci*cw + cw//2 - _tw(fMD, v)//2
                col = '#16a34a' if ci >= 2 else '#1e293b'
                d.text((vx, y+IP), v, font=fMD, fill=_hex(col))
            y += row_h
        y += GAP

    # ── 3. 整體狀況 (需先分析) ──
    if sections.get('status', True):
        if not ticker_data:
            sec_title('📊  整體狀況')
            _rect(d, PAD, y, W-PAD, y+IP*2+hMD, _hex('#fefce8'), outline='#fde68a', radius=8)
            d.text((PAD+IP, y+IP), '⚠ 請先按「🚀 開始分析」後再製圖，才能顯示此區塊', font=fMD, fill=_hex('#92400e'))
            y += IP*2+hMD+GAP
        else:
            sec_title('📊  整體狀況')
            n = len(ticker_data)
            card_w = (W - PAD*2 - GAP*(n-1)) // n
            card_h = IP + hSM + 8 + hTIC + IP
            for ci, td in enumerate(ticker_data):
                cx = PAD + ci*(card_w+GAP)
                cp = td['current_price']
                sp = td['safety_prob']
                safe_col = '#16a34a' if sp >= 80 else ('#d97706' if sp >= 60 else '#dc2626')
                _rect(d, cx, y, cx+card_w, y+card_h, _hex('#ffffff'), outline='#e2e8f0', radius=10)
                d.text((cx+IP, y+IP), td['ticker'], font=fSM, fill=_hex('#94a3b8'))
                d.text((cx+IP, y+IP+hSM+8), f'${cp:.2f}', font=fTIC, fill=_hex('#1e293b'))
                safe_txt = f'安全率 {sp:.1f}%'
                d.text((cx+card_w-IP-_tw(fSM, safe_txt), y+IP), safe_txt, font=fSM, fill=_hex(safe_col))
            y += card_h + GAP

    # ── 4. 個股詳細卡片 (需先分析) ──
    if sections.get('stocks', True):
        if not ticker_data:
            sec_title('📈  個股詳細卡片')
            _rect(d, PAD, y, W-PAD, y+IP*2+hMD, _hex('#fefce8'), outline='#fde68a', radius=8)
            d.text((PAD+IP, y+IP), '⚠ 請先按「🚀 開始分析」後再製圖，才能顯示此區塊', font=fMD, fill=_hex('#92400e'))
            y += IP*2+hMD+GAP
        else:
            sec_title('📈  個股詳細卡片')
            n = len(ticker_data)
            card_w = (W - PAD*2 - GAP*(n-1)) // n
            bar_h  = 18
            card_h = IP + hTIC + 8 + hMD + 12 + bar_h + 8 + hSM*3 + 8 + hMD*2 + IP

            for ci, td in enumerate(ticker_data):
                cx = PAD + ci*(card_w+GAP)
                cp = td['current_price']
                ko_p  = cp * ko_pct  / 100
                st_p  = cp * strike_pct / 100
                ki_p  = cp * ki_pct  / 100
                sp    = td['safety_prob']
                pp    = td['positive_prob']
                safe_col = '#16a34a' if sp >= 80 else ('#d97706' if sp >= 60 else '#dc2626')
                pos_col  = '#16a34a' if pp >= 60 else '#d97706'

                _rect(d, cx, y, cx+card_w, y+card_h, _hex('#ffffff'), outline='#e2e8f0', radius=10)
                iy = y + IP

                # Ticker + price
                d.text((cx+IP, iy), td['ticker'], font=fTIC, fill=_hex('#1e293b'))
                iy += hTIC + 8
                d.text((cx+IP, iy), f'現價  ${cp:.2f}', font=fMD, fill=_hex('#475569'))
                iy += hMD + 12

                # Price bar
                bx0, bx1 = cx+IP, cx+card_w-IP
                btotal = bx1 - bx0
                rng_lo, rng_hi = ki_pct * 0.75, ko_pct * 1.25
                rng = rng_hi - rng_lo

                def px(pct):
                    return bx0 + int((pct - rng_lo) / rng * btotal)

                d.rectangle([bx0, iy, bx1, iy+bar_h], fill=_hex('#e2e8f0'))
                xi = px(ki_pct); xs = px(strike_pct); xk = px(ko_pct)
                if xi < xs:
                    d.rectangle([max(bx0,xi), iy, min(bx1,xs), iy+bar_h], fill=_hex('#fecaca'))
                if xs < xk:
                    d.rectangle([max(bx0,xs), iy, min(bx1,xk), iy+bar_h], fill=_hex('#bbf7d0'))
                if xk < bx1:
                    d.rectangle([xk, iy, bx1, iy+bar_h], fill=_hex('#4ade80'))
                xc = px(100)
                d.rectangle([xc-2, iy-3, xc+2, iy+bar_h+3], fill=_hex('#1e293b'))
                iy += bar_h + 8

                # Level labels
                for label, col_l in [
                    (f'▼ KI {ki_pct:.0f}%  ${ki_p:.2f}', '#d97706'),
                    (f'— Strike {strike_pct:.0f}%  ${st_p:.2f}', '#16a34a'),
                    (f'▲ KO {ko_pct:.0f}%  ${ko_p:.2f}', '#dc2626'),
                ]:
                    d.text((cx+IP, iy), label, font=fSM, fill=_hex(col_l)); iy += hSM+2
                iy += 6

                # Backtest stats
                d.text((cx+IP, iy), f'安全機率：{sp:.1f}%', font=fMD, fill=_hex(safe_col))
                iy += hMD
                d.text((cx+IP, iy), f'正報酬機率：{pp:.1f}%', font=fMD, fill=_hex(pos_col))

            y += card_h + GAP

    # ── 5. KO / Strike / KI 條件說明 ──
    if sections.get('legend', True):
        sec_title('📝  條件說明')
        leg_data = [
            ('KO 自動提前回固', f'出場價 {ko_pct:.0f}%', '#dc2626', '#fff1f2', '#fecaca',
             '三檔標的皆超標，產品自動結束，拿回本金＋已累積配息。', '只要有一檔未達標，當天就不解構。'),
            ('Strike 執行價', f'— Strike {strike_pct:.0f}%', '#16a34a', '#f0fdf4', '#bbf7d0',
             '到期時若最差標的低於此值，將以此價格買進', '最差標的股票，用以返還本金。'),
            ('KI 保護價', f'▼ KI 保護 {ki_pct:.0f}%', '#d97706', '#fffbeb', '#fde68a',
             '若任一比價日任一檔低於KI值，到期將以執行價', '（Strike）買進最差標的，未跌破則不在此限。'),
        ]
        leg_w = (W - PAD*2 - GAP*2) // 3
        leg_h = IP + hSM + 6 + hLG + 10 + hSM*2 + 6 + IP
        for ci, (title_l, badge, col, bg, border, line1, line2) in enumerate(leg_data):
            lx = PAD + ci*(leg_w+GAP)
            _rect(d, lx, y, lx+leg_w, y+leg_h, _hex(bg), outline=border, radius=10)
            d.text((lx+IP, y+IP), title_l, font=fSM, fill=_hex('#64748b'))
            d.text((lx+IP, y+IP+hSM+6), badge, font=fLG, fill=_hex(col))
            d.text((lx+IP, y+IP+hSM+6+hLG+8), line1, font=fSM, fill=_hex('#374151'))
            d.text((lx+IP, y+IP+hSM+6+hLG+8+hSM+3), line2, font=fSM, fill=_hex('#374151'))
        y += leg_h + GAP

    # watermark
    wm = f'結構商品全能工作站  {date.today().strftime("%Y/%m/%d")}'
    d.text((W-PAD-_tw(fSM, wm), y), wm, font=fSM, fill=_hex('#cbd5e1'))
    y += hSM

    img = img.crop((0, 0, W, y + PAD))
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

# ── Section 7：產生公版頁面 ──
if st.session_state.get('fcn_page_html'):
    st.markdown("## 🌐 公版頁面預覽")
    components.html(st.session_state['fcn_page_html'], height=950, scrolling=True)
    st.divider()

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
        _img_key = f"img_{ticker}_{coupon_pa}_{principal}_{ko_pct}_{ki_pct}_{strike_pct}"
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

        # 儲存到 session_state 供製圖工具使用
        st.session_state[f'stats_{ticker}'] = stats
        st.session_state[f'price_{ticker}'] = {'current_price': current_price}

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

# ══════════════════════════════════════
# 7️⃣  生成網頁結果（永遠顯示）
# ══════════════════════════════════════
if st.session_state.get('fcn_page_html'):
    st.divider()
    st.markdown("## 🌐 公版頁面預覽")
    import base64 as _b64
    _html_content = st.session_state['fcn_page_html']
    components.html(_html_content, height=900, scrolling=True)
    _fn_html = f"FCN公版頁面_{date.today().strftime('%Y%m%d')}.html"
    st.download_button(
        "📥 下載 HTML 檔案（可傳給客戶或上傳至網頁）",
        _html_content, _fn_html, "text/html",
        use_container_width=True,
    )
    if st.button("🗑️ 清除預覽", use_container_width=True):
        del st.session_state['fcn_page_html']
        st.rerun()

# ══════════════════════════════════════
# 8️⃣  製圖工具（永遠顯示）
# ══════════════════════════════════════
st.divider()
st.markdown("## 🖼️ 製圖")

_sections = {
    'header':  True,
    'periods': True,
    'legend':  True,
    'status':  False,
    'stocks':  False,
}

if st.button("🖼️ 開始製圖", type="primary", use_container_width=True):
    _tl = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    _ticker_data = []
    for _t in _tl:
        _s = st.session_state.get(f'stats_{_t}')
        _p = st.session_state.get(f'price_{_t}')
        if _s and _p:
            _ticker_data.append({
                'ticker': _t,
                'current_price': _p['current_price'],
                'safety_prob':   _s['safety_prob'],
                'positive_prob': _s['positive_prob'],
            })
    try:
        _img = generate_fcn_image(
            _tl, ko_pct, ki_pct, strike_pct,
            coupon_pa, monthly_coupon_usd, monthly_coupon_twd, fx_rate,
            principal, first_obs_date, last_obs_date,
            filled_periods, ticker_data=_ticker_data or None,
            sections=_sections, period_months=period_months,
        )
        import base64 as _b64
        _b64_str = _b64.b64encode(_img).decode()
        _fn = f"FCN客戶圖_{date.today().strftime('%Y%m%d')}.png"
        st.markdown(
            f'<a href="data:image/png;base64,{_b64_str}" download="{_fn}" '
            f'style="display:block;width:100%;text-align:center;padding:12px;'
            f'background:#1e3a5f;color:white;border-radius:8px;font-weight:bold;'
            f'text-decoration:none;font-size:1.05em;">📥 下載客戶圖片</a>',
            unsafe_allow_html=True,
        )
        st.success("圖片已產出，點上方連結下載。")
    except Exception as e:
        st.error(f"製圖失敗：{e}")

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
