"""Bound the shared splitter without truncating supported quotations or evidence."""
import time

import pytest

from backend import requirements as req
from backend.catalog import CatalogError


def inquiry(count, separator='\n', product='CEM-A-FAST-50 1 bag'):
    return separator.join([product]*count)+'\nDeliver to Shah Alam.'


@pytest.mark.parametrize('separator',['\n',';',' and ',' dan ','，','和'])
def test_forty_products_keep_all_quantities_and_original_spans(business_data,separator):
    text=inquiry(40,separator)
    data=req.understand(text,business_data['products'],business_data)
    assert data['status']=='READY',data
    assert len(data['items'])==40
    assert [i['quantity'] for i in data['items']]==['1']*40
    spans=[i['source_segments'][0]['span'] for i in data['items']]
    assert spans==sorted(spans)
    assert len({i['source_id'] for i in data['items']})==40
    for item,span in zip(data['items'],spans):
        assert text[span[0]:span[1]]==item['source_segments'][0]['source_text']


@pytest.mark.parametrize('separator',['\n',';',' and ',' dan ','，','和'])
def test_forty_one_products_are_rejected_entirely(business_data,separator):
    with pytest.raises(CatalogError,match='submit smaller batches'):
        req.understand(inquiry(41,separator),business_data['products'],business_data)


def test_delivery_and_greetings_do_not_use_product_slots(business_data):
    text='Hello\n'+('\nDeliver to Shah Alam.\n'.join(['CEM-A-FAST-50 1 bag']*40))+'\nHow much?'
    data=req.understand(text,business_data['products'],business_data)
    assert len(data['items'])==40 and data['status']=='READY'
    # Forty unresolved quantities remain forty questions, rather than a limit error.
    missing=req.understand(inquiry(40,product='CEM-A-FAST-50'),business_data['products'],business_data)
    assert len(missing['items'])==40 and missing['status']=='NEEDS_INFO'
    assert all(i['quantity']=='' for i in missing['items'])


def test_unknown_goods_also_count_towards_the_limit(business_data):
    with pytest.raises(CatalogError,match='submit smaller batches'):
        req.understand(inquiry(40)+'\nsand 1 bag',business_data['products'],business_data)


@pytest.mark.parametrize('constant,value,text',[
    ('MAX_PENDING_SEGMENTS',2,'Hello\nHello\nHello'),
    ('MAX_RAW_SEGMENTS',2,'Hello\nHello\nHello'),
    ('MAX_SPLIT_STEPS',1,inquiry(2,' and ')),
    ('MAX_SPLIT_CHARACTERS',20,inquiry(1)),
])
def test_each_work_budget_is_enforced_by_the_shared_splitter(business_data,monkeypatch,constant,value,text):
    monkeypatch.setattr(req,constant,value)
    with pytest.raises(CatalogError,match='submit smaller batches'):
        req.split_segments(text,business_data['products'],business_data)


@pytest.mark.parametrize('count',[41,1000])
@pytest.mark.parametrize('endpoint',['parse','review'])
def test_oversized_api_requests_are_fast_controlled_and_do_not_create_records(reviewed_app,count,endpoint):
    c,_,staff,app=reviewed_app
    text=('cement and '*999+'cement 1 bag. Deliver to Shah Alam.') if count==1000 else inquiry(41)
    assert len(text)<=12000
    with app.state.store.transaction() as db:
        before=[db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ['quotes','requirement_reviews']]
    path='/api/inquiries/parse' if endpoint=='parse' else '/api/requirements/review'
    body={'text':text,'mode':'requirements'} if endpoint=='parse' else {'inquiry':text,'items':[{'sku':'CEM-A-FAST-50','quantity':'1'}],'area':'Shah Alam','fulfilment':'delivery'}
    # Warm this test machine, then measure the same request, including HTTP handling.
    c.get('/api/health')
    started=time.perf_counter();response=c.post(path,headers=staff,json=body);seconds=time.perf_counter()-started
    assert response.status_code==422,response.text
    assert response.json()=={'detail':req.INQUIRY_TOO_LARGE}
    assert seconds<2.0,{'seconds':seconds,'endpoint':endpoint,'count':count}
    assert c.get('/api/health').status_code==200
    with app.state.store.transaction() as db:
        after=[db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ['quotes','requirement_reviews']]
    assert after==before


@pytest.mark.parametrize('endpoint',['parse','review'])
@pytest.mark.parametrize('length',[12000,12001])
def test_character_boundary_stays_controlled(reviewed_app,endpoint,length):
    c,_,staff,_=reviewed_app
    raw='cement and '*999+'cement 1 bag. Deliver to Shah Alam.'
    text=raw+' '*(length-len(raw))
    body={'text':text,'mode':'requirements'} if endpoint=='parse' else {'inquiry':text,'items':[{'sku':'CEM-A-FAST-50','quantity':'1'}],'area':'Shah Alam','fulfilment':'delivery'}
    started=time.perf_counter()
    response=c.post('/api/inquiries/parse' if endpoint=='parse' else '/api/requirements/review',headers=staff,json=body)
    assert response.status_code==422
    if length==12000:assert response.json()=={'detail':req.INQUIRY_TOO_LARGE}
    else:assert response.json()['detail'][0]['type']=='string_too_long'
    assert time.perf_counter()-started<2.0
    assert c.get('/api/health').status_code==200


def test_forty_products_can_review_and_save_without_truncation(reviewed_app):
    c,_,staff,_=reviewed_app;text=inquiry(40)
    parsed=c.post('/api/inquiries/parse',headers=staff,json={'text':text,'mode':'requirements'})
    assert parsed.status_code==200 and parsed.json()['can_quote']
    items=[{key:i[key] for key in ('sku','quantity','source_id')} for i in parsed.json()['items']]
    checked=c.post('/api/requirements/review',headers=staff,json={'inquiry':text,'items':items,'area':'Shah Alam','fulfilment':'delivery'})
    assert checked.status_code==200 and checked.json()['can_quote'],checked.text
    saved=c.post('/api/quotes',headers=staff,json={'customer':'40 synthetic products','inquiry':text,'language':'en','source_confirmed':True,
        'request_key':'forty-products-v154','items':[{k:i[k] for k in ('sku','quantity')} for i in items],
        'pricing_enabled':True,'delivery_area':'Shah Alam','review_id':checked.json()['review_id']})
    assert saved.status_code==200 and len(saved.json()['items'])==40,saved.text
