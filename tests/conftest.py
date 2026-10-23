"""Shared isolated fixtures for requirement-review regression tests."""
import base64
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.business import read_business

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def business_data():
    return read_business(base64.b64encode((ROOT/'samples/business_demo.xlsx').read_bytes()).decode())[0]

@pytest.fixture
def reviewed_app(tmp_path):
    class RejectNetwork:
        def post(self,*a,**k):raise AssertionError('Unexpected external API call')
    app=create_app(tmp_path,transport=RejectNetwork(),start_worker=False)
    with TestClient(app) as c:
        boss={'Authorization':'Bearer '+c.post('/api/setup',json={'shop_name':'Review regression','boss_password':'review-boss-123','staff_password':'review-staff-123'}).json()['token']}
        staff={'Authorization':'Bearer '+c.post('/api/login',json={'username':'staff','password':'review-staff-123'}).json()['token']}
        r=c.post('/api/business/import',headers=boss,json={'filename':'business_demo.xlsx','content_b64':base64.b64encode((ROOT/'samples/business_demo.xlsx').read_bytes()).decode()})
        assert r.status_code==200,r.text
        yield c,boss,staff,app
