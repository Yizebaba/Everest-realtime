import html

def build_evidence_page(title, source_url, time_str, image_urls, layer_names=None, signature='vx:No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］'):
    esc = html.escape
    title_esc = esc(title)
    url_esc = esc(source_url)
    time_esc = esc(time_str)
    sig_esc = esc(signature)
    
    total = len(image_urls)
    is_multi = total > 1
    
    cards_html = []
    for i, img_url in enumerate(image_urls, 1):
        name = ""
        if layer_names and i - 1 < len(layer_names):
            name = layer_names[i - 1]
        elif is_multi:
            name = f"图层 {i}"
        
        badge = f'<div class="badge">第 {i} / {total} 层 · {esc(name)}</div>' if name else ''
        cards_html.append(f'''
        <div class="card">
            {badge}
            <div class="img-wrap">
                <a href="{esc(img_url)}" target="_blank" title="点击查看大图">
                    <img loading="lazy" src="{esc(img_url)}" alt="监测截图 {i}" />
                </a>
            </div>
            <div class="img-hint">点击图片可看原图，长按可保存分享</div>
        </div>
        ''')
    
    multi_tag = f'<span class="multi-pill">多图层模式 · 共 {total} 层</span>' if is_multi else ''
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0">
    <title>{title_esc}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: #090d16;
            color: #f1f5f9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
            padding: 16px 12px;
            line-height: 1.6;
        }}
        .container {{ max-width: 860px; margin: 0 auto; }}
        .header {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 16px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.35);
        }}
        .title-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 14px;
        }}
        h1 {{ font-size: 22px; color: #38bdf8; font-weight: 700; }}
        .multi-pill {{
            background: rgba(56, 189, 248, 0.2);
            color: #7dd3fc;
            border: 1px solid rgba(56, 189, 248, 0.45);
            font-size: 14px;
            padding: 4px 12px;
            border-radius: 14px;
            font-weight: 600;
        }}
        .meta-box {{
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 14px 16px;
            font-size: 15px;
        }}
        .meta-line {{
            margin-bottom: 10px;
            display: flex;
            align-items: baseline;
            gap: 8px;
        }}
        .meta-line:last-child {{ margin-bottom: 0; }}
        .label {{ color: #94a3b8; flex-shrink: 0; font-weight: 600; font-size: 15px; }}
        .url-link {{
            color: #38bdf8;
            font-size: 15px;
            word-break: break-all;
            text-decoration: underline;
            text-underline-offset: 4px;
            font-weight: 500;
        }}
        .url-link:hover {{ color: #7dd3fc; }}
        .card {{
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
            box-shadow: 0 6px 16px rgba(0,0,0,0.3);
        }}
        .badge {{
            display: inline-block;
            background: #1e293b;
            color: #38bdf8;
            border-left: 4px solid #0284c7;
            font-size: 16px;
            font-weight: 700;
            padding: 6px 14px;
            border-radius: 4px;
            margin-bottom: 14px;
        }}
        .img-wrap img {{
            width: 100%;
            height: auto;
            display: block;
            border-radius: 8px;
            border: 1px solid #334155;
            background: #020617;
        }}
        .img-hint {{
            text-align: center;
            font-size: 12px;
            color: #64748b;
            margin-top: 8px;
        }}
        .footer {{
            text-align: center;
            font-size: 14px;
            color: #94a3b8;
            font-weight: 500;
            padding: 24px 0 12px;
            border-top: 1px solid #1e293b;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title-bar">
                <h1>{title_esc}</h1>
                {multi_tag}
            </div>
            <div class="meta-box">
                <div class="meta-line">
                    <span class="label">来源网址：</span>
                    <a class="url-link" href="{url_esc}" target="_blank" rel="noopener noreferrer">{url_esc}</a>
                </div>
                <div class="meta-line">
                    <span class="label">监测时间：</span>
                    <span style="color:#f1f5f9;">{time_esc}</span>
                </div>
            </div>
        </div>

        <div class="cards-flow">
            {''.join(cards_html)}
        </div>

        <div class="footer">
            {sig_esc}
        </div>
    </div>
</body>
</html>'''
