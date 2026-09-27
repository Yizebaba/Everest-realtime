import base64
import requests
from pathlib import Path

def upload_image_to_github(path, owner='Yizebaba', repo='Everest-realtime', token_file=None):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Image not found: {path}")
    
    token = None
    candidates = [
        token_file,
        Path('/app/github_token.txt'),
        Path('D:/Zhufenjianche/github_token.txt'),
        Path('/tmp/github_token.txt')
    ]
    for c in candidates:
        if c and Path(c).is_file():
            token = Path(c).read_text(encoding='utf-8').strip()
            break
            
    if not token:
        raise ValueError("GitHub token not found for image upload")

    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Everest-Image-Publisher'
    }
    
    file_bytes = p.read_bytes()
    content_b64 = base64.b64encode(file_bytes).decode('utf-8')
    rel_path = f"evidence/images/{p.name}"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{rel_path}"
    
    get_res = requests.get(url, headers=headers)
    sha = get_res.json().get('sha') if get_res.status_code == 200 else None
    
    payload = {
        'message': f'upload: evidence image {p.name}',
        'content': content_b64
    }
    if sha:
        payload['sha'] = sha
        
    put_res = requests.put(url, headers=headers, json=payload, timeout=30)
    if put_res.status_code in (200, 201):
        return f"https://{owner}.github.io/{repo}/{rel_path}"
    raise ValueError(f"GitHub image upload failed: {put_res.status_code} {put_res.text[:100]}")
