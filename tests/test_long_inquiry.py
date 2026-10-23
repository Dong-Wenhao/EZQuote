"""Formal version of the PDF's long-input reproduction; no partial success."""
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from test_copilot import business
from fastapi.testclient import TestClient
from backend.requirements import INQUIRY_TOO_LARGE


def test_many_product_segments_are_rejected_without_server_error(business):
    c,_,staff,store=business
    text='cement and '*999+'cement 1 bag. Deliver to Shah Alam.'
    assert len(text)==11024
    with TestClient(c.app,raise_server_exceptions=False) as probe:
        assert probe.get('/api/health').status_code==200
        with store.transaction() as db:
            before=[db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['quotes','requirement_reviews']]
        results=[]
        for endpoint in ['parse','review']:
            body={'text':text,'mode':'requirements'} if endpoint=='parse' else {'inquiry':text,
                'items':[{'sku':'CEM-A-FAST-50','quantity':'1'}],'area':'Shah Alam','fulfilment':'delivery'}
            started=time.perf_counter()
            response=probe.post('/api/inquiries/parse' if endpoint=='parse' else '/api/requirements/review',headers=staff,json=body)
            seconds=time.perf_counter()-started
            health=probe.get('/api/health')
            evidence={'endpoint':endpoint,'characters':len(text),'product_mentions':1000,
                'status_code':response.status_code,'response':response.text[:300],
                'seconds':round(seconds,4),'target_seconds':2.0,'health_after':health.status_code}
            results.append(evidence)
            assert response.status_code==422,evidence
            assert response.json()=={'detail':INQUIRY_TOO_LARGE},evidence
            assert seconds<2.0,evidence
            assert health.status_code==200,evidence
        with store.transaction() as db:
            after=[db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['quotes','requirement_reviews']]
        assert after==before
        output=ROOT/'test-results'
        output.mkdir(parents=True,exist_ok=True)
        (output/'long-inquiry-current.json').write_text(json.dumps({
            'version':c.get('/api/health').json()['version'],'results':results,'quotes_before_after':[before[0],after[0]],
            'reviews_before_after':[before[1],after[1]],'partial_quote_created':False},indent=2),encoding='utf-8')
