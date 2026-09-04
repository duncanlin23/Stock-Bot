import yfinance as yf
import pandas as pd
import requests
import os
import time

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
def fetch_with_retry(ticker, period="2y", interval="1d", max_retries=3, wait_sec=5):
    """
    下載資料，並驗證資料有效性（非空、Close 非全 NaN、最後一筆非 NaN）。
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
                auto_adjust=True,   # 明確指定，避免新舊版 yfinance 預設值不同造成欄位差異
            )

            # 有些 yfinance 版本在單一 ticker 時仍會回傳 MultiIndex columns，這裡統一攤平
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if df is None or df.empty:
                raise ValueError(f"{ticker} 回傳空 DataFrame（第 {attempt} 次）")

            # 去掉 Close 是 NaN 的尾端資料列，取最後一筆「有效」收盤價
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


def compute_close_ma_dev(df, ticker_name):
    close_series = df["Close"].dropna()
    if close_series.empty:
        raise ValueError(f"{ticker_name} 沒有有效收盤價")
    close = float(close_series.iloc[-1])

    ma_series = df["Close"].rolling(200).mean().dropna()
    if ma_series.empty:
        raise ValueError(f"{ticker_name} 資料不足以算 200MA（可能資料筆數 < 200）")
    ma200 = float(ma_series.iloc[-1])

    if ma200 == 0:
        raise ValueError(f"{ticker_name} MA200 為 0，無法計算偏離率")

    dev = (close / ma200 - 1) * 100
    return close, ma200, dev


# =========================
# SPY 數據
# =========================
def get_spy_data():
    df = fetch_with_retry("SPY")
    return compute_close_ma_dev(df, "SPY")


# =========================
# 0050.tw 數據
# =========================
def get_0050tw_data():
    df = fetch_with_retry("0050.TW")
    return compute_close_ma_dev(df, "0050.TW")


# =========================
# 主程式
# =========================
if __name__ == "__main__":
    try:
        close, ma200, dev = get_spy_data()
        spy_block = f"""📊 SPY 技術數據
收盤價：{close:.2f}
200MA：{ma200:.2f}
偏離率：{dev:.2f}%"""
    except Exception as e:
        print(f"[ERROR] SPY 抓取失敗: {e}")
        spy_block = f"📊 SPY 技術數據\n⚠️ 資料抓取失敗，已跳過（原因：{e}）"

    try:
        close_0050, ma200_0050, dev_0050 = get_0050tw_data()
        e0050_block = f"""📊 0050.TW 技術數據
收盤價：{close_0050:.2f}
200MA：{ma200_0050:.2f}
偏離率：{dev_0050:.2f}%"""
    except Exception as e:
        print(f"[ERROR] 0050.TW 抓取失敗: {e}")
        e0050_block = f"📊 0050.TW 技術數據\n⚠️ 資料抓取失敗，已跳過（原因：{e}）"

    msg = f"""
{spy_block}

{e0050_block}
"""
    send_line(msg)
