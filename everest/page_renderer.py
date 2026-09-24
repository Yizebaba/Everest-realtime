import html

def render_notification_page(title, source_url, time_str, image_cards, signature='vx:No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］'):
    """
    World-Class Clean Style D (Bilingual Chinese & English, Devanagari/Nepali completely removed).
    image_cards: list of dicts, each like:
    {
        'layer_cn': '真彩色遥感底图',
        'layer_en': 'MODIS Terra True Color',
        'layer_index': 1,
        'layer_total': 2,
        'image_url': 'https://...',
        'layer_target_url': 'https://...'
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
        
        # Build layer bilingual heading (Chinese + English only)
        layer_parts = []
        if cn:
            layer_parts.append(f'<a class="layer-title-link" href="{esc(jump_url)}" target="_blank" rel="noopener noreferrer">{esc(cn)}</a>')
        if en:
            layer_parts.append(f'<span class="lang-en-text">{esc(en)}</span>')
            
        if not layer_parts and is_multi:
            layer_parts.append(f'<a class="layer-title-link" href="{esc(jump_url)}" target="_blank" rel="noopener noreferrer">图层 {idx}</a>')

        heading_content = '<span class="divider-slash">/</span>'.join(layer_parts)
        badge_html = f'''
        <div class="flow-header">
            <div class="layer-heading-row">
                {heading_content}
            </div>
            <div class="flow-index-tag">LAYER {idx:02d} / {tot:02d}</div>
        </div>
        ''' if layer_parts else ''

        cards_html.append(f'''
        <article class="flow-card">
            {badge_html}
            <div class="flow-image-box">
                <img loading="lazy" src="{esc(img_url)}" alt="{title_esc} 监测截图 {idx}" />
            </div>
        </article>
        ''')

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0">
    <title>{title_esc}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=IBM+Plex+Mono:wght@500;600&family=IBM+Plex+Sans+Devanagari:wght@400;600&family=Inter:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-page: #ffffff;
            --bg-muted: #f8fafc;
            --border-light: #e5e7eb;
            --border-line: #cbd5e1;
            --accent-blue: #0284c7;
            --accent-navy: #0f172a;
            --text-title: #0f172a;
            --text-body: #334155;
            --text-muted: #64748b;
            --text-light: #94a3b8;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-page);
            color: var(--text-body);
            font-family: 'Inter', 'Noto Sans SC', -apple-system, sans-serif;
            padding: 24px 20px 60px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1120px;
            margin: 0 auto;
        }}

        /* 顶部机构标头（取消第三行，仅保留纯净单行英文） */
        .world-topbar {{
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-line);
            margin-bottom: 28px;
        }}

        .name-en {{
            font-family: 'Cormorant Garamond', Georgia, serif;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: var(--text-title);
            line-height: 1.2;
        }}

        /* 主标题区域：底色放宽，文字向右内收 28px，取消尼泊尔语 */
        .event-card {{
            background: var(--bg-muted);
            border: none;
            border-top: 1px solid var(--border-light);
            border-bottom: 1px solid var(--border-light);
            border-radius: 0;
            padding: 24px 28px;
            margin-bottom: 24px;
            box-shadow: none;
        }}

        .event-title-main {{
            font-size: 26px;
            font-weight: 900;
            color: var(--text-title);
            letter-spacing: -0.5px;
            margin-bottom: 8px;
        }}

        .event-title-main a {{
            color: var(--text-title);
            text-decoration: none;
            transition: color 0.15s;
        }}
        .event-title-main a:hover {{
            color: var(--accent-blue);
        }}

        .intl-subtitle-grid {{
            display: flex;
            align-items: center;
        }}

        .sub-item {{
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .sub-tag {{
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 2px 6px;
            border-radius: 4px;
            background: #ffffff;
            border: 1px solid var(--border-light);
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }}

        .sub-text-en {{
            color: var(--text-muted);
            font-weight: 500;
        }}

        /* 来源/时间：横向放宽，取消 Scope（范围） */
        .meta-metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            background: transparent;
            border: none;
            border-bottom: 1px solid var(--border-light);
            border-radius: 0;
            padding: 0 0 20px 0;
            margin-bottom: 36px;
        }}

        .metric {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .metric-label {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-light);
        }}

        .metric-val {{
            font-size: 15px;
            font-weight: 600;
            color: var(--text-title);
            word-break: break-all;
        }}

        .metric-val a {{
            color: var(--accent-blue);
            text-decoration: underline;
            text-underline-offset: 3px;
        }}

        /* 图层流 */
        .layer-flow {{
            display: flex;
            flex-direction: column;
            gap: 40px;
        }}

        .flow-card {{
            background: #ffffff;
            border: none;
            border-radius: 0;
            padding: 0;
            box-shadow: none;
        }}

        .flow-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            margin-bottom: 12px;
            padding: 12px 0 10px 0;
            border-bottom: 1.5px solid var(--text-title);
        }}

        .layer-heading-row {{
            display: flex;
            align-items: baseline;
            flex-wrap: wrap;
            gap: 12px;
            flex: 1;
        }}

        .layer-title-link {{
            font-size: 19px;
            font-weight: 900;
            color: var(--text-title);
            text-decoration: none;
            letter-spacing: -0.2px;
            white-space: nowrap;
            transition: color 0.15s;
        }}
        .layer-title-link:hover {{ color: var(--accent-blue); }}

        .divider-slash {{
            color: var(--border-line);
            font-weight: 300;
            font-size: 15px;
        }}

        .lang-en-text {{
            font-family: 'Inter', sans-serif;
            color: var(--text-muted);
            font-size: 14px;
            font-weight: 500;
        }}

        .flow-index-tag {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 12px;
            font-weight: 700;
            color: var(--text-title);
            background: #f1f5f9;
            border: 1px solid var(--border-line);
            padding: 4px 12px;
            border-radius: 4px;
            white-space: nowrap;
        }}

        .flow-image-box {{
            background: #ffffff;
            border: 1px solid var(--border-light);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        }}

        .flow-image-box img {{
            width: 100%;
            height: auto;
            display: block;
        }}

        /* 页面底部署名：中英双语，取消尼泊尔语 */
        .footer-banner {{
            margin-top: 50px;
            padding: 24px 16px 12px;
            border-top: 1px solid var(--border-line);
            text-align: center;
        }}

        .ft-lead {{
            font-size: 14px;
            font-weight: 800;
            color: var(--text-title);
            margin-bottom: 6px;
            letter-spacing: 0.3px;
        }}

        .ft-sub {{
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 4px;
            letter-spacing: 0.3px;
        }}

        .ft-nepali {{
            font-family: 'IBM Plex Sans Devanagari', sans-serif;
            font-size: 12px;
            color: var(--text-light);
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 顶部机构名（纯净单行英文） -->
        <header class="world-topbar">
            <div class="name-en">MT. EVEREST OBSERVATION INITIATIVE</div>
        </header>

        <!-- 主标题区域：底色放宽，文字向右内收 28px，仅保留中英双语 -->
        <section class="event-card">
            <h1 class="event-title-main">
                <a href="{url_esc}" target="_blank">{title_esc}</a>
            </h1>
            <div class="intl-subtitle-grid">
                <div class="sub-item">
                    <span class="sub-tag">English</span>
                    <span class="sub-text-en">NASA Earth Observatory Spaceborne Telemetry Array</span>
                </div>
            </div>
        </section>

        <!-- 来源/时间：横向放宽，取消 Scope（范围） -->
        <div class="meta-metrics">
            <div class="metric">
                <span class="metric-label">Source</span>
                <span class="metric-val">
                    <a href="{url_esc}" target="_blank">{url_esc}</a>
                </span>
            </div>
            <div class="metric">
                <span class="metric-label">Observed Time</span>
                <span class="metric-val">{time_esc}</span>
            </div>
        </div>

        <!-- 多图层流 -->
        <main class="layer-flow">
            {''.join(cards_html)}
        </main>

        <!-- 页面最底部细线署名：保留尼泊尔语官方名称 -->
        <footer class="footer-banner">
            <div class="ft-lead">WeChat: No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］</div>
            <div class="ft-sub">Mt. Everest Natural Environment Information Monitoring System [Beta]</div>
            <div class="ft-nepali">सगरमाथा बहु-प्रकोप वातावरण अनुगमन प्रणाली (परीक्षण संस्करण)</div>
        </footer>
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
