import re

def normalize_youtube_url(url):
    u = str(url or "").strip()
    u = re.sub(r"[`\s\"']*(https?://[^`\s\"']+)[`\s\"']*", r"\1", u)
    u = u.strip("` \t\r\n\"'")
    if not u:
        return ""
    
    m = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})(?:\?|&|/|$)", u)
    if m:
        video_id = m.group(1)
        return f"https://youtu.be/{video_id}"
    return u

urls = [
    "https://youtu.be/xj3xEisC7D4",
    "https://www.youtube.com/watch?v=xj3xEisC7D4",
    "https://www.youtube.com/watch?v=xj3xEisC7D4&t=1s",
    "https://youtube.com/live/xj3xEisC7D4?feature=share",
    "https://www.youtube.com/shorts/xj3xEisC7D4",
    "xj3xEisC7D4",
    "youtu.be/xj3xEisC7D4",
    "https://m.youtube.com/watch?v=xj3xEisC7D4"
]

for url in urls:
    print(f"{url} -> {normalize_youtube_url(url)}")
