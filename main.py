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

    response = requests.post(url, headers=headers, json=data)
    print("STATUS:", response.status_code)
    print("BODY:", response.text)
    

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
# 0050.tw 數據
# =========================
def get_0050tw_data():
   df = yf.download("0050.TW", period="2y", interval="1d")

   if df.empty:
       raise ValueError("0050 沒抓到資料（Yahoo API 回空）")

   close = df["Close"].dropna().iloc[-1]
   close = close.item() if hasattr(close, "item") else float(close)
    
   ma_series = df["Close"].rolling(200).mean()
   ma200 = ma_series.iloc[-1]
   ma200 = ma200.item() if hasattr(ma200, "item") else float(ma200)

   dev = (close / ma200 - 1) * 100
   print(f"0050 收盤: {close:.2f}, MA200: {ma200:.2f}, 偏離: {dev:.2f}%")
   print(df.tail())

   return close, ma200, dev

# =========================
# 主程式
# =========================
if __name__ == "__main__":
    close, ma200, dev = get_spy_data()
    close_0050, ma200_0050, dev_0050 = get_0050tw_data()

    msg = f"""
📊 SPY 技術數據

收盤價：{close:.2f}
200MA：{ma200:.2f}
偏離率：{dev:.2f}%

📊 0050.TW 技術數據

收盤價：{close_0050:.2f}
200MA：{ma200_0050:.2f}
偏離率：{dev_0050:.2f}%
"""

    #send_line(msg)
    
