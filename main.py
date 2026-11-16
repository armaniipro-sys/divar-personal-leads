
import os
import json
import requests
import config
from datetime import datetime

SEEN_FILE = "seen_ads.json"
MAX_PHOTOS = 10

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

def telegram_request(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/{method}"
    response = requests.post(
        url, data=data, files=files, timeout=40
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(str(result))
    return result

def send_text(text):
    for start in range(0, len(text), 4000):
        telegram_request(
            "sendMessage",
            data={
                "chat_id": config.BOT_CHATID,
                "text": text[start:start + 4000],
                "disable_web_page_preview": True
            }
        )

def send_photos(photo_urls, caption):
    photo_urls = photo_urls[:MAX_PHOTOS]

    if not photo_urls:
        send_text(caption)
        return

    media = []
    files = {}
    opened_files = []

    try:
        for index, photo_url in enumerate(photo_urls):
            response = requests.get(
                photo_url,
                headers=config.REQUEST_HEADERS,
                timeout=30
            )
            response.raise_for_status()

            filename = f"photo{index}.jpg"
            files[filename] = (
                filename,
                response.content,
                "image/jpeg"
            )
            media.append({
                "type": "photo",
                "media": f"attach://{filename}"
            })

        media[0]["caption"] = caption[:1000]

        telegram_request(
            "sendMediaGroup",
            data={
                "chat_id": config.BOT_CHATID,
                "media": json.dumps(media, ensure_ascii=False)
            },
            files=files
        )

    except Exception as error:
        print("Photo sending failed:", str(error)[:500])
        send_text(caption)

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
                    "data": {
                        "sort": {"str": {"value": "sort_date"}}
                    }
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
        timeout=30
    )
    response.raise_for_status()

    data = response.json()
    tokens = []

    for widget in data.get("list_widgets", []):
        if widget.get("widget_type") == "POST_ROW":
            token = widget.get("data", {}).get("token")
            if token:
                tokens.append(token)

    return tokens

def get_ad(token):
    url = config.DIVAR_POST_DETAIL_URL.format(token=token)
    response = requests.get(
        url,
        headers=config.REQUEST_HEADERS,
        timeout=30
    )
    response.raise_for_status()
    return response.json()

def find_text_values(obj):
    values = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ("text", "title", "value", "description"):
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())
            elif isinstance(value, (dict, list)):
                values.extend(find_text_values(value))

    elif isinstance(obj, list):
        for item in obj:
            values.extend(find_text_values(item))

    return values

def find_images(obj):
    images = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                lower_key = key.lower()
                if (
                    ("image" in lower_key or "picture" in lower_key
                     or "url" in lower_key)
                    and value.startswith("https://")
                    and any(ext in value.lower() for ext in
                            (".jpg", ".jpeg", ".png", ".webp"))
                ):
                    images.append(value)

            elif isinstance(value, (dict, list)):
                images.extend(find_images(value))

    elif isinstance(obj, list):
        for item in obj:
            images.extend(find_images(item))

    return list(dict.fromkeys(images))

def parse_ad(token):
    data = get_ad(token)

    title = ""
    description = ""
    district = ""
    details = []
    sections = data.get("sections", [])

    for section in sections:
        name = section.get("section_name", "")
        widgets = section.get("widgets", [])

        for widget in widgets:
            item = widget.get("data", {})

            if name == "TITLE":
                title = item.get("title", title)

            elif name == "DESCRIPTION":
                description = item.get("text", description)

            elif name not in ("BREADCRUMB",):
                for value in find_text_values(item):
                    if value not in details and value != title:
                        details.append(value)

    web_info = data.get("seo", {}).get("web_info", {})
    district = web_info.get("district_persian", "")

    breadcrumb = []
    for section in sections:
        if section.get("section_name") == "BREADCRUMB":
            for widget in section.get("widgets", []):
                for item in widget.get("data", {}).get("parent_items", []):
                    value = item.get("title", "")
                    if value:
                        breadcrumb.append(value)

    photos = find_images(data)

    return {
        "token": token,
        "title": title,
        "description": description,
        "district": district,
        "breadcrumb": breadcrumb,
        "details": details,
        "photos": photos
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
                "آگهی جدید\n\n"
                + (ad["title"] or "بدون عنوان") + "\n"
                + "محدوده: " + (ad["district"] or "ثبت نشده") + "\n"
                + "دسته‌بندی: "
                + " / ".join(ad["breadcrumb"]) + "\n\n"
                + (ad["description"] or "توضیحات ثبت نشده")
                + "\n\n"
            )

            if ad["details"]:
                message += "مشخصات و جزئیات:\n"
                message += "\n".join(
                    dict.fromkeys(ad["details"])
                )[:2500] + "\n\n"

            message += "لینک آگهی:\n" + link

            if ad["photos"]:
                send_photos(ad["photos"], message)
            else:
                send_text(message)

            print(
                "Sent:", token,
                "Photos:", len(ad["photos"])
            )
            seen.add(token)

        except Exception as error:
            print(
                "Error:", token, type(error).__name__,
                "HTTP:",
                getattr(getattr(error, "response", None),
                        "status_code", ""),
                "DETAIL:",
                getattr(getattr(error, "response", None),
                        "text", str(error))[:500]
            )

    save_seen(seen)
    print("Finished:", datetime.now())

if __name__ == "__main__":
    main()
