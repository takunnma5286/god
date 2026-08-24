import os
import sys
import json
import shutil
import mimetypes
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CUSTOM_DATA_DIR = os.path.join(BASE_DIR, 'custom_data')
UPLOADS_DIR = os.path.join(CUSTOM_DATA_DIR, 'uploads')
DEFAULTS_DIR = os.path.join(CUSTOM_DATA_DIR, 'defaults')
CONFIG_FILE = os.path.join(CUSTOM_DATA_DIR, 'skin_config.json')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DEFAULTS_DIR, exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_default_ja():
    path = os.path.join(DEFAULTS_DIR, 'i18n', 'ja.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def get_current_ja():
    path = os.path.join(BASE_DIR, 'i18n', 'ja.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_current_ja(data):
    path = os.path.join(BASE_DIR, 'i18n', 'ja.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def find_image_for_item(img_name, category):
    candidates = [
        f'images/items/{category}/{img_name}.webp',
        f'images/items/{img_name}.webp',
        f'images/{category}/{img_name}.webp',
        f'images/{img_name}.webp'
    ]
    for c in candidates:
        if os.path.exists(os.path.join(BASE_DIR, c)):
            return c
    for root, dirs, files in os.walk(os.path.join(BASE_DIR, 'images')):
        if f'{img_name}.webp' in files:
            return os.path.relpath(os.path.join(root, f'{img_name}.webp'), BASE_DIR)
    return None

class EditorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/editor':
            editor_path = os.path.join(BASE_DIR, 'templates', 'editor.html')
            if os.path.exists(editor_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(editor_path, 'rb') as f:
                    self.wfile.write(f.read())
                return

        if path == '/api/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()

            cur_ja = get_current_ja()
            def_ja = get_default_ja()
            config = load_config()

            items_list = []
            cur_items = cur_ja.get('items', [])
            def_items = def_ja.get('items', [])

            for idx, item in enumerate(cur_items):
                def_item = def_items[idx] if idx < len(def_items) else {}
                img_name = item.get('imageName')
                cat = item.get('category', 'unknown')
                img_rel_path = find_image_for_item(img_name, cat)

                default_w, default_h = 80, 80
                if img_rel_path:
                    def_img_full = os.path.join(DEFAULTS_DIR, img_rel_path)
                    if os.path.exists(def_img_full):
                        try:
                            with Image.open(def_img_full) as im:
                                default_w, default_h = im.size
                        except Exception:
                            pass

                item_id = f'{cat}_{img_name}_{idx}'
                custom_info = config.get('items', {}).get(item_id, {})

                items_list.append({
                    'id': item_id,
                    'index': idx,
                    'category': cat,
                    'imageName': img_name,
                    'imagePath': img_rel_path,
                    'defaultName': def_item.get('name', item.get('name', '')),
                    'currentName': item.get('name', ''),
                    'ability': item.get('ability', ''),
                    'atk': item.get('atk'),
                    'isPlusAtk': item.get('isPlusAtk'),
                    'def': item.get('def'),
                    'price': item.get('price'),
                    'giftRate': item.get('giftRate'),
                    'hp': item.get('hp'),
                    'mp': item.get('mp'),
                    'cp': item.get('cp'),
                    'element': item.get('element'),
                    'defaultWidth': default_w,
                    'defaultHeight': default_h,
                    'custom': custom_info
                })

            other_images = []
            for root, dirs, files in os.walk(os.path.join(BASE_DIR, 'images')):
                for f in files:
                    if f.endswith(('.webp', '.png', '.jpg', '.svg')):
                        rel = os.path.relpath(os.path.join(root, f), BASE_DIR)
                        is_item = any(it['imagePath'] == rel for it in items_list)
                        if not is_item:
                            img_id = rel.replace('/', '_').replace('.', '_')
                            def_img_full = os.path.join(DEFAULTS_DIR, rel)
                            dw, dh = 100, 100
                            if os.path.exists(def_img_full):
                                try:
                                    with Image.open(def_img_full) as im:
                                        dw, dh = im.size
                                except Exception:
                                    pass
                            other_images.append({
                                'id': img_id,
                                'imagePath': rel,
                                'filename': f,
                                'category': rel.split('/')[1] if len(rel.split('/')) > 2 else 'other',
                                'defaultWidth': dw,
                                'defaultHeight': dh,
                                'custom': config.get('other_images', {}).get(img_id, {})
                            })

            res = {
                'items': items_list,
                'other_images': other_images,
                'current_texts': cur_ja.get('texts', {}),
                'default_texts': def_ja.get('texts', {}),
                'config': config
            }
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        if path == '/api/upload':
            try:
                data = json.loads(body.decode('utf-8'))
                target_id = data.get('target_id', 'temp')
                image_base64 = data.get('image_base64', '')
                ext = data.get('ext', 'png')

                import base64
                if ',' in image_base64:
                    image_base64 = image_base64.split(',', 1)[1]
                raw_bytes = base64.b64decode(image_base64)

                filename = f'{target_id}_raw.{ext}'
                save_path = os.path.join(UPLOADS_DIR, filename)
                with open(save_path, 'wb') as f:
                    f.write(raw_bytes)

                with Image.open(save_path) as im:
                    w, h = im.size

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'ok',
                    'filename': filename,
                    'upload_url': f'/custom_data/uploads/{filename}',
                    'width': w,
                    'height': h
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
            return

        if path == '/api/crop':
            try:
                data = json.loads(body.decode('utf-8'))
                target_id = data.get('target_id')
                target_type = data.get('target_type', 'item')
                image_path = data.get('image_path')
                raw_filename = data.get('raw_filename')
                crop_box = data.get('crop_box')
                resize_to_default = data.get('resize_to_default', True)
                lock_aspect_ratio = data.get('lock_aspect_ratio', True)
                default_w = data.get('default_width', 80)
                default_h = data.get('default_height', 80)

                raw_full = os.path.join(UPLOADS_DIR, raw_filename)
                if not os.path.exists(raw_full):
                    raise Exception(f'Raw image not found: {raw_filename}')

                dest_full = os.path.join(BASE_DIR, image_path)
                os.makedirs(os.path.dirname(dest_full), exist_ok=True)

                with Image.open(raw_full) as im:
                    im = im.convert('RGBA')
                    
                    cx = max(0, int(crop_box['x']))
                    cy = max(0, int(crop_box['y']))
                    cw = min(im.width - cx, int(crop_box['width']))
                    ch = min(im.height - cy, int(crop_box['height']))
                    
                    cropped = im.crop((cx, cy, cx + cw, cy + ch))

                    if resize_to_default:
                        final_img = cropped.resize((int(default_w), int(default_h)), Image.Resampling.LANCZOS)
                    else:
                        final_img = cropped

                    final_img.save(dest_full, 'WEBP', quality=95)

                cfg = load_config()
                group = 'items' if target_type == 'item' else 'other_images'
                if group not in cfg:
                    cfg[group] = {}
                cfg[group][target_id] = {
                    'raw_filename': raw_filename,
                    'crop_box': crop_box,
                    'resize_to_default': resize_to_default,
                    'lock_aspect_ratio': lock_aspect_ratio,
                    'updated_at': os.path.getmtime(dest_full)
                }
                save_config(cfg)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'message': 'Image updated successfully'}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
            return

        if path == '/api/update_text':
            try:
                data = json.loads(body.decode('utf-8'))
                target_type = data.get('target_type')
                
                cur_ja = get_current_ja()
                if target_type == 'item_name':
                    item_index = int(data.get('item_index'))
                    new_name = data.get('name', '')
                    if 0 <= item_index < len(cur_ja.get('items', [])):
                        cur_ja['items'][item_index]['name'] = new_name
                        save_current_ja(cur_ja)
                elif target_type == 'text_entry':
                    category = data.get('category')
                    key = data.get('key')
                    new_val = data.get('value', '')
                    if 'texts' in cur_ja and category in cur_ja['texts']:
                        cur_ja['texts'][category][key] = new_val
                        save_current_ja(cur_ja)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
            return

        if path == '/api/reset_image':
            try:
                data = json.loads(body.decode('utf-8'))
                target_id = data.get('target_id')
                target_type = data.get('target_type', 'item')
                image_path = data.get('image_path')

                def_full = os.path.join(DEFAULTS_DIR, image_path)
                cur_full = os.path.join(BASE_DIR, image_path)

                if os.path.exists(def_full):
                    shutil.copy2(def_full, cur_full)

                cfg = load_config()
                group = 'items' if target_type == 'item' else 'other_images'
                if group in cfg and target_id in cfg[group]:
                    del cfg[group][target_id]
                    save_config(cfg)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
            return

        if path == '/api/reset_text':
            try:
                data = json.loads(body.decode('utf-8'))
                target_type = data.get('target_type')

                def_ja = get_default_ja()
                cur_ja = get_current_ja()

                if target_type == 'item_name':
                    item_index = int(data.get('item_index'))
                    def_name = def_ja.get('items', [])[item_index].get('name', '')
                    cur_ja['items'][item_index]['name'] = def_name
                    save_current_ja(cur_ja)
                elif target_type == 'text_entry':
                    category = data.get('category')
                    key = data.get('key')
                    def_val = def_ja.get('texts', {}).get(category, {}).get(key, '')
                    cur_ja['texts'][category][key] = def_val
                    save_current_ja(cur_ja)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

def run_server(port=5000):
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, EditorHandler)
    print('=====================================================')
    print(' God Field Custom Skin Editor Server Started!')
    print(f' - Game:   http://localhost:{port}/')
    print(f' - Editor: http://localhost:{port}/editor')
    print('=====================================================')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        httpd.server_close()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    run_server(port)
