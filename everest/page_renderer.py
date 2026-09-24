import html

def render_notification_page(title, source_url, time_str, image_cards, signature='vx:No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］'):
    """
    image_cards: list of dicts, each like:
    {
        'layer_cn': '真彩色遥感底图',
        'layer_en': 'MODIS Terra True Color',
        'layer_index': 1,
        'layer_total': 3,
        'image_url': 'https://...',
        'layer_target_url': 'https://...' (optional target url, default to source_url)
    }
    """
    esc = html.escape
    title_esc = esc(title)
    url_esc = esc(source_url)
    time_esc = esc(time_str)
    sig_esc = esc(signature)
    
    total = len(image_cards)
    is_multi = total > 1

    cards_html = []
    for i, card in enumerate(image_cards, 1):
        if isinstance(card, str):
            img_url = card
            cn = ""
            en = ""
            idx = i
            tot = total
            jump_url = source_url
        else:
            img_url = card.get('image_url', '')
            cn = card.get('layer_cn', '')
            en = card.get('layer_en', '')
            idx = card.get('layer_index', i)
            tot = card.get('layer_total', total)
            jump_url = card.get('layer_target_url') or source_url
        
        badge_html = ""
        if cn or en:
            label_text = f"{cn} · {en}" if (cn and en) else (cn or en)
            badge_html = f'''
            <div class="layer-header">
                <div class="layer-name">{esc(label_text)}</div>
                <div class="layer-index">图层 {idx} / {tot}</div>
            </div>
            '''
        elif is_multi:
            badge_html = f'''
            <div class="layer-header">
                <div class="layer-name">图层 {idx}</div>
                <div class="layer-index">图层 {idx} / {tot}</div>
            </div>
            '''

        sig_block = f'<div class="footer">{sig_esc}</div>' if (i == total) else ''
        cards_html.append(f'''
        <div class="card-box">
            {badge_html}
            <div class="img-wrapper">
                <a href="{esc(jump_url)}" target="_blank" rel="noopener noreferrer">
                    <img loading="lazy" src="{esc(img_url)}" alt="{title_esc} 截图" />
                </a>
            </div>
            {sig_block}
        </div>
        ''')

    multi_badge = f'<div class="multi-tag">多图层模式 · 共 {total} 层</div>' if is_multi else ''

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
            padding: 16px 14px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 880px;
            margin: 0 auto;
        }}
        .top-panel {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 18px 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        }}
        .title-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 14px;
            border-bottom: 1px solid #334155;
            padding-bottom: 12px;
        }}
        h1 {{
            font-size: 20px;
            color: #38bdf8;
            font-weight: 700;
        }}
        .multi-tag {{
            background: rgba(56, 189, 248, 0.15);
            color: #7dd3fc;
            border: 1px solid rgba(56, 189, 248, 0.35);
            font-size: 13px;
            padding: 3px 12px;
            border-radius: 20px;
            font-weight: 600;
        }}
        .meta-line {{
            margin-bottom: 10px;
            font-size: 15px;
            display: flex;
            align-items: flex-start;
            gap: 8px;
        }}
        .meta-line:last-child {{ margin-bottom: 0; }}
        .label {{
            color: #94a3b8;
            font-weight: 600;
            flex-shrink: 0;
        }}
        .source-url {{
            color: #38bdf8;
            word-break: break-all;
            text-decoration: underline;
            text-underline-offset: 4px;
            font-weight: 500;
        }}
        .source-url:hover {{
            color: #7dd3fc;
        }}
        .card-box {{
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 22px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.35);
        }}
        .layer-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #1e293b;
            border-left: 4px solid #38bdf8;
            border-radius: 4px;
            padding: 8px 14px;
            margin-bottom: 14px;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .layer-name {{
            color: #f8fafc;
            font-size: 15px;
            font-weight: 700;
            letter-spacing: 0.3px;
        }}
        .layer-index {{
            background: #334155;
            color: #93c5fd;
            font-size: 12px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .img-wrapper a {{
            display: block;
            cursor: pointer;
        }}
        .img-wrapper img {{
            width: 100%;
            height: auto;
            display: block;
            border-radius: 8px;
            border: 1px solid #334155;
            background: #020617;
            transition: opacity 0.2s;
        }}
        .img-wrapper a:hover img {{
            opacity: 0.92;
        }}
        .footer {{
            text-align: center;
            font-size: 13px;
            color: #94a3b8;
            padding: 24px 0 14px;
            border-top: 1px solid #1e293b;
            margin-top: 24px;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="top-panel">
            <div class="title-bar">
                <h1>{title_esc}</h1>
                {multi_badge}
            </div>
            <div class="meta-line">
                <span class="label">来源网址：</span>
                <a class="source-url" href="{url_esc}" target="_blank" rel="noopener noreferrer">{url_esc}</a>
            </div>
            <div class="meta-line">
                <span class="label">监测时间：</span>
                <span style="color:#f1f5f9;">{time_esc}</span>
            </div>
        </div>

        <div class="cards-stream">
            {''.join(cards_html)}
        </div>
    </div>
</body>
</html>'''

def build_evidence_page(title, source_url, time_str, image_urls, layer_names=None, signature='vx:No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］'):
    cards = []
    for i, u in enumerate(image_urls):
        name = layer_names[i] if layer_names and i < len(layer_names) else ""
        cards.append({
            'layer_cn': name,
            'layer_en': '',
            'layer_index': i + 1,
            'layer_total': len(image_urls),
            'image_url': u,
            'layer_target_url': source_url
        })
    return render_notification_page(title, source_url, time_str, cards, signature)
