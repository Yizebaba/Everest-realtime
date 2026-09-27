from everest.page_renderer import render_notification_page


def test_evidence_page_uses_nepali_subtitle_and_consistent_signature():
    page = render_notification_page(
        '产品名称 · Windy',
        'https://example.test/source',
        '2026-09-24T00:00:00Z',
        [{'layer_cn': '珠峰风力图层', 'layer_index': 1, 'layer_total': 1,
          'image_url': 'https://example.test/image.png', 'layer_target_url': 'https://example.test/source'}],
    )

    assert '<span class="sub-tag">नेपाली</span>' in page
    assert 'class="sub-text-ne"' in page
    assert '.sub-text-ne' in page
    assert page.count('WeChat / VX : No1-Shine') == 1
    assert 'Mt. Everest Natural Environment Information Monitoring System [Beta]' in page
    assert 'सगरमाथा बहु-प्रकोप वातावरण अनुगमन प्रणाली (परीक्षण संस्करण)' in page
    assert 'NASA Earth Observatory Spaceborne Telemetry Array' not in page


def test_evidence_page_renders_bilingual_layer_title_on_one_line():
    page = render_notification_page(
        '产品名称 · Windy', 'https://example.test/source', '2026-09-24T00:00:00Z',
        [{'layer_cn': '珠峰风力图层', 'layer_en': 'Mt. Everest Wind Layer', 'layer_index': 1,
          'layer_total': 1, 'image_url': 'https://example.test/image.png',
          'layer_target_url': 'https://example.test/source'}],
    )
    assert '珠峰风力图层' in page and 'Mt. Everest Wind Layer' in page
    assert 'white-space: nowrap' in page
