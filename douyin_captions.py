"""Timed Douyin captions. Numeric JSON is accepted only for known ms fields."""
import html
import json
import math
import re
import time
from urllib.parse import urlparse

import requests


CAPTION_HOSTS = ('douyinpic.com', 'douyinvod.com', 'douyin.com', 'byteimg.com', 'zjcdn.com')
TIMECODE = r'(?:\d{1,3}:)?[0-5]\d:[0-5]\d[.,]\d{3}'
TIMING = re.compile(rf'^\s*({TIMECODE})\s+-->\s+({TIMECODE})(?:\s+.*)?$')


def seconds(value):
    total = 0
    for part in value.replace(',', '.').split(':'):
        total = total * 60 + float(part)
    return total


def parse_caption(payload):
    payload = payload.lstrip('\ufeff \r\n\t')
    if payload.startswith('{'):
        data = json.loads(payload)
        return [
            [float(x['start_time']) / 1000, float(x['end_time']) / 1000, x['text']]
            for x in data.get('utterances', [])
        ]
    rows = []
    for block in re.split(r'\r?\n\s*\r?\n', payload):
        lines = block.splitlines()
        for i, line in enumerate(lines[:2]):
            timing = TIMING.fullmatch(line)
            if timing:
                text = html.unescape(re.sub(r'<[^>]*>', '', ' '.join(lines[i+1:])))
                rows.append([seconds(timing[1]), seconds(timing[2]), text])
                break
    return rows


def clean_cues(rows, duration):
    if not isinstance(rows, list) or not 0 < duration <= 7200:
        return []
    cues = set()
    for row in rows[:10000]:
        if not isinstance(row, list) or len(row) != 3:
            continue
        a, b, text = row
        if (type(a) not in (int, float) or type(b) not in (int, float)
                or not math.isfinite(a) or not math.isfinite(b) or not 0 <= a < b <= duration + .75
                or not isinstance(text, str) or not 0 < len(text.strip()) <= 600):
            continue
        a, b = round(a, 3), round(min(b, duration), 3)
        if b > a:
            cues.add((a, b, text.strip()))
    return sorted(cues)


def fetch_caption(url, validate, cancelled, deadline):
    host = urlparse(url).hostname or ''
    if not any(host == d or host.endswith('.'+d) for d in CAPTION_HOSTS):
        return []
    validate(url)
    if cancelled.is_set() or time.monotonic() >= deadline:
        return []
    with requests.get(url, headers={'Referer': 'https://www.douyin.com/'}, timeout=(2, 2),
                      allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            return []
        data = bytearray()
        for chunk in response.iter_content(16384):
            if cancelled.is_set() or time.monotonic() >= deadline or len(data)+len(chunk) > 1_000_000:
                return []
            data.extend(chunk)
        return parse_caption(data.decode('utf-8-sig'))


def covered_cues(cues, start, end):
    """Prefer caption-backed spans; use audio on a window with a large gap."""
    selected = []
    covered = start
    for a, b, text in cues:
        if a >= end:
            break
        if b <= start:
            continue
        if a > covered + 3:
            return []
        if a >= start:
            selected.append({'word': text, 'start': a, 'end': b})
        covered = max(covered, b)
    return selected if covered >= end - 3 else []
