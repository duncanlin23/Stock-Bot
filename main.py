import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import time

# 如果有設定環境變數 YF_DEBUG=1，就開啟 yfinance debug log，方便排查429限流/cookie驗證等問題
if os.environ.get("YF_DEBUG") == "1":
    yf.enable_debug_mode()

# =========================
# LINE 推播 function
# =========================
def send_line(msg):
    token = os.environ["LINE_TOKEN"]
    user_id1 = os.environ["USER_ID1"]
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "to": user_id1,
        "messages": [
            {
                "type": "text",
                "text": msg
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    print("STATUS:", response.status_code)
    print("BODY:", response.text)


# =========================
# 共用：帶重試機制的下載 + 驗證
# =========================
def fetch_with_retry(ticker, period="2y", interval="1d", max_retries=5, wait_sec=10):
    """
    下載資料，並驗證資料有效性（非空、Close 非全 NaN）。
    抓不到有效資料時會重試，重試完仍失敗則 raise。
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            df = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=False,  # 用原始收盤價，跟 Yahoo 網頁/一般查價網站數字一致（不做除權息還原）
            )

            # 有些 yfinance 版本在單一 ticker 時仍會回傳 MultiIndex columns，這裡統一攤平
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if df is None or df.empty:
                raise ValueError(f"{ticker} 回傳空 DataFrame（第 {attempt} 次）")

            close_series = df["Close"].dropna()
            if close_series.empty:
                raise ValueError(f"{ticker} 的 Close 欄位全部是 NaN（第 {attempt} 次）")

            return df

        except Exception as e:
            last_error = e
            print(f"[WARN] {ticker} 第 {attempt} 次下載失敗: {e}")
            if attempt < max_retries:
                time.sleep(wait_sec)

    raise RuntimeError(f"{ticker} 重試 {max_retries} 次後仍失敗: {last_error}")


def keep_only_completed_days(df, market_tz):
    """
    過濾掉「今天」這筆資料（如果市場還在盤中或當天資料尚未定案），
    只保留已經確定收盤的交易日，避免抓到即時跳動的盤中價格。
    """
    idx = df.index
    today_market = pd.Timestamp.now(tz=market_tz).normalize()

    if idx.tz is None:
        idx_market = idx.tz_localize(market_tz)
    else:
        idx_market = idx.tz_convert(market_tz)

    mask = idx_market.normalize() < today_market
    return df[mask]


def compute_close_ma_dev(hist_df, recent_df, ticker_name, market_tz, max_stale_days=1):
    """
    回傳: close, ma200, dev, last_date, is_stale
    is_stale=True 代表資料距今超過 max_stale_days 個交易日，可能不是最新收盤價，
    但仍然會照算、照回傳，不會擋掉——由呼叫端決定要不要在訊息裡標註警告。
    """
    recent_completed = keep_only_completed_days(recent_df, market_tz)
    hist_completed = keep_only_completed_days(hist_df, market_tz)

    recent_close = recent_completed["Close"].dropna()
    if recent_close.empty:
        raise ValueError(f"{ticker_name} 沒有有效的『已收盤』最新價（可能還在盤中，或還沒有已完成的交易日資料）")

    last_date = recent_close.index[-1]
    if hasattr(last_date, "to_pydatetime"):
        last_date = last_date.to_pydatetime()

    # 用「工作日天數」判斷新舊，避免週末造成誤判（例如週一抓到上週五資料，這其實是正常最新的）
    today_naive = pd.Timestamp.now(tz=last_date.tzinfo).normalize()
    last_date_naive = pd.Timestamp(last_date).normalize()
    business_days_old = int(np.busday_count(last_date_naive.date(), today_naive.date()))
    is_stale = business_days_old > max_stale_days

    close = float(recent_close.iloc[-1])

    # 200MA 用大範圍歷史資料算（已濾掉未收盤的今天），200 天前的資料稍舊不影響
    ma_series = hist_completed["Close"].rolling(200).mean().dropna()
    if ma_series.empty:
        raise ValueError(f"{ticker_name} 資料不足以算 200MA（可能資料筆數 < 200）")
    ma200 = float(ma_series.iloc[-1])

    if ma200 == 0:
        raise ValueError(f"{ticker_name} MA200 為 0，無法計算偏離率")

    dev = (close / ma200 - 1) * 100
    return close, ma200, dev, last_date.date(), is_stale


# =========================
# SPY 數據
# =========================
def get_spy_data():
    hist_df = fetch_with_retry("SPY", period="2y")
    recent_df = fetch_with_retry("SPY", period="5d")
    return compute_close_ma_dev(hist_df, recent_df, "SPY", market_tz="America/New_York")


# =========================
# 0050.tw 數據
# =========================
def get_0050tw_data():
    hist_df = fetch_with_retry("0050.TW", period="2y")
    recent_df = fetch_with_retry("0050.TW", period="5d")
    return compute_close_ma_dev(hist_df, recent_df, "0050.TW", market_tz="Asia/Taipei")


def format_block(title, close, ma200, dev, data_date, is_stale):
    warning = "\n⚠️ 非最新收盤價（Yahoo 資料尚未更新，僅供參考）" if is_stale else ""
    return f"""📊 {title}（資料日期：{data_date}）{warning}
收盤價：{close:.2f}
200MA：{ma200:.2f}
偏離率：{dev:.2f}%"""


# =========================
# 主程式
# =========================
if __name__ == "__main__":
    try:
        close, ma200, dev, data_date, is_stale = get_spy_data()
        spy_block = format_block("SPY 技術數據", close, ma200, dev, data_date, is_stale)
    except Exception as e:
        print(f"[ERROR] SPY 抓取失敗: {e}")
        spy_block = f"📊 SPY 技術數據\n⚠️ 資料抓取失敗，已跳過（原因：{e}）"

    try:
        close_0050, ma200_0050, dev_0050, data_date_0050, is_stale_0050 = get_0050tw_data()
        e0050_block = format_block("0050.TW 技術數據", close_0050, ma200_0050, dev_0050, data_date_0050, is_stale_0050)
    except Exception as e:
        print(f"[ERROR] 0050.TW 抓取失敗: {e}")
        e0050_block = f"📊 0050.TW 技術數據\n⚠️ 資料抓取失敗，已跳過（原因：{e}）"

    msg = f"""
{spy_block}

{e0050_block}
"""
    send_line(msg)
