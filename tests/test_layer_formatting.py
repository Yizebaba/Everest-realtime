import sys
from pathlib import Path
sys.path.insert(0, r"E:\Everest-realtime")

from everest.delivery import deliver, destination
from everest.core import Store, read_json
import hashlib

def test_layer_names_translated_and_paired_with_images(tmp_path):
    store = Store(tmp_path / "test.db")
    try:
        card1 = tmp_path / "card1.png"; card1.write_bytes(b"c1")
        card2 = tmp_path / "card2.png"; card2.write_bytes(b"c2")
        
        result = {
            "run_id": "run-map",
            "source": {"rule_id": "weather-06", "name": "Windy", "url": "https://www.windy.com/"},
            "result": "found",
            "retrieved_at": "2026-09-15T00:00:00Z",
            "matches": ["sample"],
            "image_kind": "everest_map_view",
            "map_view_layers": ["wind", "rain"],
            "map_view_items": [
                {"layer": "wind", "name": "珠峰风力图层", "path": str(card1)},
                {"layer": "rain", "name": "珠峰降雨/对流图层", "path": str(card2)},
            ],
            "cards": [str(card1), str(card2)],
            "card_hashes": {
                str(card1): hashlib.sha256(b"c1").hexdigest(),
                str(card2): hashlib.sha256(b"c2").hexdigest(),
            }
        }
        path = tmp_path / "result.json"
        path.write_text(__import__("json").dumps(result), encoding="utf-8")
        
        cfg = {"serverchan": {"sendkey": "mock-key"}}
        store.record(result, path, "all", destination(cfg))
        
        sent = []
        def mock_sender(config, title, text):
            sent.append((title, text))
            return {"code": 0}
            
        def mock_uploader(path, settings):
            return f"https://img.test/{Path(path).name}"
            
        stats = deliver(store, "run-map", cfg, {"notification_interval_seconds": 0},
                        uploader=mock_uploader, sender=mock_sender, sleeper=lambda _: None)
        
        assert stats["accepted"] == 1
        assert len(sent) == 1
        title, text = sent[0]
        
        print("Generated notification text preview:\n" + "-"*40)
        print(text)
        print("-" * 40)
        
        # Verify Chinese layer names are present
        assert "珠峰风力图层" in text
        assert "珠峰降雨/对流图层" in text

        # Verify each image is paired with its Chinese layer name in correct order
        assert "![珠峰风力图层](https://img.test/card1.png)" in text
        assert "![珠峰降雨/对流图层](https://img.test/card2.png)" in text
        
        # Verify signature
        assert text.endswith("vx:No1-Shine ｜ 珠峰自然环境信息监控系统［测试版］")
        print("PASS: Map layers properly translated and paired in order with images.")
    finally:
        store.close()

if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_layer_names_translated_and_paired_with_images(Path(td))
