"""Development-only synthetic provider; never imported by run.py."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if os.getenv("WA_QUOTE_FIXTURE") != "1" or not os.getenv("WA_QUOTE_DATA"):
    raise SystemExit("Use this fixture only through tests/mobile_browser.mjs with a temporary data directory")

from backend.app import create_app
from backend.network import ServiceError


class SyntheticProvider:
    def __init__(self):
        self.phone = []

    def post(self, url, token, body, timeout=45):
        if "SYNTHETIC" not in token:
            raise ServiceError("fixture_rejects_real_credentials")
        if "api.openai.com" in url:
            text = json.loads(body["input"])["inquiry"]
            expected = "A牌50kg水泥二十袋，还有 Brand A PVC pipe 20mm five pieces"
            if text != expected:
                raise ServiceError("fixture_unknown_inquiry")
            rows = [
                {"source_text": "A牌50kg水泥二十袋", "normalized_text": "Brand A Cement 50kg 20 bags",
                 "evidence": {"product": "水泥", "brand": "A牌", "spec": "50kg", "quantity": "二十", "unit": "袋"}, "missing_fields": []},
                {"source_text": "Brand A PVC pipe 20mm five pieces", "normalized_text": "Brand A PVC pipe 20mm 5 pieces",
                 "evidence": {"product": "PVC pipe", "brand": "Brand A", "spec": "20mm", "quantity": "five", "unit": "pieces"}, "missing_fields": []},
            ]
            return {"status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": json.dumps({"language": "zh", "items": rows}, ensure_ascii=False)}
            ]}]}
        self.phone.append(body)
        return {"messages": [{"id": "wamid.SYNTHETIC-PHONE-NOT-SENT"}]}


provider = SyntheticProvider()
app = create_app(os.environ["WA_QUOTE_DATA"], transport=provider)


@app.get("/__fixture/phone")
def recorded_phone():
    return provider.phone


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
