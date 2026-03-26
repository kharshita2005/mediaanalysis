from flask import Flask, render_template, request, jsonify
import pandas as pd
import re
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from textblob import TextBlob
import logging
import os
import requests
import urllib.parse
import html as html_lib
from dotenv import load_dotenv

# --- Logging ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

# --- Load environment variables ---
load_dotenv()
BEARER_TOKEN = os.getenv('BEARER_TOKEN')
INSTAGRAM_SESSIONID = os.getenv('INSTAGRAM_SESSIONID')
INSTAGRAM_DS_USER_ID = os.getenv('INSTAGRAM_DS_USER_ID')
INSTAGRAM_CSRF_TOKEN = os.getenv('INSTAGRAM_CSRF_TOKEN')
INSTAGRAM_MID = os.getenv('INSTAGRAM_MID')

log.info("BEARER_TOKEN present: %s", bool(BEARER_TOKEN))
log.info("INSTAGRAM_SESSIONID present: %s", bool(INSTAGRAM_SESSIONID))

# --- Flask App ---
app = Flask(__name__)

# --- NLTK Setup ---
try:
    nltk.data.find('sentiment/vader_lexicon')
except:
    nltk.download('vader_lexicon')

_sia = SentimentIntensityAnalyzer()

# --- Sentiment Helpers ---
def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'http\S+|www\S+|https\S+', '', text)
    text = re.sub(r'\@\w+|\#', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

def analyze_sentiment_textblob(text):
    polarity = TextBlob(clean_text(text)).sentiment.polarity
    sentiment = "positive" if polarity > 0.05 else "negative" if polarity < -0.05 else "neutral"
    return {"text": text, "sentiment": sentiment, "polarity": round(polarity,2)}

def analyze_sentiment_vader(text):
    compound = _sia.polarity_scores(clean_text(text))['compound']
    sentiment = "positive" if compound >= 0.05 else "negative" if compound <= -0.05 else "neutral"
    return {"text": text, "sentiment": sentiment, "polarity": round(compound,2)}

# --- Twitter Helper ---
def get_tweet_text(tweet_url_or_id):
    # Extract tweet ID from URL or use numeric ID
    match = re.search(r'(?:x\.com|twitter\.com)/.+/status/(\d+)', str(tweet_url_or_id))
    tweet_id = match.group(1) if match else (tweet_url_or_id if tweet_url_or_id.isdigit() else None)
    if not tweet_id:
        return None, "Invalid tweet URL or ID"
    if not BEARER_TOKEN:
        return None, "BEARER_TOKEN missing"

    url = f"https://api.twitter.com/2/tweets/{tweet_id}"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    params = {"tweet.fields": "text"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code != 200:
            return None, f"Twitter API error {r.status_code}"
        data = r.json().get("data")
        if not data or "text" not in data:
            return None, "No text returned by Twitter"
        return data["text"], None
    except Exception as e:
        log.exception("Twitter fetch failed")
        return None, str(e)

# --- Instagram Helper ---
def fetch_instagram_caption(url):
    # Public oEmbed first
    try:
        oembed_url = f"https://api.instagram.com/oembed?url={urllib.parse.quote(url)}"
        r = requests.get(oembed_url, timeout=10)
        if r.status_code == 200:
            return r.json().get("title")
    except:
        pass

    # Fallback using session cookies
    cookies = {}
    if INSTAGRAM_SESSIONID:
        cookies['sessionid'] = urllib.parse.unquote(INSTAGRAM_SESSIONID)
    if INSTAGRAM_DS_USER_ID:
        cookies['ds_user_id'] = urllib.parse.unquote(INSTAGRAM_DS_USER_ID)
    if INSTAGRAM_CSRF_TOKEN:
        cookies['csrftoken'] = urllib.parse.unquote(INSTAGRAM_CSRF_TOKEN)
    if INSTAGRAM_MID:
        cookies['mid'] = urllib.parse.unquote(INSTAGRAM_MID)

    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, cookies=cookies or None, timeout=10)
        if r.status_code != 200:
            return None
        html = r.text
        m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if m:
            return html_lib.unescape(m.group(1)).strip()
    except:
        pass
    return None

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_text():
    req = request.get_json(silent=True) or {}
    text = req.get('text') or request.form.get('text','')
    if not text:
        return jsonify({"error":"No text provided"}),400

    tb_res = analyze_sentiment_textblob(text)
    vader_res = analyze_sentiment_vader(text)
    return jsonify({
        "text": text,
        "sentiment": vader_res["sentiment"],
        "polarity": vader_res["polarity"],
        "secondary_polarity": tb_res["polarity"],
        "analyzers_used": ["VADER","TextBlob"]
    })

@app.route('/analyze_bulk', methods=['POST'])
def analyze_bulk():
    if 'file' not in request.files:
        return jsonify({"error":"No file uploaded"}),400
    file = request.files['file']
    try:
        df = pd.read_csv(file)
    except Exception:
        return jsonify({"error":"Invalid CSV"}),400
    if 'text' not in df.columns:
        return jsonify({"error":"CSV must contain 'text' column"}),400

    results, counts = [], {"positive":0,"negative":0,"neutral":0}
    for raw in df['text']:
        text = str(raw) if pd.notna(raw) else ""
        tb_res = analyze_sentiment_textblob(text)
        vader_res = analyze_sentiment_vader(text)
        sentiment = vader_res["sentiment"]
        counts[sentiment] += 1
        results.append({
            "text": text,
            "sentiment": sentiment,
            "polarity": vader_res["polarity"],
            "secondary_polarity": tb_res["polarity"]
        })
    total = len(results)
    summary = {k: counts[k] for k in counts}
    summary.update({f"{k}_pct": round((counts[k]/total)*100,2) for k in counts})
    return jsonify({"status":"success","count":total,"summary":summary,"results":results})
@app.route('/analyze_tweet', methods=['POST'])
def analyze_tweet():
    # --- Log raw incoming data ---
    log.info("Raw form data: %s", request.form)
    log.info("Raw JSON data: %s", request.get_json(silent=True))
    log.info("Raw args: %s", request.args)

    json_data = request.get_json(silent=True) or {}

    # --- Attempt to get tweet input from multiple sources ---
    tweet_input = json_data.get('tweet_url') or json_data.get('tweet_id') \
                  or request.form.get('tweet_url') or request.form.get('tweet_id') \
                  or request.args.get('tweet_url') or request.args.get('tweet_id')

    log.info("Parsed tweet_input: %s", tweet_input)

    if not tweet_input:
        return jsonify({"error": "No tweet URL or ID provided"}), 400

    # --- Clean URL (remove query params) ---
    clean_url = str(tweet_input).split('?')[0]

    # --- Extract tweet ID ---
    match = re.search(r'(?:twitter|x)\.com/.+/status/(\d+)', clean_url)
    tweet_id = match.group(1) if match else (clean_url if clean_url.isdigit() else None)

    if not tweet_id:
        return jsonify({"error": "Invalid Tweet URL or ID"}), 400

    # --- Fetch tweet text ---
    tweet_text, err = get_tweet_text(tweet_id)
    if err:
        log.warning("Tweet fetch error: %s", err)
        return jsonify({"error": f"Failed to fetch tweet: {err}"}), 400

    # --- Analyze sentiment ---
    tb_res = analyze_sentiment_textblob(tweet_text)
    vader_res = analyze_sentiment_vader(tweet_text)

    return jsonify({
        "text": tweet_text,
        "sentiment": vader_res["sentiment"],
        "polarity": vader_res["polarity"],
        "secondary_polarity": tb_res["polarity"],
        "analysis_metadata": {
            "source": "twitter",
            "analyzers_used": ["VADER", "TextBlob"]
        }
    })

@app.route('/analyze_instagram', methods=['POST'])
def analyze_instagram():
    req = request.get_json(silent=True) or {}
    url = req.get('post_url') or request.form.get('post_url','')
    if not url:
        return jsonify({"error":"No Instagram URL provided"}),400

    caption = fetch_instagram_caption(url)
    if not caption:
        return jsonify({"error":"Failed to fetch caption"}),503

    tb_res = analyze_sentiment_textblob(caption)
    vader_res = analyze_sentiment_vader(caption)
    return jsonify({
        "text": caption,
        "sentiment": vader_res["sentiment"],
        "polarity": vader_res["polarity"],
        "secondary_polarity": tb_res["polarity"],
        "analyzers_used": ["VADER","TextBlob"]
    })

# --- Run ---
if __name__ == '__main__':
    debug_flag = os.getenv("FLASK_DEBUG","False")=="True"
    port = int(os.getenv("PORT",5000))
    app.run(host='0.0.0.0', port=port, debug=debug_flag)
