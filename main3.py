import json
import os
import urllib.parse
import urllib.request
import base64
import concurrent.futures

def download_or_extract(entry, base_dir):
    req = entry.get("request", {})
    url = req.get("url", "")
    if not url:
        return
    
    parsed = urllib.parse.urlparse(url)
    
    # godfield.net 関連のパス抽出
    if "godfield.net" in parsed.netloc:
        path = parsed.path.lstrip("/")
        if not path or path == "index.html":
            return
        save_path = os.path.join(base_dir, path)
    elif "gstatic.com" in parsed.netloc:
        path = parsed.path.lstrip("/")
        save_path = os.path.join(base_dir, path)
    elif "googletagmanager.com" in parsed.netloc:
        path = "analytics.js"
        save_path = os.path.join(base_dir, path)
    else:
        path = parsed.path.lstrip("/")
        if not path:
            return
        save_path = os.path.join(base_dir, path)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    # まず HAR 内のレスポンスボディをチェック
    resp = entry.get("response", {})
    content = resp.get("content", {})
    text = content.get("text")
    encoding = content.get("encoding")
    
    if text is not None and len(text) > 0:
        try:
            if encoding == "base64":
                raw_data = base64.b64decode(text)
                with open(save_path, "wb") as f:
                    f.write(raw_data)
            else:
                with open(save_path, "wb") as f:
                    f.write(text.encode("utf-8"))
            return
        except Exception:
            pass

    # HAR内にデータがない場合はHTTPリクエストでダウンロード
    try:
        req_obj = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req_obj, timeout=10) as response:
            if response.status == 200:
                with open(save_path, "wb") as f:
                    f.write(response.read())
    except Exception as e:
        print(f"Error downloading {url}: {e}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    har_path = os.path.join(base_dir, "godfield.net.har")
    
    if not os.path.exists(har_path):
        print(f"HAR file not found: {har_path}")
        return
        
    with open(har_path, "r", encoding="utf-8") as f:
        har_data = json.load(f)
        
    entries = har_data.get("log", {}).get("entries", [])
    print(f"Total entries to process: {len(entries)}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(download_or_extract, entry, base_dir) for entry in entries]
        for future in concurrent.futures.as_completed(futures):
            if future.exception():
                print(f"Task error: {future.exception()}")
    print("Download and extraction completed!")

if __name__ == "__main__":
    main()
