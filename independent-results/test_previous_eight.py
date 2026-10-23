"""Independent requirement correctness tests; known failures in supplied v1.4.0."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_copilot import business
import pytest


def parse(business, text):
    client, _, staff, _ = business
    response = client.post('/api/inquiries/parse', headers=staff, json={'text': text, 'mode': 'requirements'})
    assert response.status_code == 200, response.text
    return response.json()


def test_thousands_separator_never_silently_reduces_quantity(business):
    r = parse(business, 'Need 1,020 bags cement 50kg. Deliver to Shah Alam.')
    assert r['status'] != 'READY' or r['items'][0]['quantity'] == '1020', r


def test_equal_quantity_two_products_never_silently_drops_a_product(business):
    r = parse(business, 'Need 20 bags cement for plastering and 20 bags nails. Deliver to Shah Alam.')
    assert r['status'] != 'READY' or len(r['items']) == 2, r


@pytest.mark.parametrize('text', [
    'Need 20 bags cement for plastering, not fast setting. Deliver to Shah Alam.',
    '\u6211\u898120\u888b\u6c34\u6ce5\u7528\u4e8e\u62b9\u7070\uff0c\u4e0d\u8981\u901f\u51dd\uff0c\u9001\u5230\u838e\u963f\u5357\u3002',
])
def test_excluded_preference_not_recommended(business, text):
    r = parse(business, text)
    assert r['status'] != 'READY' or r['items'][0]['sku'] != 'CEM-A-FAST-50', r


def test_excluded_brand_not_recommended(business):
    r = parse(business, 'Need 20 bags cement for plastering. No Brand A please. Deliver to Shah Alam.')
    assert r['status'] != 'READY' or r['items'][0]['best_match']['brand'] != 'Brand A', r


@pytest.mark.parametrize('text', [
    'Need 20 bags cement 50kg. Do not pick up; deliver to Shah Alam.',
    '\u6211\u898120\u888b\u6c34\u6ce550kg\uff0c\u4e0d\u8981\u81ea\u63d0\uff0c\u9001\u5230\u838e\u963f\u5357\u3002',
])
def test_delivery_not_changed_to_pickup_by_negated_phrase(business, text):
    r = parse(business, text)
    assert r['status'] != 'READY' or r['requirement']['fulfilment'] == 'delivery', r


def test_preference_continuation_line_is_not_an_extra_product(business):
    r = parse(business, 'Need 20 bags cement for plastering.\nPrefer fast setting.\nDeliver to Shah Alam.')
    assert r['status'] == 'READY' and len(r['items']) == 1 and r['items'][0]['sku'] == 'CEM-A-FAST-50', r
