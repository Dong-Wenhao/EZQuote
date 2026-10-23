"""Independent follow-up checks: do not silently omit or truncate new expressions."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_copilot import business
import pytest

CASES=[
 ('unknown-extra','Need 20 bags cement 50kg and sand. Deliver to Shah Alam.','20'),
 ('underscore-number','Need 1_020 bags cement 50kg. Deliver to Shah Alam.','20'),
 ('fullwidth-range','Need 20／30 bags cement 50kg. Deliver to Shah Alam.','30'),
]

@pytest.mark.parametrize('name,text,bad_quantity',CASES)
def test_ambiguous_or_uncovered_input_cannot_become_approved_quote(business,name,text,bad_quantity):
    c,boss,staff,store=business
    parsed=c.post('/api/inquiries/parse',headers=staff,json={'text':text,'mode':'requirements'}).json()
    selected=[{'sku':i['sku'],'quantity':i['quantity'],'source_id':i['source_id']} for i in parsed['items'] if i['sku']]
    evidence={'case':name,'text':text,'parsed_status':parsed['status'],'parsed_can_quote':parsed['can_quote'],'selected':selected}
    if parsed['can_quote']:
        review=c.post('/api/requirements/review',headers=staff,json={'inquiry':text,'items':selected,'area':'Shah Alam','fulfilment':'delivery'})
        evidence['review_status']=review.status_code
        evidence['review_can_quote']=review.json().get('can_quote')
        if review.status_code==200 and review.json().get('can_quote'):
            body={'customer':'Independent synthetic QA','inquiry':text,'language':'en','items':[{k:i[k] for k in ('sku','quantity')} for i in selected],'source_confirmed':True,'request_key':'independent-'+name,'pricing_enabled':True,'delivery_area':'Shah Alam','fulfilment':'delivery','review_id':review.json()['review_id']}
            q=c.post('/api/quotes',headers=staff,json=body)
            evidence['create_status']=q.status_code
            if q.status_code==200:
                q=q.json();qid=q['id']
                submit=c.post('/api/quotes/'+qid+'/submit',headers=staff,json={'expected_revision':1})
                approve=c.post('/api/quotes/'+qid+'/approve',headers=boss,json={'expected_revision':1})
                evidence.update(submit_status=submit.status_code,approve_status=approve.status_code)
                if approve.status_code==200:
                    q=approve.json();evidence.update(final_status=q['status'],total=q['total'],items=[{k:i[k] for k in ('sku','quantity')} for i in q['items']])
    output=ROOT/'test-results'
    output.mkdir(parents=True,exist_ok=True)
    (output/('remaining-'+name+'.json')).write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not parsed['can_quote'],evidence
