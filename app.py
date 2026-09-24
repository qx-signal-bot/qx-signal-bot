import os
import time
import requests
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- Crypto: Kraken (no key needed, works 24/7, no geo-block issues) ---
KRAKEN_PAIR_MAP = {
    "BTCUSDT": "XBTUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD",
}

# --- Real forex majors: Twelve Data (needs a free API key) ---
# These are REAL interbank forex prices, only available during real forex
# market hours (closed weekends). They are NOT the same feed as Quotex's
# OTC pairs, which are Quotex's own synthetic price generator and run 24/7.
# Set TWELVE_DATA_API_KEY as an environment variable on Render to enable these.
TWELVE_DATA_PAIR_MAP = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "USDCHF": "USD/CHF",
    "USDCAD": "USD/CAD",
    "NZDUSD": "NZD/USD",
    "EURGBP": "EUR/GBP",
    "EURJPY": "EUR/JPY",
    "GBPJPY": "GBP/JPY",
    "AUDJPY": "AUD/JPY",
    "EURAUD": "EUR/AUD",
    "USDSGD": "USD/SGD",
    "USDZAR": "USD/ZAR",
}
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")

ASSET_TYPE = {}
for _s in KRAKEN_PAIR_MAP:
    ASSET_TYPE[_s] = "crypto"
for _s in TWELVE_DATA_PAIR_MAP:
    ASSET_TYPE[_s] = "forex"

VALID_SYMBOLS = list(ASSET_TYPE.keys())

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
        h2 { text-align: center; color: #38bdf8; font-size: 19px; margin-top: 0; }
        label { font-size: 13px; color: #94a3b8; font-weight: 600; display: block; margin-top: 10px; }
        select, button { width: 100%; padding: 12px; margin-top: 6px; margin-bottom: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; font-size: 14px; outline: none; }
        button { background: #0284c7; color: white; font-weight: bold; border: none; cursor: pointer; transition: 0.2s; }
        button:hover { background: #0369a1; }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        .toggle-row { display: flex; align-items: center; justify-content: space-between; margin: 10px 0; }
        .toggle-row label { margin: 0; }
        .stats { background: #0f172a; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 12px; border-left: 4px solid #38bdf8; line-height: 1.6; }
        .sig-box { background: #1e293b; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #64748b; }
        .sig-box.CALL { border-left-color: #22c55e; }
        .sig-box.PUT { border-left-color: #ef4444; }
        .sig-box.NONE { border-left-color: #64748b; }
        .CALL-text { color: #22c55e; font-weight: bold; }
        .PUT-text { color: #ef4444; font-weight: bold; }
        .track-record { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; margin-bottom: 15px; }
        .track-record h3 { font-size: 13px; color: #94a3b8; margin: 0 0 8px; font-weight: 600; }
        .tr-stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; }
        .tr-stat .num { font-size: 18px; font-weight: 700; }
        .tr-stat .lbl { font-size: 10px; color: #64748b; margin-top: 2px; }
        .tr-win { color: #22c55e; } .tr-loss { color: #ef4444; } .tr-neutral { color: #94a3b8; }
        table.log { width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 10px; }
        table.log th, table.log td { text-align: left; padding: 5px 3px; border-bottom: 1px solid #1e293b; }
        table.log th { color: #64748b; font-weight: 500; }
        .reset-btn { background: #334155; font-size: 12px; padding: 8px; margin-top: 4px; }
        .warn { font-size: 11px; color: #fbbf24; margin-top: 14px; line-height: 1.5; border-top: 1px solid #1e293b; padding-top: 10px; }
        .status-line { font-size: 11px; color: #64748b; text-align: center; margin: -6px 0 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>📊 QX Multi-Indicator Read — Live Track Record</h2>

        <label>SELECT MARKET ASSET:</label>
        <select id="symbol" onchange="onSymbolChange()">
            <optgroup label="Crypto (24/7)">
                <option value="BTCUSDT">BTC/USDT</option>
                <option value="ETHUSDT">ETH/USDT</option>
                <option value="SOLUSDT">SOL/USDT</option>
            </optgroup>
            <optgroup label="Real forex majors (market hours only)">
                <option value="EURUSD">EUR/USD</option>
                <option value="GBPUSD">GBP/USD</option>
                <option value="USDJPY">USD/JPY</option>
                <option value="AUDUSD">AUD/USD</option>
                <option value="USDCHF">USD/CHF</option>
                <option value="USDCAD">USD/CAD</option>
                <option value="NZDUSD">NZD/USD</option>
            </optgroup>
            <optgroup label="Real forex crosses (market hours only)">
                <option value="EURGBP">EUR/GBP</option>
                <option value="EURJPY">EUR/JPY</option>
                <option value="GBPJPY">GBP/JPY</option>
                <option value="AUDJPY">AUD/JPY</option>
                <option value="EURAUD">EUR/AUD</option>
                <option value="USDSGD">USD/SGD</option>
                <option value="USDZAR">USD/ZAR</option>
            </optgroup>
        </select>
        <div class="status-line" style="margin-top:-2px;">
            Forex pairs are real interbank data — different from Quotex's OTC feed,
            and only return data while the real forex market is open (closed weekends).
        </div>

        <div class="toggle-row">
            <label style="margin:0;">Auto-refresh every 60s (M1 timeframe)</label>
            <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()" style="width:auto; margin:0;">
        </div>

        <label>Confluence threshold (indicators needed out of 7): <span id="thresholdVal">4.0</span></label>
        <input type="range" id="thresholdSlider" min="1.5" max="7" step="0.5" value="4"
               oninput="onThresholdChange()" style="width:100%; margin-bottom:6px;">
        <div class="status-line" style="margin-top:-2px;">Lower = more signals, weaker agreement between indicators. Higher = fewer signals, stronger agreement.</div>

        <label>Resolve after (candles held):</label>
        <select id="holdSelect" onchange="onHoldChange()">
            <option value="1">1 candle (~1 min)</option>
            <option value="3">3 candles (~3 min)</option>
            <option value="5">5 candles (~5 min)</option>
        </select>
        <div class="status-line" style="margin-top:-2px;">Only accurate with auto-refresh ON — manual clicks aren't spaced 1 minute apart, so hold-length counting won't line up.</div>

        <button onclick="getSignal()" id="manualBtn">⚡ READ CURRENT CONFLUENCE</button>
        <div class="status-line" id="nextRefreshLine"></div>

        <div class="track-record">
            <h3>Honest track record — this asset, threshold <span id="trThresholdLabel">4.0</span>, hold <span id="trHoldLabel">1</span> candle(s)</h3>
            <div class="tr-stat-grid">
                <div class="tr-stat"><div class="num tr-neutral" id="trTotal">0</div><div class="lbl">Resolved</div></div>
                <div class="tr-stat"><div class="num tr-win" id="trWins">0</div><div class="lbl">Correct</div></div>
                <div class="tr-stat"><div class="num" id="trRate">—</div><div class="lbl">Win rate</div></div>
            </div>
            <button class="reset-btn" onclick="resetTrackRecord()">Reset track record for this asset</button>
            <button class="reset-btn" style="background:#0f766e; margin-top:6px;" onclick="exportTrackRecordCSV()">⬇ Export this track record as CSV</button>
            <button class="reset-btn" style="background:#0284c7; margin-top:6px;" onclick="exportCSV()">Export full history as CSV</button>
        </div>

        <div id="statsBox" class="stats" style="display:none;"></div>
        <div id="results"></div>

        <table class="log" id="logTable" style="display:none;">
            <thead><tr><th>Time</th><th>Signal</th><th>Score</th><th>Outcome</th></tr></thead>
            <tbody id="logBody"></tbody>
        </table>

        <div class="warn">
            Every row here is a real, timestamped reading against live Kraken data —
            not a fabricated list of future minutes. "Outcome" is filled in only once
            the next real candle actually closes, by comparing the new price to the
            price at signal time. Nothing here is guaranteed; this is a track record
            you build and judge for yourself, not a promise of accuracy.
        </div>
    </div>

    <script>
        let refreshTimer = null;
        let pendingQueue = []; // [{symbol, direction, close, call_score, put_score, threshold, holdCandles, candlesLeft, timeLabel}]

        function currentThreshold() {
            return parseFloat(document.getElementById('thresholdSlider').value);
        }

        function currentHold() {
            return parseInt(document.getElementById('holdSelect').value);
        }

        function decideDirection(callScore, putScore, threshold) {
            if (callScore >= threshold) return 'CALL';
            if (putScore >= threshold) return 'PUT';
            return 'NONE';
        }

        function onThresholdChange() {
            const t = currentThreshold().toFixed(1);
            document.getElementById('thresholdVal').textContent = t;
            document.getElementById('trThresholdLabel').textContent = t;
            renderTrackRecord(document.getElementById('symbol').value);
        }

        function exportCSV() {
            const symbol = document.getElementById('symbol').value;
            const history = loadHistory(symbol).filter(h => h.resolved);
            if (history.length === 0) { alert('No resolved signals yet for this asset.'); return; }

            const headers = ['time', 'symbol', 'direction', 'call_score', 'put_score', 'threshold', 'hold_candles', 'reasons', 'outcome'];
            const rows = history.map(h => [
                h.timeLabel, symbol, h.direction, h.call_score, h.put_score,
                h.threshold, h.holdCandles, (h.reasons || []).join('; '), h.won ? 'WIN' : 'LOSS'
            ]);
            const csv = [headers.join(',')].concat(
                rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
            ).join('\n');

            const blob = new Blob([csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `qx_track_${symbol}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        function onHoldChange() {
            document.getElementById('trHoldLabel').textContent = currentHold();
            renderTrackRecord(document.getElementById('symbol').value);
        }

        function storageKey(symbol) { return `qx_track_${symbol}`; }

        function loadHistory(symbol) {
            try {
                const raw = localStorage.getItem(storageKey(symbol));
                return raw ? JSON.parse(raw) : [];
            } catch (e) { return []; }
        }

        function saveHistory(symbol, history) {
            try { localStorage.setItem(storageKey(symbol), JSON.stringify(history)); } catch (e) {}
        }

        function resetTrackRecord() {
            const symbol = document.getElementById('symbol').value;
            localStorage.removeItem(storageKey(symbol));
            pendingQueue = pendingQueue.filter(p => p.symbol !== symbol);
            renderTrackRecord(symbol);
        }

        function exportTrackRecordCSV() {
            const symbol = document.getElementById('symbol').value;
            const history = loadHistory(symbol).filter(h => h.resolved);
            if (history.length === 0) { alert('No resolved signals yet for this asset.'); return; }

            const header = 'time,symbol,direction,call_score,put_score,threshold,hold_candles,outcome\n';
            const rows = history.map(h =>
                [h.timeLabel, symbol, h.direction, h.call_score, h.put_score, h.threshold, h.holdCandles, h.won ? 'WIN' : 'LOSS'].join(',')
            ).join('\n');

            const blob = new Blob([header + rows], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `qx_track_${symbol}_${Date.now()}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        function onSymbolChange() {
            pendingQueue = [];
            const symbol = document.getElementById('symbol').value;
            renderTrackRecord(symbol);
            document.getElementById('results').innerHTML = '';
            document.getElementById('statsBox').style.display = 'none';
        }

        function renderTrackRecord(symbol) {
            const threshold = currentThreshold();
            const hold = currentHold();
            // Only compare readings taken at the SAME threshold AND hold length —
            // mixing settings would make the win rate meaningless.
            const history = loadHistory(symbol).filter(
                h => h.resolved && h.threshold === threshold && h.holdCandles === hold
            );
            const total = history.length;
            const wins = history.filter(h => h.won).length;
            document.getElementById('trTotal').textContent = total;
            document.getElementById('trWins').textContent = wins;
            document.getElementById('trRate').textContent = total > 0 ? ((wins / total) * 100).toFixed(1) + '%' : '—';

            const logBody = document.getElementById('logBody');
            const logTable = document.getElementById('logTable');
            if (total === 0) { logTable.style.display = 'none'; return; }
            logTable.style.display = 'table';
            logBody.innerHTML = '';
            history.slice(-15).reverse().forEach(h => {
                const tr = document.createElement('tr');
                const outcomeColor = h.won ? '#22c55e' : '#ef4444';
                tr.innerHTML = `<td>${h.timeLabel}</td><td>${h.direction}</td><td>${h.call_score}/${h.put_score}</td>` +
                                `<td style="color:${outcomeColor}">${h.won ? 'WIN' : 'LOSS'}</td>`;
                logBody.appendChild(tr);
            });
        }

        // Every fetch = roughly one closed candle (when auto-refresh is on).
        // Decrement every queued signal for this symbol; resolve any that have
        // now waited out their full hold length, using the fresh close price.
        function tickAndResolve(symbol, newClose) {
            const stillPending = [];
            for (const p of pendingQueue) {
                if (p.symbol !== symbol) { stillPending.push(p); continue; }
                p.candlesLeft -= 1;
                if (p.candlesLeft > 0) { stillPending.push(p); continue; }

                if (p.direction !== 'NONE') {
                    const won = p.direction === 'CALL' ? newClose > p.close : newClose < p.close;
                    const history = loadHistory(symbol);
                    history.push({
                        timeLabel: p.timeLabel,
                        direction: p.direction,
                        call_score: p.call_score,
                        put_score: p.put_score,
                        reasons: p.reasons || [],
                        threshold: p.threshold,
                        holdCandles: p.holdCandles,
                        resolved: true,
                        won: won,
                    });
                    saveHistory(symbol, history.slice(-500));
                }
                // NONE readings are just dropped — nothing to resolve.
            }
            pendingQueue = stillPending;
        }

        async function getSignal() {
            const symbol = document.getElementById('symbol').value;
            const threshold = currentThreshold();
            const hold = currentHold();
            const resDiv = document.getElementById('results');
            const statsDiv = document.getElementById('statsBox');

            try {
                const res = await fetch(`/api/signals?symbol=${symbol}`);
                const data = await res.json();

                if (data.status === "success") {
                    // Age and resolve anything already in the queue for this symbol.
                    tickAndResolve(symbol, data.last_close);

                    const ans = data.analysis;
                    statsDiv.style.display = "block";
                    statsDiv.innerHTML = `<b>Asset:</b> ${data.symbol} &middot; <b>Last close:</b> ${data.last_close}<br>` +
                                         `<b>EMA Trend:</b> ${ans.ema_trend} | <b>RSI(14):</b> ${ans.rsi} | <b>MACD:</b> ${ans.macd_trend}<br>` +
                                         `<b>Stoch K:</b> ${ans.stoch} | <b>BB Zone:</b> ${ans.bb_status}`;

                    // Direction is decided HERE, client-side, from the raw scores
                    // and whatever threshold the slider is set to right now.
                    const callScore = data.signal.call_score;
                    const putScore = data.signal.put_score;
                    const callReasons = data.signal.call_reasons || [];
                    const putReasons = data.signal.put_reasons || [];
                    const direction = decideDirection(callScore, putScore, threshold);
                    const activeReasons = direction === 'CALL' ? callReasons : (direction === 'PUT' ? putReasons : []);

                    const colorClass = direction === "CALL" ? "CALL" : (direction === "PUT" ? "PUT" : "NONE");
                    const textClass = direction === "CALL" ? "CALL-text" : (direction === "PUT" ? "PUT-text" : "");
                    const now = new Date();
                    const timeLabel = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                    const reasonsHtml = activeReasons.length > 0
                        ? `<br><small style="color:#94a3b8;">${activeReasons.join(' &middot; ')}</small>` : '';

                    resDiv.innerHTML = `
                        <div class="sig-box ${colorClass}">
                            <span class="${textClass}">${direction === "NONE" ? "No confluence reached" : direction}</span>
                            <small style="color:#64748b;"> &middot; read at ${timeLabel} &middot; threshold ${threshold.toFixed(1)} &middot; hold ${hold}</small><br>
                            <small style="color:#cbd5e1;">Confluence score — CALL: ${callScore}/7, PUT: ${putScore}/7</small>
                            ${reasonsHtml}
                        </div>`;

                    // Queue this reading; it resolves once `hold` more real
                    // fetches (≈ candles) have passed.
                    pendingQueue.push({
                        symbol: symbol,
                        direction: direction,
                        close: data.last_close,
                        call_score: callScore,
                        put_score: putScore,
                        reasons: activeReasons,
                        threshold: threshold,
                        holdCandles: hold,
                        candlesLeft: hold,
                        timeLabel: timeLabel,
                    });

                    renderTrackRecord(symbol);
                } else {
                    resDiv.innerHTML = `<p style='color:#ef4444; text-align:center;'>${data.message}</p>`;
                }
            } catch (e) {
                resDiv.innerHTML = "<p style='color:#ef4444; text-align:center;'>Server connection error.</p>";
            }
        }

        function toggleAutoRefresh() {
            const on = document.getElementById('autoRefresh').checked;
            const manualBtn = document.getElementById('manualBtn');
            if (on) {
                manualBtn.disabled = true;
                getSignal();
                let secondsLeft = 60;
                const lineEl = document.getElementById('nextRefreshLine');
                refreshTimer = setInterval(() => {
                    secondsLeft--;
                    lineEl.textContent = secondsLeft > 0 ? `Next real fetch in ${secondsLeft}s` : 'Fetching...';
                    if (secondsLeft <= 0) {
                        secondsLeft = 60;
                        getSignal();
                    }
                }, 1000);
            } else {
                manualBtn.disabled = false;
                clearInterval(refreshTimer);
                document.getElementById('nextRefreshLine').textContent = '';
            }
        }

        renderTrackRecord(document.getElementById('symbol').value);
    </script>
</body>
</html>
"""


def fetch_klines_kraken(symbol):
    kraken_pair = KRAKEN_PAIR_MAP[symbol]
    url = f"https://api.kraken.com/0/public/OHLC?pair={kraken_pair}&interval=1"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    data = res.json()

    if data.get("error"):
        raise ValueError(f"Kraken API error: {data['error']}")

    result = data.get("result", {})
    candle_key = next((k for k in result.keys() if k != "last"), None)
    if candle_key is None:
        raise ValueError(f"Unexpected Kraken response shape for {symbol}")

    candles = result[candle_key][-100:]
    if len(candles) == 0:
        raise ValueError(f"Market data unavailable for {symbol}")

    opens, highs, lows, closes = [], [], [], []
    for c in candles:
        # Kraken OHLC row: [time, open, high, low, close, vwap, volume, count]
        opens.append(float(c[1]))
        highs.append(float(c[2]))
        lows.append(float(c[3]))
        closes.append(float(c[4]))

    return opens, highs, lows, closes


def fetch_klines_twelvedata(symbol):
    if not TWELVE_DATA_API_KEY:
        raise ValueError(
            "Forex data needs a Twelve Data API key. Set TWELVE_DATA_API_KEY "
            "in Render's Environment tab (free key at twelvedata.com)."
        )

    td_symbol = TWELVE_DATA_PAIR_MAP[symbol]
    url = (
        "https://api.twelvedata.com/time_series"
        f"?symbol={td_symbol}&interval=1min&outputsize=100&apikey={TWELVE_DATA_API_KEY}"
    )
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    data = res.json()

    if data.get("status") == "error" or "values" not in data:
        msg = data.get("message", "Unknown Twelve Data error")
        raise ValueError(
            f"Twelve Data error for {symbol}: {msg}. "
            "Note: real forex markets are closed on weekends — this pair "
            "will only return data during real market hours."
        )

    values = list(reversed(data["values"]))  # API returns newest-first; we need oldest-first
    if len(values) == 0:
        raise ValueError(f"No forex candles returned for {symbol} (market may be closed).")

    opens = [float(v["open"]) for v in values]
    highs = [float(v["high"]) for v in values]
    lows = [float(v["low"]) for v in values]
    closes = [float(v["close"]) for v in values]

    return opens, highs, lows, closes


def fetch_klines_safe(symbol="BTCUSDT"):
    if symbol not in VALID_SYMBOLS:
        raise ValueError(f"'{symbol}' is not supported. Choose one of {VALID_SYMBOLS}.")

    if ASSET_TYPE[symbol] == "crypto":
        return fetch_klines_kraken(symbol)
    else:
        return fetch_klines_twelvedata(symbol)


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


def calculate_macd(closes, fast=12, slow=26, signal=9):
    # Standard MACD: EMA(fast) - EMA(slow), then EMA(signal) of that line.
    ema_fast_series = calculate_ema(closes, fast)
    ema_slow_series = calculate_ema(closes, slow)
    start = max(fast, slow) - 1
    macd_line_series = [ema_fast_series[i] - ema_slow_series[i] for i in range(start, len(closes))]
    if len(macd_line_series) < signal:
        return macd_line_series[-1], macd_line_series[-1]  # not enough data to smooth; treat as flat
    signal_series = calculate_ema(macd_line_series, signal)
    return round(macd_line_series[-1], 5), round(signal_series[-1], 5)


def analyze_strict_confluence(opens, highs, lows, closes):
    rsi = calculate_rsi(closes, 14)
    ema20 = calculate_ema(closes, 20)[-1]
    ema50 = calculate_ema(closes, 50)[-1]
    bb_upper, bb_lower, bb_middle = calculate_bollinger(closes, 20, 2.0)
    stoch_k = calculate_stochastic(highs, lows, closes, 14)
    macd_line, macd_signal = calculate_macd(closes, 12, 26, 9)

    c_open, c_close, c_high, c_low = opens[-1], closes[-1], highs[-1], lows[-1]
    body = abs(c_close - c_open)
    lower_shade = min(c_open, c_close) - c_low
    upper_shade = c_high - max(c_open, c_close)

    call_filters = 0.0
    put_filters = 0.0
    call_reasons = []
    put_reasons = []

    if c_close > ema20 and ema20 > ema50:
        call_filters += 1
        call_reasons.append("EMA20>EMA50 uptrend")
    elif c_close < ema20 and ema20 < ema50:
        put_filters += 1
        put_reasons.append("EMA20<EMA50 downtrend")

    if rsi <= 35:
        call_filters += 1.5
        call_reasons.append(f"RSI oversold ({rsi})")
    elif rsi >= 65:
        put_filters += 1.5
        put_reasons.append(f"RSI overbought ({rsi})")

    bb_status = "MIDDLE ZONE"
    if c_close <= bb_lower or c_low <= bb_lower:
        call_filters += 1.5
        bb_status = "OVERSOLD (LOWER BAND)"
        call_reasons.append("Price at/below lower Bollinger band")
    elif c_close >= bb_upper or c_high >= bb_upper:
        put_filters += 1.5
        bb_status = "OVERBOUGHT (UPPER BAND)"
        put_reasons.append("Price at/above upper Bollinger band")

    if stoch_k < 25:
        call_filters += 1
        call_reasons.append(f"Stochastic oversold ({stoch_k})")
    elif stoch_k > 75:
        put_filters += 1
        put_reasons.append(f"Stochastic overbought ({stoch_k})")

    if lower_shade > (1.8 * body) and lower_shade > 0:
        call_filters += 1
        call_reasons.append("Long lower wick (rejection)")
    if upper_shade > (1.8 * body) and upper_shade > 0:
        put_filters += 1
        put_reasons.append("Long upper wick (rejection)")

    macd_trend = "FLAT"
    if macd_line > macd_signal:
        call_filters += 1
        macd_trend = "BULLISH"
        call_reasons.append(f"MACD above signal ({macd_line} > {macd_signal})")
    elif macd_line < macd_signal:
        put_filters += 1
        macd_trend = "BEARISH"
        put_reasons.append(f"MACD below signal ({macd_line} < {macd_signal})")

    ema_trend = "BULLISH" if ema20 > ema50 else "BEARISH"

    return {
        "call_score": round(call_filters, 1),
        "put_score": round(put_filters, 1),
        "call_reasons": call_reasons,
        "put_reasons": put_reasons,
        "rsi": rsi,
        "stoch": stoch_k,
        "bb_status": bb_status,
        "ema_trend": ema_trend,
        "macd_trend": macd_trend,
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
                "call_reasons": analysis['call_reasons'],
                "put_reasons": analysis['put_reasons'],
            },
        })

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except requests.RequestException:
        return jsonify({"status": "error", "message": "Could not reach Kraken API."}), 502
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
