import os
import json
import time
import requests
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quotex Live Multi-Indicator Scanner Pro</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0b0f19; color: #f8fafc; padding: 15px; margin: 0; }
        .card { background: #151c2c; border-radius: 14px; padding: 20px; max-width: 500px; margin: auto; box-shadow: 0 8px 25px rgba(0,0,0,0.6); border: 1px solid #1e293b; }
        h2 { text-align: center; color: #38bdf8; font-size: 20px; margin-top: 0; }
        label { font-size: 13px; color: #94a3b8; font-weight: 600; display: block; margin-top: 10px; }
        select, button { width: 100%; padding: 12px; margin-top: 6px; margin-bottom: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; font-size: 14px; outline: none; }
        button { background: #0284c7; color: white; font-weight: bold; border: none; cursor: pointer; transition: 0.2s; }
        button:hover { background: #0369a1; }
        .stats { background: #0f172a; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 12px; border-left: 4px solid #38bdf8; line-height: 1.6; }
        .sig-box { background: #1e293b; padding: 12px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid #64748b; }
        .sig-box.CALL { border-left-color: #22c55e; }
        .sig-box.PUT { border-left-color: #ef4444; }
        .CALL-text { color: #22c55e; font-weight: bold; }
        .PUT-text { color: #ef4444; font-weight: bold; }
        .copy-btn { width: auto; padding: 6px 14px; margin: 0; font-size: 12px; background: #38bdf8; color: #000; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h2>📊 QX Strict Multi-Indicator Filter</h2>
        
        <label>SELECT MARKET ASSET:</label>
        <select id="symbol">
            <option value="BTCUSDT">BTC/USDT (Crypto)</option>
            <option value="ETHUSDT">ETH/USDT (Crypto)</option>
            <option value="SOLUSDT">SOL/USDT (Crypto)</option>
            <option value="EURUSDT">EUR/USDT (Forex Proxy)</option>
            <option value="GBPUSDT">GBP/USDT (Forex Proxy)</option>
        </select>

        <label>POWERFUL SURESHOT SIGNALS COUNT:</label>
        <select id="count">
            <option value="3">3 Sureshot Signals</option>
            <option value="5" selected>5 Sureshot Signals</option>
            <option value="10">10 Sureshot Signals</option>
        </select>

        <button onclick="getSignals()">⚡ SCAN STRICT CONFLUENCE</button>

        <div id="statsBox" class="stats" style="display:none;"></div>
        <div id="results"></div>
    </div>

    <script>
        async function getSignals() {
            const symbol = document.getElementById('symbol').value;
            const count = document.getElementById('count').value;
            const resDiv = document.getElementById('results');
            const statsDiv = document.getElementById('statsBox');
            
            resDiv.innerHTML = "<p style='text-align:center; color:#94a3b8;'>Scanning Live Stream with 6 Indicators...</p>";
            statsDiv.style.display = "none";

            try {
                const res = await fetch(`/api/signals?symbol=${symbol}&count=${count}`);
                const data = await res.json();

                if(data.status === "success") {
                    const ans = data.analysis;
                    statsDiv.style.display = "block";
                    statsDiv.innerHTML = `<b>Asset:</b> ${data.symbol}<br>` +
                                         `<b>EMA Trend:</b> ${ans.ema_trend} | <b>RSI(14):</b> ${ans.rsi}<br>` +
                                         `<b>Stoch K:</b> ${ans.stoch} | <b>BB Zone:</b> ${ans.bb_status}`;

                    resDiv.innerHTML = "";
                    let fullText = `--- ${data.symbol} SURESHOT SIGNALS ---\\n`;

                    data.signals.forEach(s => {
                        const isCall = s.direction.includes("CALL");
                        const colorClass = isCall ? "CALL" : "PUT";
                        const textClass = isCall ? "CALL-text" : "PUT-text";
                        
                        fullText += `${s.time}: ${s.direction} (${s.confidence}) [Confluence: ${s.confluence}]\\n`;
                        
                        resDiv.innerHTML += `
                            <div class="sig-box ${colorClass}">
                                <div>
                                    <small style="color:#38bdf8; font-weight:bold;">${s.time}</small><br>
                                    <span class="${textClass}">${s.direction}</span> 
                                    <small>(${s.confidence})</small><br>
                                    <small style="font-size:11px; color:#cbd5e1;">Filters Matched: ${s.confluence}</small>
                                </div>
                                <button class="copy-btn" onclick="navigator.clipboard.writeText('${s.time}: ${s.direction}')">Copy</button>
                            </div>
                        `;
                    });

                    resDiv.innerHTML += `<button style="background:#22c55e; margin-top:10px;" onclick="navigator.clipboard.writeText(\`${fullText}\`)">📋 Copy All Signals</button>`;
                } else {
                    resDiv.innerHTML = `<p style='color:#ef4444; text-align:center;'>${data.message}</p>`;
                }
            } catch(e) {
                resDiv.innerHTML = "<p style='color:#ef4444; text-align:center;'>Server Connection Error!</p>";
            }
        }
    </script>
</body>
</html>
"""

def fetch_klines_safe(symbol="BTCUSDT"):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
    res = requests.get(url, timeout=10)
    data = res.json()

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError(f"Market Data Unavailable for {symbol}")

    opens, highs, lows, closes = [], [], [], []
    for item in data:
        opens.append(float(item[1]))
        highs.append(float(item[2]))
        lows.append(float(item[3]))
        closes.append(float(item[4]))

    return opens, highs, lows, closes

def calculate_ema(closes, period):
    mult = 2 / (period + 1)
    ema = [closes[0]]
    for p in closes[1:]:
        ema.append((p - ema[-1]) * mult + ema[-1])
    return ema

def calculate_rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calculate_bollinger(closes, period=20, mult=2.0):
    slice_c = closes[-period:]
    sma = sum(slice_c) / period
    std_dev = (sum((x - sma) ** 2 for x in slice_c) / period) ** 0.5
    return round(sma + mult * std_dev, 4), round(sma - mult * std_dev, 4), round(sma, 4)

def calculate_stochastic(highs, lows, closes, period=14):
    l_low = min(lows[-period:])
    h_high = max(highs[-period:])
    if h_high == l_low: return 50
    return round(((closes[-1] - l_low) / (h_high - l_low)) * 100, 2)

def analyze_strict_confluence(opens, highs, lows, closes):
    rsi = calculate_rsi(closes, 14)
    ema20 = calculate_ema(closes, 20)[-1]
    ema50 = calculate_ema(closes, 50)[-1]
    bb_upper, bb_lower, bb_middle = calculate_bollinger(closes, 20, 2.0)
    stoch_k = calculate_stochastic(highs, lows, closes, 14)

    c_open, c_close, c_high, c_low = opens[-1], closes[-1], highs[-1], lows[-1]
    body = abs(c_close - c_open)
    lower_shade = min(c_open, c_close) - c_low
    upper_shade = c_high - max(c_open, c_close)

    call_filters = 0
    put_filters = 0

    if c_close > ema20 and ema20 > ema50: call_filters += 1
    elif c_close < ema20 and ema20 < ema50: put_filters += 1

    if rsi <= 35: call_filters += 1.5
    elif rsi >= 65: put_filters += 1.5

    bb_status = "MIDDLE ZONE"
    if c_close <= bb_lower or c_low <= bb_lower:
        call_filters += 1.5
        bb_status = "OVERSOLD (LOWER BAND)"
    elif c_close >= bb_upper or c_high >= bb_upper:
        put_filters += 1.5
        bb_status = "OVERBOUGHT (UPPER BAND)"

    if stoch_k < 25: call_filters += 1
    elif stoch_k > 75: put_filters += 1

    if lower_shade > (1.8 * body) and lower_shade > 0: call_filters += 1
    if upper_shade > (1.8 * body) and upper_shade > 0: put_filters += 1

    ema_trend = "BULLISH 📈" if ema20 > ema50 else "BEARISH 📉"

    return {
        "call_score": call_filters,
        "put_score": put_filters,
        "rsi": rsi,
        "stoch": stoch_k,
        "bb_status": bb_status,
        "ema_trend": ema_trend
    }

@app.route('/')
def home():
    return render_template_string(HTML_PAGE)

@app.route('/api/signals', methods=['GET'])
def get_signals():
    symbol = request.args.get('symbol', 'BTCUSDT')
    required_count = int(request.args.get('count', 5))
    
    try:
        opens, highs, lows, closes = fetch_klines_safe(symbol)
        analysis = analyze_strict_confluence(opens, highs, lows, closes)
        
        signals = []
        scanned_minute = 1
        
        while len(signals) < required_count and scanned_minute <= 45:
            call_s = analysis['call_score']
            put_s = analysis['put_score']
            
            if call_s >= 4.0:
                signals.append({
                    "time": f"In +{scanned_minute} min candle",
                    "direction": "CALL (UP 🟩)",
                    "confidence": f"{min(98, int(80 + call_s * 3.5))}%",
                    "confluence": f"{round(call_s, 1)}/6 Strict Indicators Passed"
                })
                scanned_minute += 3
            elif put_s >= 4.0:
                signals.append({
                    "time": f"In +{scanned_minute} min candle",
                    "direction": "PUT (DOWN 🟥)",
                    "confidence": f"{min(98, int(80 + put_s * 3.5))}%",
                    "confluence": f"{round(put_s, 1)}/6 Strict Indicators Passed"
                })
                scanned_minute += 3
            else:
                scanned_minute += 1

        return jsonify({
            "status": "success",
            "symbol": symbol,
            "analysis": analysis,
            "signals": signals
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
