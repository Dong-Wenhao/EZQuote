"""Independent boundary checks from the user's requested self-review of v1.5."""
import json
from urllib.parse import urlparse
from decimal import Decimal
import pytest
from backend.requirements import understand
from backend.requirement_tokens import quantities,VERSION
from backend.catalog import UNITS,parse_inquiry

TEXT='Need 20 bags fast setting cement for plastering. Deliver to Shah Alam.'
RANGES=['20 or 30','20 to 30','20-30','20/30','20 and 30','20×30','twenty or thirty','二十或三十','20 atau 30']


def review_body(text=TEXT,items=None):
    return {'inquiry':text,'items':items or [{'sku':'CEM-A-FAST-50','quantity':'20'}],'area':'Shah Alam','fulfilment':'delivery'}


def quote_body(checked,body,key='self-review-quote-001'):
    return {'customer':'Synthetic self-review customer','inquiry':body['inquiry'],'language':'en','source_confirmed':True,
            'items':[{k:i[k] for k in ('sku','quantity')} for i in body['items']],'pricing_enabled':True,
            'delivery_area':body['area'],'fulfilment':body['fulfilment'],'request_key':key,'review_id':checked['review_id']}


@pytest.mark.parametrize('raw',RANGES)
def test_alternative_and_range_quantities_cannot_become_a_single_endpoint(business_data,raw):
    mentions=quantities('Need '+raw+' bags cement 50kg',UNITS)
    assert len(mentions)==1 and mentions[0]['raw']==raw
    assert mentions[0]['value'] is None and mentions[0]['error']=='multiple_quantities'
    d=understand('Need '+raw+' bags cement 50kg. Deliver to Shah Alam.',business_data['products'],business_data)
    assert not d['can_quote'] and d['items'][0]['quantity']==''
    assert 'multiple_quantities' in d['items'][0]['issues']


def test_ranges_require_editing_the_inquiry_instead_of_a_general_confirmation(reviewed_app):
    c,_,staff,_=reviewed_app
    body=review_body('Need 20 or 30 bags fast setting cement. Deliver to Shah Alam.',[{'sku':'CEM-A-FAST-50','quantity':'30'}])
    r=c.post('/api/requirements/review',headers=staff,json=body)
    assert r.status_code==200 and not r.json()['can_quote']
    problem=next(p for p in r.json()['issue_details'] if p['code']=='multiple_quantities')
    forged=c.post('/api/requirements/review',headers=staff,json={**body,'corrections':[{'issue_id':problem['id'],'value':'30','reason':'Looks okay to me'}]})
    assert forged.status_code==422
    assert c.get('/api/quotes',headers=staff).json()==[]


@pytest.mark.parametrize('continuation,expected',[
 ('Prefer fast setting, deliver to Shah Alam.','CEM-A-FAST-50'),
 ('No Brand A please, deliver to Shah Alam.','CEM-C-PRO-50'),
 ('50kg. Deliver to Shah Alam.','CEM-A-50'),
])
def test_delivery_continuations_preserve_preferences_brands_and_specs(business_data,continuation,expected):
    d=understand('Need 20 bags cement for plastering.\n'+continuation,business_data['products'],business_data)
    assert d['can_quote'] and len(d['items'])==1,d
    assert d['items'][0]['sku']==expected and d['items'][0]['quantity']=='20'
    assert d['requirement']['area']=='Shah Alam' and d['requirement']['fulfilment']=='delivery'


def test_unknown_product_on_a_delivery_line_is_retained_and_cannot_disappear(reviewed_app):
    c,_,staff,_=reviewed_app;text='Need 20 bags cement for plastering.\n10 bags sand, deliver to Shah Alam.'
    parsed=c.post('/api/inquiries/parse',headers=staff,json={'text':text,'mode':'requirements'}).json()
    assert not parsed['can_quote'] and len(parsed['items'])==2
    assert parsed['items'][1]['quantity']=='10' and 'sand' in parsed['items'][1]['source_text']
    known=parsed['items'][0]
    r=c.post('/api/requirements/review',headers=staff,json=review_body(text,[{k:known[k] for k in ('sku','quantity','source_id')}]))
    assert r.status_code==200 and not r.json()['can_quote']
    assert any(p['code']=='missing_product' and 'sand' in p['source_text'] for p in r.json()['issue_details'])


@pytest.mark.parametrize('text,expected_method,excluded_brand,excluded_preference',[
 ('Need 20 bags cement for plastering. No Brand A, Brand C please. Deliver to Shah Alam.','delivery','Brand A',None),
 ('我要20袋水泥用于抹灰，速凝不要，送到莎阿南。','delivery',None,'fast_setting'),
 ('我要20袋水泥50kg，自提不要，送到莎阿南。','delivery',None,None),
 ('Need 20 bags cement for plastering, fast setting not wanted. Deliver to Shah Alam.','delivery',None,'fast_setting'),
 ('Mahu 20 beg simen untuk melepa, cepat kering tak mahu. Hantar ke Shah Alam.','delivery',None,'fast_setting'),
])
def test_negation_stays_with_its_condition_and_accepts_common_postfix_forms(business_data,text,expected_method,excluded_brand,excluded_preference):
    d=understand(text,business_data['products'],business_data);assert d['can_quote'],d
    selected=[p for p in business_data['products'] if p['sku'] in {i['sku'] for i in d['items']}]
    assert d['requirement']['fulfilment']==expected_method
    if excluded_brand:assert all(p['brand']!=excluded_brand for p in selected) and all(p['brand']=='Brand C' for p in selected)
    if excluded_preference:assert all(excluded_preference not in p['preferences'] for p in selected)


def test_optional_postfix_preference_is_clarified_instead_of_treated_as_required(business_data):
    d=understand('Need 20 bags cement for plastering, fast setting is not required. Deliver to Shah Alam.',business_data['products'],business_data)
    assert not d['can_quote'] and any(p['code']=='negation_ambiguous' for p in d['issue_details'])


@pytest.mark.parametrize('value',['oops','NaN','Infinity','1e10000000','-1','0','1.5'])
def test_bad_selected_quantities_return_validation_errors_without_server_failures(reviewed_app,value):
    c,_,staff,_=reviewed_app
    r=c.post('/api/requirements/review',headers=staff,json=review_body(items=[{'sku':'CEM-A-FAST-50','quantity':value}]))
    assert r.status_code==422,r.text
    assert c.get('/api/quotes',headers=staff).json()==[]


def test_extra_product_has_an_actionable_row_and_specific_audited_confirmation(reviewed_app):
    c,_,staff,_=reviewed_app
    source=c.post('/api/inquiries/parse',headers=staff,json={'text':TEXT,'mode':'requirements'}).json()['items'][0]['source_id']
    body=review_body(items=[{'sku':'CEM-A-FAST-50','quantity':'20','source_id':source},{'sku':'NAIL-A-1','quantity':'5'}])
    first=c.post('/api/requirements/review',headers=staff,json=body).json()
    problem=next(p for p in first['issue_details'] if p['code']=='extra_product')
    assert problem['item_index']==1 and problem['expected_value']=={'sku':'NAIL-A-1','quantity':'5'}
    accepted=c.post('/api/requirements/review',headers=staff,json={**body,'corrections':[{'issue_id':problem['id'],'value':problem['expected_value'],'reason':'Customer also ordered five bags of nails'}]}).json()
    assert accepted['can_quote']
    saved=c.post('/api/quotes',headers=staff,json=quote_body(accepted,body))
    assert saved.status_code==200 and len(saved.json()['items'])==2
    assert any(p['code']=='extra_product' for p in saved.json()['review']['resolutions'])


@pytest.mark.parametrize('raw,ready,expected',[('1,020',True,'1020'),('1,02',False,''),('20 or 30',False,''),('twenty',True,'20')])
def test_price_list_mode_uses_the_same_complete_numeric_tokens(business_data,raw,ready,expected):
    d=parse_inquiry('CEM-A-50 '+raw+' bags',business_data['products'])
    assert (d['status']=='READY')==ready,d
    assert d['items'][0]['quantity']==expected
    assert d['items'][0]['quantity']!='2' and (expected=='20' or d['items'][0]['quantity']!='20')


def test_price_list_mode_does_not_merge_equal_quantity_mentions(business_data):
    d=parse_inquiry('CEM-A-50 20 bags and NAIL-A-1 20 bags',business_data['products'])
    assert d['status']=='NEEDS_INFO' and 'multiple_quantities' in d['items'][0]['issues']


def test_phone_review_exposes_manual_reason_and_the_need_for_a_new_review(reviewed_app):
    c,boss,staff,app=reviewed_app
    body=review_body(items=[{'sku':'CEM-A-FAST-50','quantity':'21'}])
    first=c.post('/api/requirements/review',headers=staff,json=body).json()
    p=next(p for p in first['issue_details'] if p['code']=='quantity_changed')
    checked=c.post('/api/requirements/review',headers=staff,json={**body,'corrections':[{'issue_id':p['id'],'value':'21','reason':'Customer confirmed twenty-one bags'}]}).json()
    q=c.post('/api/quotes',headers=staff,json=quote_body(checked,body)).json()
    assert c.post('/api/quotes/'+q['id']+'/submit',headers=staff,json={'expected_revision':1}).status_code==200
    assert c.put('/api/integrations',headers=boss,json={'public_url':'https://phone.example.test'}).status_code==200
    link=c.post('/api/quotes/'+q['id']+'/mobile-link',headers=staff,json={'expected_revision':1}).json()
    phone={'Authorization':'Bearer '+urlparse(link['url']).fragment}
    current=c.post('/api/mobile/review',headers=phone).json()['quote']
    assert not current['review_required']
    assert any(p['resolution']['reason']=='Customer confirmed twenty-one bags' for p in current['pricing']['requirement']['resolutions'])
    with app.state.store.transaction() as db:db.execute("UPDATE requirement_reviews SET parser_version='requirements_rules_v2'")
    current=c.post('/api/mobile/review',headers=phone).json()['quote']
    assert current['review_required']
    blocked=c.post('/api/mobile/decision',headers=phone,json={'expected_revision':1,'decision':'approve','boss_password':'review-boss-123'})
    assert blocked.status_code==409 and blocked.json()['detail']['code']=='review_stale'
    assert c.get('/api/quotes/'+q['id'],headers=staff).json()['approval'] is None
