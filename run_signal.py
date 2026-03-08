import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials

NEWS_API_KEY = os.environ["NEWS_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SHEET_ID = "1tgtoTCJg_VBAedPbiq88UvyiC9h29sJaJ_q3f5Hm1co"

TICKERS = [
    "CRWD", "MOD", "FTNT", "MP", "CCJ", "TDG", "SLB",
    "KTOS", "RTX", "RHM", "LDO", "LNG", "LYSCF", "ASML",
    "AMAT", "VNM", "GLD", "AEM", "BX", "IBIT", "APO",
    "CGNX", "ROK", "ZBRA", "TER", "RMD", "EXAS", "ISRG"
]

def get_news():
    query = " OR ".join(TICKERS)
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 20,
        "domains": "reuters.com,bloomberg.com,wsj.com,ft.com,cnbc.com",
        "apiKey": NEWS_API_KEY
    }
    res = requests.get("https://newsapi.org/v2/everything", params=params)
    return res.json().get("articles", [])

def analyze(title, description):
    prompt = f"""انت محلل مالي. حلل هذا الخبر واجب بـ JSON فقط بدون اي كلام اخر. ابدا بـ {{ وانته بـ }}.

الخبر: {title}
التفاصيل: {description or ''}

الشكل المطلوب:
{{"triggered": true, "urgency": "HIGH", "summary": "اكتب هنا الملخص باللغة العربية فقط", "action": "WATCH"}}

urgency: HIGH او MEDIUM او LOW
action: STRONG SIGNAL او WATCH
triggered: true فقط اذا كان الخبر يؤثر على احد اسهمنا
مهم جدا: اكتب قيمة summary باللغة العربية فقط"""

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
    raw = raw.replace("```json", "").replace("```", "").strip()
    if raw.startswith("null"):
        raw = raw[4:].strip()
    if raw.endswith("null"):
        raw = raw[:-4].strip()
    return json.loads(raw)

def find_ticker(text):
    text_upper = text.upper()
    for t in TICKERS:
        if t in text_upper:
            return t
    return "GENERAL"

def main():
    print("SIGNAL - بدء التشغيل")
    articles = get_news()
    print(f"{len(articles)} خبر مجلوب")

    rows = []
    for a in articles:
        title = a.get("title", "")
        desc = a.get("description", "")
        try:
            result = analyze(title, desc)
            rows.append({
                "date": a.get("publishedAt", ""),
                "ticker": find_ticker(title + " " + (desc or "")),
                "source": a.get("source", {}).get("name", ""),
                "triggered": result.get("triggered", False),
                "urgency": result.get("urgency", "LOW"),
                "summary": result.get("summary", title),
                "action": result.get("action", "WATCH"),
                "url": a.get("url", "")
            })
        except Exception as e:
            print(f"خطا: {title[:50]} - {e}")

    if not rows:
        print("لا توجد نتائج")
        return

    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDENTIALS"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    sheet = gspread.authorize(creds).open_by_key(SHEET_ID).worksheet("الورقة1")
    print("اتصل بالشيت بنجاح")

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
        print(f"كتب: {row['ticker']} - {row['summary'][:50]}")

    print(f"تم - {len(rows)} خبر")

if __name__ == "__main__":
    main()
