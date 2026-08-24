import unittest
import os
import json
import base64
import time
from PIL import Image
import urllib.request
import threading
from editor_server import ThreadingHTTPServer, EditorHandler

TEST_PORT = 5002

class TestSkinEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('localhost', TEST_PORT), EditorHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_01_get_data(self):
        url = f'http://localhost:{TEST_PORT}/api/data'
        with urllib.request.urlopen(url) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode('utf-8'))
            self.assertIn('items', data)
            self.assertIn('other_images', data)
            self.assertIn('current_texts', data)
            self.assertIn('default_texts', data)
            self.assertEqual(len(data['items']), 296)
            self.assertGreater(len(data['other_images']), 0)
            print(f'Items loaded: {len(data["items"])}, Other images: {len(data["other_images"])}')

    def test_02_update_and_reset_text(self):
        # 1. Update text
        url = f'http://localhost:{TEST_PORT}/api/update_text'
        payload = json.dumps({
            'target_type': 'item_name',
            'item_index': 0,
            'name': 'テスト神器'
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)

        # Check ja.json
        with open('i18n/ja.json', 'r', encoding='utf-8') as f:
            ja = json.load(f)
            self.assertEqual(ja['items'][0]['name'], 'テスト神器')

        # 2. Reset text
        url_reset = f'http://localhost:{TEST_PORT}/api/reset_text'
        payload_reset = json.dumps({
            'target_type': 'item_name',
            'item_index': 0
        }).encode('utf-8')
        req_reset = urllib.request.Request(url_reset, data=payload_reset, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req_reset) as res:
            self.assertEqual(res.status, 200)

        # Check ja.json restored
        with open('i18n/ja.json', 'r', encoding='utf-8') as f:
            ja = json.load(f)
            self.assertEqual(ja['items'][0]['name'], '捨てる')

    def test_03_image_upload_and_crop_4_patterns(self):
        # Create a sample 200x200 test image
        img = Image.new('RGBA', (200, 200), (255, 0, 0, 255))
        test_img_path = 'custom_data/test_sample.png'
        img.save(test_img_path)

        with open(test_img_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')

        # 1. Upload
        url_upload = f'http://localhost:{TEST_PORT}/api/upload'
        payload_upload = json.dumps({
            'target_id': 'trade_discard_0',
            'image_base64': b64,
            'ext': 'png'
        }).encode('utf-8')
        req_upload = urllib.request.Request(url_upload, data=payload_upload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req_upload) as res:
            self.assertEqual(res.status, 200)
            upload_res = json.loads(res.read().decode('utf-8'))
            raw_filename = upload_res['filename']
            self.assertEqual(upload_res['width'], 200)
            self.assertEqual(upload_res['height'], 200)

        target_img_path = 'images/items/trade/discard.webp'

        # Pattern 1: Both ON (resize=True, lock_aspect=True) -> output must be default_width x default_height (80x80)
        url_crop = f'http://localhost:{TEST_PORT}/api/crop'
        payload_crop1 = json.dumps({
            'target_id': 'trade_discard_0',
            'target_type': 'item',
            'image_path': target_img_path,
            'raw_filename': raw_filename,
            'crop_box': {'x': 10, 'y': 10, 'width': 100, 'height': 100},
            'resize_to_default': True,
            'lock_aspect_ratio': True,
            'default_width': 80,
            'default_height': 80
        }).encode('utf-8')
        req_crop1 = urllib.request.Request(url_crop, data=payload_crop1, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req_crop1) as res:
            self.assertEqual(res.status, 200)
        with Image.open(target_img_path) as im:
            self.assertEqual(im.size, (80, 80))

        # Pattern 2: resize=False, lock_aspect=True -> output must be cropped size (120x120)
        payload_crop2 = json.dumps({
            'target_id': 'trade_discard_0',
            'target_type': 'item',
            'image_path': target_img_path,
            'raw_filename': raw_filename,
            'crop_box': {'x': 10, 'y': 10, 'width': 120, 'height': 120},
            'resize_to_default': False,
            'lock_aspect_ratio': True,
            'default_width': 80,
            'default_height': 80
        }).encode('utf-8')
        req_crop2 = urllib.request.Request(url_crop, data=payload_crop2, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req_crop2) as res:
            self.assertEqual(res.status, 200)
        with Image.open(target_img_path) as im:
            self.assertEqual(im.size, (120, 120))

        # Pattern 3: resize=True, lock_aspect=False (free crop resized to 80x80) -> output must be (80, 80)
        payload_crop3 = json.dumps({
            'target_id': 'trade_discard_0',
            'target_type': 'item',
            'image_path': target_img_path,
            'raw_filename': raw_filename,
            'crop_box': {'x': 0, 'y': 0, 'width': 180, 'height': 90},
            'resize_to_default': True,
            'lock_aspect_ratio': False,
            'default_width': 80,
            'default_height': 80
        }).encode('utf-8')
        req_crop3 = urllib.request.Request(url_crop, data=payload_crop3, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req_crop3) as res:
            self.assertEqual(res.status, 200)
        with Image.open(target_img_path) as im:
            self.assertEqual(im.size, (80, 80))

        # Pattern 4: Both OFF (resize=False, lock_aspect=False) -> output must be (150, 75)
        payload_crop4 = json.dumps({
            'target_id': 'trade_discard_0',
            'target_type': 'item',
            'image_path': target_img_path,
            'raw_filename': raw_filename,
            'crop_box': {'x': 0, 'y': 0, 'width': 150, 'height': 75},
            'resize_to_default': False,
            'lock_aspect_ratio': False,
            'default_width': 80,
            'default_height': 80
        }).encode('utf-8')
        req_crop4 = urllib.request.Request(url_crop, data=payload_crop4, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req_crop4) as res:
            self.assertEqual(res.status, 200)
        with Image.open(target_img_path) as im:
            self.assertEqual(im.size, (150, 75))

        # Reset image to original
        url_reset_img = f'http://localhost:{TEST_PORT}/api/reset_image'
        payload_reset_img = json.dumps({
            'target_id': 'trade_discard_0',
            'target_type': 'item',
            'image_path': target_img_path
        }).encode('utf-8')
        req_reset_img = urllib.request.Request(url_reset_img, data=payload_reset_img, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req_reset_img) as res:
            self.assertEqual(res.status, 200)

        # Verify image was restored
        with Image.open(target_img_path) as im:
            self.assertEqual(im.size, (80, 80))

        # Cleanup test image
        if os.path.exists(test_img_path):
            os.remove(test_img_path)
        print('All 4 cropping and reset patterns passed successfully!')

if __name__ == '__main__':
    unittest.main()
