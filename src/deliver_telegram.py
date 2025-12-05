
import os
import requests

def send_digest_telegram(items, bullets=6):
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    top = items[:bullets]
    text = "\n\n".join([
        f"• *{i['title']}*\n_{i.get('source','')} — {i.get('date','')}_\n"
        f"{ i.get('key_findings','(see link)') }\n{ i['url'] }"
        for i in top
    ])

    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  data={"chat_id": chat_id, "text": text, "parse_mode":"Markdown"})

def send_photo_telegram(caption, photo_url):
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                  data={"chat_id": chat_id, "caption": caption,
                        "photo": photo_url, "parse_mode":"Markdown"})
