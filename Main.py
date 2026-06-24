import yfinance as yf
import pandas as pd
import requests
import os

# ===== LINE 推播 =====
def send_line(msg):
    token = os.environ["LINE_TOKEN"]
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": msg}
    requests.post(url, headers=headers, data=data)

# ===== 取得 SPY 數據 =====
def get_spy_data():
    df = yf.download("SPY", period="2y", interval="1d")

    close = df["Close"].iloc[-1]          # 最新收盤價
    ma200 = df["Close"].rolling(200).mean().iloc[-1]  # 200MA

    deviation = (close / ma200 - 1) * 100  # %

    return close, ma200, deviation

# ===== 主程式 =====
if __name__ == "__main__":
    close, ma200, dev = get_spy_data()

    msg = f"""
📊 SPY 技術數據

收盤價：{close:.2f}
200MA：{ma200:.2f}
偏離率：{dev:.2f}%

"""

    send_line(msg)
