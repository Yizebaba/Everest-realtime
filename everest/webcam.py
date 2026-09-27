import io
from pathlib import Path

import requests
from PIL import Image, ImageStat

from .core import now


def _visual_signature(image):
    """Use low-resolution grayscale values so broad visibility changes outrank JPEG noise."""
    image = image.convert('L').resize((32, 18))
    return bytes(image.get_flattened_data())


def collect_camera(source, folder, settings, run_id):
    """Download the configured camera frame for visual change detection."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    frame_url = source['camera_frame_url']
    result = {
        'source': source,
        'run_id': run_id,
        'result': 'unknown',
        'retrieved_at': now(),
        'source_time': None,
        'content': [],
        'matches': [],
        'cards': [],
        'error': '',
        'pages': [],
        'network_records': [],
        'map_images': [],
        'article_records': [],
        'acquisition_errors': [],
        'pending_urls': [],
        'alert_screenshots': [],
    }
    try:
        response = requests.get(
            frame_url,
            timeout=settings['timeout_seconds'],
            headers={'User-Agent': 'Everest-realtime/4.0', 'Cache-Control': 'no-cache'},
        )
        response.raise_for_status()
        with Image.open(io.BytesIO(response.content)) as image:
            image = image.convert('RGB')
            if image.width < 100 or image.height < 100:
                raise ValueError('Camera frame is too small')
            if max(ImageStat.Stat(image.convert('L')).var) < 4:
                raise ValueError('Camera frame is blank')
            target = folder / 'camera-frame.jpg'
            image.save(target, quality=95)
            result['camera_frame_signature'] = _visual_signature(image).hex()
            result['camera_frame_path'] = str(target)
            result['camera_frame_size'] = [image.width, image.height]
        result['content'] = [f"Windy camera frame {source['camera_id']}"]
        result['matches'] = list(result['content'])
        result['result'] = 'found'
        result['relevance'] = 'in_scope'
        result['event_status'] = 'candidate'
        result['coverage'] = 'complete_for_requested_pages'
        result['pages'] = [{'url': source['url'], 'kind': 'camera', 'content_type': 'image/jpeg',
                            'retrieved_at': result['retrieved_at'], 'items': 1}]
    except Exception as exc:
        result['error'] = type(exc).__name__
        result['acquisition_errors'].append({'url': frame_url, 'stage': 'camera_frame', 'error': type(exc).__name__})
        result['coverage'] = 'partial'
    return result
