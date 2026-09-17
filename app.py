import os
import time
import requests
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Only real Binance spot pairs. EURUSDT / GBPUSDT don't exist on Binance and
# will 400 on every request, which was silently producing the empty-result bug.
VALID_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

HTML_PAGE = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quotex Live Multi-Indicator Scanner (Fixed)</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0b0f19; color: #f8fafc; padding: 15px; margin: 0; }
        .card { background: #151c2c; border-radius: 14px; padding: 20px; max-width: 500px; margin: auto; box-shadow: 0 8px 25px rgba(0,0,0,0.6); border: 1px solid #1e293b; }
        h2 { text-align: center; color: #38bdf8; font-size: 20px; margin-top: 0; }
        label { font-size: 13px; color: #94a3b8; font-weight: 600; display: block; margin-top: 10px; }
        select, button { width: 100%; padding: 12px; margin-top: 6px; margin-bottom: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; font-size: 14px; outline: none; }
        button { background: #0284c7; color: white; font-weight: bold; border: none; cursor: pointer; transition: 0.2s; }
        button:hover { background: #0369a1; }
        .stats { background: #0f172a; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 12px; border-left: 4px solid #38bdf8; line-height: 1.6; }
        .sig-box { background: #1e293b; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #64748b; }
        .sig-box.CALL { border-left-color: #22c55e; }
        .sig-box.PUT { border-left-color: #ef4444; }
        .sig-box.NONE { border-left-color: #64748b; }
        .CALL-text { color: #22c55e; font-weight: bold; }
        .PUT-text { color: #ef4444; font-weight: bold; }
        .warn { font-size: 11px; color: #fbbf24; margin-top: 14px; line-height: 1.5; border-top: 1px solid #1e293b; padding-top: 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>📊 QX Multi-Indicator Read (current moment only)</h2>

        <label>SELECT MARKET ASSET:</label>
        <select id="symbol">
            <option value="BTCUSDT">BTC/USDT</option>
            <option value="ETHUSDT">ETH/USDT</option>
            <option value="SOLUSDT">SOL/USDT</option>
        </select>

        <button onclick="getSignal()">⚡ READ CURRENT CONFLUENCE</button>

        <div id="statsBox" class="stats" style="display:none;"></div>
        <div id="results"></div>

        <div class="warn">
            This reads indicators for the candle that has already closed. It is a
            snapshot of current conditions, not a verified prediction of the next
            candle. Confluence score is real math; it has not been backtested for
            accuracy on this data. Treat any single reading as informational, not
            as a trade instruction.
        </div>
    </div>

    <script>
        async function getSignal() {
            const symbol = document.getElementById('symbol').value;
            const resDiv = document.getElementById('results');
            const statsDiv = document.getElementById('statsBox');

            resDiv.innerHTML = "<p style='text-align:center; color:#94a3b8;'>Fetching live candles...</p>";
            statsDiv.style.display = "none";

            try {
                const res = await fetch(`/api/signals?symbol=${symbol}`);
                const data = await res.json();

                if (data.status === "success") {
                    const ans = data.analysis;
                    statsDiv.style.display = "block";
                    statsDiv.innerHTML = `<b>Asset:</b> ${data.symbol} &middot; <b>Last close:</b> ${data.last_close}<br>` +
                                         `<b>EMA Trend:</b> ${ans.ema_trend} | <b>RSI(14):</b> ${ans.rsi}<br>` +
                                         `<b>Stoch K:</b> ${ans.stoch} | <b>BB Zone:</b> ${ans.bb_status}`;

                    const s = data.signal;
                    const colorClass = s.direction === "CALL" ? "CALL" : (s.direction === "PUT" ? "PUT" : "NONE");
                    const textClass = s.direction === "CALL" ? "CALL-text" : (s.direction === "PUT" ? "PUT-text" : "");

                    resDiv.innerHTML = `
                        <div class="sig-box ${colorClass}">
                            <span class="${textClass}">${s.direction === "NONE" ? "No confluence reached" : s.direction}</span><br>
                            <small style="color:#cbd5e1;">Confluence score — CALL: ${s.call_score}/6, PUT: ${s.put_score}/6</small>
                        </div>`;
                } else {
                    resDiv.innerHTML = `<p style='color:#ef4444; text-align:center;'>${data.message}</p>`;
                }
            } catch (e) {
                resDiv.innerHTML = "<p style='color:#ef4444; text-align:center;'>Server connection error.</p>";
            }
        }
    </script>
</body>
</html>
"""


def fetch_klines_safe(symbol="BTCUSDT"):
    if symbol not in VALID_SYMBOLS:
        raise ValueError(f"'{symbol}' is not a supported Binance pair. Choose one of {VALID_SYMBOLS}.")

    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    data = res.json()

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError(f"Market data unavailable for {symbol}")

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
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
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
    if h_high == l_low:
        return 50
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

    call_filters = 0.0
    put_filters = 0.0

    if c_close > ema20 and ema20 > ema50:
        call_filters += 1
    elif c_close < ema20 and ema20 < ema50:
        put_filters += 1

    if rsi <= 35:
        call_filters += 1.5
    elif rsi >= 65:
        put_filters += 1.5

    bb_status = "MIDDLE ZONE"
    if c_close <= bb_lower or c_low <= bb_lower:
        call_filters += 1.5
        bb_status = "OVERSOLD (LOWER BAND)"
    elif c_close >= bb_upper or c_high >= bb_upper:
        put_filters += 1.5
        bb_status = "OVERBOUGHT (UPPER BAND)"

    if stoch_k < 25:
        call_filters += 1
    elif stoch_k > 75:
        put_filters += 1

    if lower_shade > (1.8 * body) and lower_shade > 0:
        call_filters += 1
    if upper_shade > (1.8 * body) and upper_shade > 0:
        put_filters += 1

    ema_trend = "BULLISH" if ema20 > ema50 else "BEARISH"

    return {
        "call_score": round(call_filters, 1),
        "put_score": round(put_filters, 1),
        "rsi": rsi,
        "stoch": stoch_k,
        "bb_status": bb_status,
        "ema_trend": ema_trend,
    }


@app.route('/')
def home():
    return render_template_string(HTML_PAGE)


@app.route('/api/signals', methods=['GET'])
def get_signals():
    symbol = request.args.get('symbol', 'BTCUSDT')

    try:
        opens, highs, lows, closes = fetch_klines_safe(symbol)
        analysis = analyze_strict_confluence(opens, highs, lows, closes)

        # One honest read of the current, already-closed candle. We do NOT
        # fabricate a series of future-minute signals from a single snapshot —
        # that would require re-fetching live data at each future timestamp,
        # which this synchronous request can't actually do.
        threshold = 4.0
        if analysis['call_score'] >= threshold:
            direction = "CALL"
        elif analysis['put_score'] >= threshold:
            direction = "PUT"
        else:
            direction = "NONE"

        return jsonify({
            "status": "success",
            "symbol": symbol,
            "last_close": closes[-1],
            "analysis": analysis,
            "signal": {
                "direction": direction,
                "call_score": analysis['call_score'],
                "put_score": analysis['put_score'],
            },
        })

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except requests.RequestException:
        return jsonify({"status": "error", "message": "Could not reach Binance API."}), 502
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
