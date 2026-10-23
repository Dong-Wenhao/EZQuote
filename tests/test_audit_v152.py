"""Adversarial audit of complete numbers, source coverage, and persisted reviews."""
import pytest
from backend.number_words import evidence_number
from backend.requirement_tokens import quantities
from backend.requirements import understand
from backend.catalog import UNITS

BAD_WORDS=['twenty and thirty','two two','dua puluh tiga puluh','one million twenty',
           'one million 20','二十二十','二十三十','一百二']
VALID_WORDS=[('twenty-one','21'),('two hundred twenty','220'),('two hundred and twenty','220'),
 ('one thousand and twenty','1020'),('one thousand two hundred and twenty','1220'),
 ('dua puluh tiga','23'),('dua ratus dua puluh','220'),('dua ratus dan dua puluh','220'),
 ('seratus dua belas','112'),('seribu dua ratus tiga puluh empat','1234'),
 ('二十','20'),('一十','10'),('两百零二','202'),('一千零一','1001'),('一万零一十','10010'),('一百万','1000000')]


@pytest.mark.parametrize('raw',BAD_WORDS)
def test_malformed_word_numbers_are_not_added_or_truncated(business_data,raw):
    assert evidence_number(raw) is None
    text='Need '+raw+' bags cement 50kg. Deliver to Shah Alam.'
    q=quantities(text,UNITS)
    assert len(q)==1 and q[0]['raw']==raw and q[0]['value'] is None and q[0]['error']=='quantity_format'
    parsed=understand(text,business_data['products'],business_data)
    assert not parsed['can_quote'] and parsed['items'][0]['quantity']==''


@pytest.mark.parametrize('raw,value',VALID_WORDS)
def test_supported_word_grammar_preserves_valid_three_language_quantities(raw,value):
    assert str(evidence_number(raw))==value
    q=quantities('Need '+raw+' bags cement',UNITS)
    assert len(q)==1 and q[0]['value']==value and q[0]['error'] is None


@pytest.mark.parametrize('separator',['_', '__', '..', ',,', '／', ' ⁄ ', '\u200b', '\u2060', ' e ', ' crore ', '万', '又要', ' or ', '，', '\u2028'])
def test_unexplained_number_join_never_produces_a_quote_for_the_numeric_suffix(business_data,separator):
    text='Need 1'+separator+'020 bags cement 50kg. Deliver to Shah Alam.'
    d=understand(text,business_data['products'],business_data)
    assert not d['can_quote'],d


@pytest.mark.parametrize('separator',['&','＆','+','plus','with','serta','bersama','及','与','並且','并且','. Need','\r','\u2028','\u2029'])
def test_unknown_fragments_cannot_get_a_review_through_alternative_connectors(reviewed_app,separator):
    c,_,staff,_=reviewed_app;text='Need 20 bags cement 50kg '+separator+' sand. Deliver to Shah Alam.'
    parsed=c.post('/api/inquiries/parse',headers=staff,json={'text':text,'mode':'requirements'}).json()
    assert not parsed['can_quote'] and any('sand' in i['source_text'] for i in parsed['items'])
    body={'inquiry':text,'items':[{'sku':'CEM-A-50','quantity':'20','source_id':parsed['items'][0]['source_id']}],'area':'Shah Alam','fulfilment':'delivery'}
    r=c.post('/api/requirements/review',headers=staff,json=body)
    assert r.status_code==200 and not r.json()['can_quote'] and not r.json().get('review_id')
    assert any(p['code'] in {'uncovered_text','missing_product'} for p in r.json()['issue_details'])
    assert c.get('/api/quotes',headers=staff).json()==[]


def test_unexplained_text_is_hard_even_when_a_sku_and_quantity_are_given(reviewed_app):
    c,_,staff,_=reviewed_app;text='CEM-A-50 20 bags & sand. Deliver to Shah Alam.'
    body={'inquiry':text,'items':[{'sku':'CEM-A-50','quantity':'20'}],'area':'Shah Alam','fulfilment':'delivery'}
    first=c.post('/api/requirements/review',headers=staff,json=body).json()
    p=next(p for p in first['issue_details'] if p['code']=='uncovered_text')
    assert 'sand' in p['uncovered_text']
    forged=c.post('/api/requirements/review',headers=staff,json={**body,'corrections':[{'issue_id':p['id'],'value':'CEM-A-50','reason':'Everything looks okay'}]})
    assert forged.status_code==422 and forged.json()['detail']['code']=='invalid_correction'
    fixed=c.post('/api/requirements/review',headers=staff,json={**body,'inquiry':'CEM-A-50 20 bags. Deliver to Shah Alam.'}).json()
    assert fixed['can_quote'] and fixed['review_id']


@pytest.mark.parametrize('negation',["I don’t want fast setting","I don‘t want fast setting","I doesn’t want fast setting",'fast setting is unwanted','速凝免了'])
def test_typographic_or_unclassified_negative_conditions_never_recommend_the_opposite(business_data,negation):
    d=understand('Need 20 bags cement for plastering. '+negation+'. Deliver to Shah Alam.',business_data['products'],business_data)
    assert not d['can_quote'] or all(i['sku']!='CEM-A-FAST-50' for i in d['items']),d


def test_curly_apostrophe_exclusion_is_also_enforced_by_backend_review(reviewed_app):
    c,_,staff,_=reviewed_app;text='Need 20 bags cement for plastering. I don’t want fast setting. Deliver to Shah Alam.'
    r=c.post('/api/requirements/review',headers=staff,json={'inquiry':text,'items':[{'sku':'CEM-A-FAST-50','quantity':'20'}],'area':'Shah Alam','fulfilment':'delivery'})
    assert r.status_code==200 and not r.json()['can_quote']
    assert any(p['code']=='preference_changed' for p in r.json()['issue_details'])
