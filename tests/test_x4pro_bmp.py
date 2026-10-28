#!/usr/bin/env python3
"""Tests for the X4 Pro sleep-screen BMP endpoint (no network)."""
import io
import logging
import os
import struct
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'modules'))
logging.basicConfig(level=logging.CRITICAL)

from PIL import Image  # noqa: E402

import main_web  # noqa: E402


def make_landscape():
    """800x480 white image with a black 40x20 block at the top-left."""
    img = Image.new('RGB', (800, 480), (255, 255, 255))
    img.paste((0, 0, 0), (0, 0, 40, 20))
    return img


def make_instance(image, config=None):
    # Skip __init__ (it would hit the network and the filesystem)
    inst = object.__new__(main_web.EPaperWeatherWeb)
    inst.latest_image = image
    inst.config = config or {}
    inst.width, inst.height = 800, 480
    return inst


class X4ProBmpTest(unittest.TestCase):
    def setUp(self):
        self._orig = main_web.weather_web
        main_web.weather_web = make_instance(make_landscape())
        self.client = main_web.app.test_client()

    def tearDown(self):
        main_web.weather_web = self._orig

    def decode(self, resp):
        return Image.open(io.BytesIO(resp.data)).convert('L')

    def test_headers(self):
        r = self.client.get('/weather-x4pro.bmp')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, 'image/bmp')
        self.assertIn('no-store', r.headers['Cache-Control'])

    def test_bmp_header(self):
        data = self.client.get('/weather-x4pro.bmp').data
        self.assertEqual(data[:2], b'BM')
        self.assertLess(len(data), 1024 * 1024)
        width, height, _planes, bpp, comp = struct.unpack('<iiHHI', data[18:34])
        self.assertEqual((width, abs(height), bpp, comp), (480, 800, 1, 0))
        dib_size = struct.unpack('<I', data[14:18])[0]
        pal = data[14 + dib_size:14 + dib_size + 8]
        self.assertEqual(pal[0:3], b'\x00\x00\x00')  # entry 0 = black (BGR)
        self.assertEqual(pal[4:7], b'\xff\xff\xff')  # entry 1 = white

    def test_default_rotation_90(self):
        img = self.decode(self.client.get('/weather-x4pro.bmp'))
        self.assertEqual(img.size, (480, 800))
        # ROTATE_90 (counter-clockwise): top-left goes to bottom-left
        self.assertEqual(img.getpixel((5, 795)), 0)
        self.assertEqual(img.getpixel((15, 770)), 0)
        self.assertEqual(img.getpixel((5, 5)), 255)
        self.assertEqual(img.getpixel((475, 795)), 255)
        self.assertEqual(img.getpixel((5, 750)), 255)
        self.assertEqual(img.getpixel((25, 795)), 255)
        self.assertEqual(set(img.getdata()), {0, 255})

    def test_rotate_270(self):
        img = self.decode(self.client.get('/weather-x4pro.bmp?rotate=270'))
        self.assertEqual(img.size, (480, 800))
        # ROTATE_270 (clockwise): top-left goes to top-right
        self.assertEqual(img.getpixel((475, 5)), 0)
        self.assertEqual(img.getpixel((475, 35)), 0)
        self.assertEqual(img.getpixel((5, 5)), 255)
        self.assertEqual(img.getpixel((5, 795)), 255)
        self.assertEqual(img.getpixel((455, 5)), 255)
        self.assertEqual(set(img.getdata()), {0, 255})

    def test_config_rotation(self):
        main_web.weather_web = make_instance(
            make_landscape(), {'x4pro': {'rotation': 270}})
        img = self.decode(self.client.get('/weather-x4pro.bmp'))
        self.assertEqual(img.getpixel((475, 5)), 0)
        # Query param overrides config
        img = self.decode(self.client.get('/weather-x4pro.bmp?rotate=90'))
        self.assertEqual(img.getpixel((5, 795)), 0)

    def test_503_without_image(self):
        main_web.weather_web = make_instance(None)
        r = self.client.get('/weather-x4pro.bmp')
        self.assertEqual(r.status_code, 503)
        self.assertNotEqual(r.mimetype, 'image/bmp')

    def test_400_bad_rotate(self):
        self.assertEqual(
            self.client.get('/weather-x4pro.bmp?rotate=45').status_code, 400)

    def test_weather_png_unchanged(self):
        r = self.client.get('/weather.png')
        self.assertEqual(r.status_code, 200)
        img = Image.open(io.BytesIO(r.data))
        self.assertEqual((img.format, img.size), ('PNG', (800, 480)))


if __name__ == '__main__':
    unittest.main()
