import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ── المفاتيح من متغيرات البيئة ──
NEWS_API_KEY = os.environ["NEWS_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SHEET_ID = "1tgtoTCJg_VBAedPbiq88UvyiC9h29sJaJ_q3f5Hm1co"

# ── قائمة الأسهم ──
TICKERS = [
    "CRWD", "MOD", "FTNT", "MP", "CCJ", "TDG", "SLB",
    "KTOS", "RTX", "RHM", "LDO", "LNG", "LYSCF", "ASML",
    "AMAT", "VNM", "GLD", "AEM", "BX", "IBIT", "APO",
    "CGNX", "ROK", "ZBRA", "TER", "RMD", "EXAS", "ISRG"
]

def get_news():
    """جلب الأخبار من NewsAPI"""
    query = " OR ".join(TICKERS)
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 20,
        "domains": "reuters.com,bloomberg.com,wsj.com,ft.com,cnbc.com",
        "apiKey": NEWS_API_KEY
    }
    res = requests.get(url, params=params)
    data = res.json()
    return data.get("articles", [])

def analyze_with_claude(title, description):
    """تحليل الخبر بـ Claude وإرجاع JSON نظيف بالعربي"""
    prompt = f"""أنت محلل مالي. حلل هذا الخبر وأجب بـ JSON فقط بدون أي كلام آخر.

الخبر: {title}
التفاصيل: {description or ''}

أجب بهذا الشكل الدقيق فقط، ابدأ بـ {{ وانتهِ بـ }}:
{{"triggered": true, "urgency": "HIGH", "summary": "ملخص الخبر بالعربية في جملة واحدة", "action": "STRONG SIGNAL"}}

قيم urgency: HIGH أو MEDIUM أو LOW
قيم action: STRONG SIGNAL أو WATCH
triggered: true فقط إذا كان الخبر يؤثر مباشرة على أحد الأسهم في قائمتنا"""

    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        }
    )

    response = res.json()
raw = response.get("content", [{}])[0].get("text", "{}").strip()
    # تنظيف الرد
    raw = raw.replace("```json", "").replace("```", "").strip()
    if raw.startswith("null"):
        raw = raw[4:].strip()
    if raw.endswith("null"):
        raw = raw[:-4].strip()

    return json.loads(raw)

def write_to_sheet(rows):
    """كتابة النتائج في Google Sheets"""
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(
        creds_json,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("الورقة1")

    for row in rows:
        sheet.append_row([
            row["date"],
            row["ticker"],
            row["source"],
            "نعم" if row["triggered"] else "لا",
            row["urgency"],
            row["summary"],
            row["action"],
            row["url"]
        ])
        print(f"✅ {row['ticker']} — {row['summary'][:50]}")

def find_ticker(text):
    """إيجاد السهم في النص"""
    text_upper = text.upper()
    for ticker in TICKERS:
        if ticker in text_upper:
            return ticker
    return "GENERAL"

def main():
    print("🚀 SIGNAL — بدء التشغيل")
    articles = get_news()
    print(f"📰 {len(articles)} خبر مجلوب")

    rows = []
    for article in articles:
        title = article.get("title", "")
        description = article.get("description", "")
        url = article.get("url", "")
        source = article.get("source", {}).get("name", "")
        published = article.get("publishedAt", "")
        ticker = find_ticker(title + " " + (description or ""))

        try:
            result = analyze_with_claude(title, description)
            rows.append({
                "date": published,
                "ticker": ticker,
                "source": source,
                "triggered": result.get("triggered", False),
                "urgency": result.get("urgency", "LOW"),
                "summary": result.get("summary", title),
                "action": result.get("action", "WATCH"),
                "url": url
            })
        except Exception as e:
            print(f"⚠️ خطأ في تحليل: {title[:50]} — {e}")
            continue

    if rows:
        write_to_sheet(rows)
        triggered = [r for r in rows if r["triggered"]]
        print(f"\n✅ تم — {len(rows)} خبر محلل، {len(triggered)} محفز")
    else:
        print("❌ لا توجد نتائج")

if __name__ == "__main__":
    main()
