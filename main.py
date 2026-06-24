import yfinance as yf
import pandas as pd
import requests
import os

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

    requests.post(url, headers=headers, json=data)

# =========================
# SPY 數據
# =========================
def get_spy_data():
    df = yf.download("SPY", period="2y", interval="1d")

   close = df["Close"].iloc[-1]
   close = close.item() if hasattr(close, "item") else float(close)
   ma_series = df["Close"].rolling(200).mean()
   ma200 = ma_series.iloc[-1]
   ma200 = ma200.item() if hasattr(ma200, "item") else float(ma200)

   dev = (close / ma200 - 1) * 100

    return close, ma200, dev

# =========================
# 主程式
# =========================
if __name__ == "__main__":
    close, ma200, dev = get_spy_data()

    msg = f"""
📊 SPY 技術數據

收盤價：{close:.2f}
200MA：{ma200:.2f}
偏離率：{dev:.2f}%
"""

    send_line(msg)
