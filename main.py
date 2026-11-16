
import os
import json
import requests
import config
from datetime import datetime

SEEN_FILE = "seen_ads.json"

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": config.BOT_CHATID,
            "text": text,
            "disable_web_page_preview": True
        },
        timeout=20
    )
    response.raise_for_status()

def get_ads():
    body = {
        "city_ids": config.SEARCH_CITY_IDS,
        "search_data": {
            "form_data": {
                "data": {
                    "category": {
                        "str": {"value": config.SEARCH_CATEGORY}
                    }
                }
            },
            "server_payload": {
                "@type": "type.googleapis.com/widgets.SearchData.ServerPayload",
                "additional_form_data": {
                    "data": {"sort": {"str": {"value": "sort_date"}}}
                }
            }
        },
        "disable_recommendation": False,
        "map_state": {"camera_info": {"bbox": {}}},
        "current_tab_slug": "default"
    }

    response = requests.post(
        config.DIVAR_SEARCH_URL,
        headers=config.REQUEST_HEADERS,
        json=body,
        timeout=25
    )
    response.raise_for_status()

    data = response.json()
    ads = []

    for widget in data.get("list_widgets", []):
        if widget.get("widget_type") != "POST_ROW":
            continue

        row = widget.get("data", {})
        token = row.get("token")
        if token:
            ads.append(token)

    return ads

def get_ad(token):
    url = config.DIVAR_POST_DETAIL_URL.format(token=token)
    response = requests.get(
        url,
        headers=config.REQUEST_HEADERS,
        timeout=25
    )
    response.raise_for_status()
    return response.json()

def parse_ad(token):
    data = get_ad(token)

    title = ""
    description = ""
    district = ""
    sections = data.get("sections", [])

    for section in sections:
        name = section.get("section_name")
        widgets = section.get("widgets", [])

        for widget in widgets:
            item = widget.get("data", {})

            if name == "TITLE":
                title = item.get("title", title)

            if name == "DESCRIPTION":
                description = item.get("text", description)

    web_info = data.get("seo", {}).get("web_info", {})
    district = web_info.get("district_persian", "")

    breadcrumb = []
    for section in sections:
        if section.get("section_name") == "BREADCRUMB":
            for widget in section.get("widgets", []):
                for item in widget.get("data", {}).get("parent_items", []):
                    breadcrumb.append(item.get("title", ""))

    return {
        "token": token,
        "title": title,
        "description": description,
        "district": district,
        "breadcrumb": breadcrumb
    }

def is_personal_ad(ad):
    text = (ad["title"] + " " + ad["description"]).lower()

    business_signs = [
        "املاک", "مشاور املاک", "دفتر املاک",
        "کارشناس فروش", "فایلینگ"
    ]

    return not any(word in text for word in business_signs)

def main():
    print("Started:", datetime.now())

    seen = load_seen()
    tokens = get_ads()

    print("Found ads:", len(tokens))

    for token in reversed(tokens):
        if token in seen:
            continue

        try:
            ad = parse_ad(token)

            if not is_personal_ad(ad):
                print("Business-like ad skipped:", token)
                seen.add(token)
                continue

            link = "https://divar.ir/v/" + token

            message = (
                "آگهی شخصی جدید\n\n"
                + ad["title"] + "\n"
                + "محدوده: " + ad["district"] + "\n\n"
                + ad["description"][:2500] + "\n\n"
                + "لینک آگهی:\n" + link
            )

            send_telegram(message)
            print("Sent:", token)
            seen.add(token)

        except Exception as error:
            print(
                "Error:", token, type(error).__name__,
                "HTTP:", getattr(getattr(error, "response", None), "status_code", ""),
                "DETAIL:", getattr(getattr(error, "response", None), "text", str(error))[:500]
            )

    save_seen(seen)
    print("Finished:", datetime.now())

if __name__ == "__main__":
    main()
