import os

DIVAR_SEARCH_URL = "https://api.divar.ir/v8/postlist/w/search"
DIVAR_POST_DETAIL_URL = "https://api.divar.ir/v8/posts-v2/web/{token}"

BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_CHATID = os.environ["BOT_CHATID"]

SEARCH_CITY_IDS = ["1751"]
SEARCH_CATEGORY = "real-estate"

REQUEST_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "referrer": "https://divar.ir/",
    "x-render-type": "CSR",
    "x-standard-divar-error": "true",
}
