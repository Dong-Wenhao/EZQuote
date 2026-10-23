"""Server-owned requirement reviews. Semantic corrections are concrete, scoped and audited."""
import copy
import hashlib
import json
import secrets
from decimal import Decimal
from fastapi import HTTPException
from .business import get_business
from .catalog import price_items, compact
from .pricing import ensure_stock
from .requirements import understand, resolve_area, product_tags, PREFERENCES, APPLICATIONS, issue, QUESTIONS
from .requirement_tokens import VERSION
from .store import dumps, now


def canonical_quantity(value):
    return format(Decimal(str(value)).normalize(),'f')


def facts(inquiry,items,area,fulfilment):
    return {'inquiry':inquiry.strip(),'items':[{'sku':i['sku'],'quantity':canonical_quantity(i['quantity'])} for i in items],
            'area':area.strip() if fulfilment=='delivery' else '', 'fulfilment':fulfilment}


def fingerprint(fact,corrections,sources,catalog,business,quote_id,base_revision):
    return hashlib.sha256(json.dumps({'facts':fact,'corrections':corrections,'sources':sources,'catalog':catalog,'business':business,
          'parser':VERSION,'quote_id':quote_id or '', 'base_revision':base_revision or 0},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def stale():
    raise HTTPException(409,{'code':'review_stale','can_quote':False})


def evaluate(store,db,user,inquiry,items,area,fulfilment,corrections=None,quote_id=None,base_revision=0):
    catalog=store.catalog(db);business=get_business(store,db)
    if not business['configured']:raise HTTPException(422,{'code':'business_required'})
    if catalog['id']!=business['catalog_id']:stale()
    # Validate untrusted quantities before Decimal normalization or comparisons.
    priced,total=price_items([{'sku':i['sku'],'quantity':i['quantity']} for i in items],catalog['products'])
    parsed=understand(inquiry.strip(),catalog['products'],business)
    by_sku={p['sku']:p for p in catalog['products']}
    corrections=sorted(corrections or [],key=lambda c:c['issue_id']);provided={c['issue_id']:c for c in corrections}
    if len(provided)!=len(corrections):raise HTTPException(422,{'code':'invalid_correction'})
    used=set();resolved=[];pending=[]
    def decide(problem,expected=None,choices=None):
        if choices is not None:problem['choices']=choices
        else:problem['expected_value']=expected
        c=provided.get(problem['id'])
        if c and len(c.get('reason','').strip())>=3 and ((choices is not None and c.get('value') in choices) or (choices is None and c.get('value')==expected)):
            used.add(problem['id']);resolved.append({**problem,'resolution':{'value':c['value'],'reason':c['reason'].strip(),'actor':user['username']}});return c['value']
        pending.append(problem);return None
    def automatic(problem,value):
        resolved.append({**problem,'resolution':{'value':value,'reason':'Concrete selection verified by server','actor':user['username']}})
    # One line maps to one original product segment. Missing/extra lines cannot disappear silently.
    source_ids={p['source_id'] for p in parsed['items']};bound={};extras=[]
    for index,item in enumerate(items):
        sid=item.get('source_id')
        if not sid and len(items)==len(parsed['items']):sid=parsed['items'][index]['source_id']
        if sid and sid not in source_ids:raise HTTPException(422,{'code':'invalid_source_segment'})
        if sid in bound:raise HTTPException(422,{'code':'duplicate_source_segment'})
        if sid:bound[sid]=(index,item)
        else:extras.append((index,item))
    effective=copy.deepcopy(parsed['requirement']);effective['area']=area.strip() if fulfilment=='delivery' else '';effective['fulfilment']=fulfilment
    def apply_constraints(cs,problems,sid):
        for p in problems:
            field=p['field']
            if p['code'] not in {'negation_ambiguous','conflicting_constraints'}:continue
            if field not in cs:continue
            target=p.get('target')
            choice=decide(p,choices=['include','exclude','ignore'] if target else ['pickup','delivery'])
            if choice is None:continue
            if target:
                for values in cs[field].values():
                    if target in values:values.remove(target)
                if choice!='ignore':cs[field][choice].append(target)
            else:cs[field]={'include':[choice],'exclude':['delivery' if choice=='pickup' else 'pickup'],'uncertain':[]}
    root_problems=[p for p in parsed['issue_details'] if not p['source_id']]
    apply_constraints(effective['constraints'],root_problems,'')
    # All remaining root issues have explicit recovery paths.
    for p in root_problems:
        if p['code'] in {'negation_ambiguous','conflicting_constraints'}:continue
        if p['code'] in {'area','unknown_area','stock'}:continue
        pending.append(p)
    for original,req in zip(parsed['items'],effective['items']):
        sid=original['source_id'];entry=bound.get(sid)
        if not entry:
            p=issue('missing_product','items',original['source_text'],source_id=sid)
            decide(p,expected={'action':'remove','source_id':sid});continue
        index,item=entry
        if item['sku'] not in by_sku:raise HTTPException(422,{'code':'unknown_sku'})
        product=by_sku[item['sku']];q=canonical_quantity(item['quantity']);req['selected_sku']=product['sku'];req['selected_quantity']=q
        cs=req['constraints'];apply_constraints(cs,original['issue_details'],sid)
        for p in original['issue_details']:
            if p['code'] in {'negation_ambiguous','conflicting_constraints','stock','preference'}:continue
            if p['code']=='spec':
                if not req['specification'] or compact(product['spec']) in {compact(s) for s in req['specification']}:automatic(p,product['sku'])
                else:decide(p,expected=product['spec'])
            elif p['code'] in {'quantity','quantity_format','invalid_quantity'}:decide(p,expected=q)
            elif p['code']=='unknown_product':decide(p,expected=product['sku'])
            else:pending.append(p)
        if req['quantity'] is not None and not any(p['code'] in {'quantity_format','invalid_quantity','multiple_quantities'} for p in original['issue_details']) and Decimal(req['quantity'])!=Decimal(q):
            decide(issue('quantity_changed','quantity',original['source_text'],source_id=sid),expected=q)
        if req['unit'] and product['unit']!=req['unit']:
            decide(issue('unit_changed','unit',original['source_text'],source_id=sid),expected=product['unit'])
        if (req['category'] and product.get('category')!=req['category']) or (req['requested_skus'] and product['sku'] not in req['requested_skus']):
            decide(issue('product_changed','sku',original['source_text'],source_id=sid),expected=product['sku'])
        if req['specification'] and compact(product['spec']) not in {compact(s) for s in req['specification']}:
            decide(issue('spec_changed','specification',original['source_text'],source_id=sid),expected=product['spec'])
        for field,values in cs.items():
            if field=='fulfilment':continue
            actual={product['brand']} if field=='brands' else product_tags(product,field,PREFERENCES if field=='preferences' else APPLICATIONS)
            for target in set(values['include'])|set(values['exclude']):
                violates=(target in values['include'] and target not in actual) or (target in values['exclude'] and target in actual)
                # Multiple included brands represent a selection among named brands, not all brands at once.
                if field=='brands' and target in values['include'] and actual&set(values['include']):violates=False
                if violates:
                    p=issue({'brands':'brand_changed','preferences':'preference_changed','applications':'application_changed'}[field],field,original['source_text'],source_id=sid,target=target)
                    compatible=['include','ignore'] if target in actual else ['exclude','ignore']
                    choice=decide(p,choices=compatible)
                    if choice:
                        for key in ('include','exclude','uncertain'):
                            if target in values[key]:values[key].remove(target)
                        if choice!='ignore':values[choice].append(target)
    for index,item in extras:
        p=issue('extra_product','items',inquiry,source_id='extra-'+str(index))
        p['item_index']=index
        decide(p,expected={'sku':item['sku'],'quantity':canonical_quantity(item['quantity'])})
    fc=effective['constraints']['fulfilment'];requires=set(fc['include']);excludes=set(fc['exclude'])
    # A manual mode override must be acknowledged even when delivery was merely the safe default.
    has_root_resolution=any(r['field']=='fulfilment' for r in resolved)
    violates_mode=fulfilment in excludes or requires and fulfilment not in requires
    if has_root_resolution and violates_mode:
        pending.append(issue('conflicting_constraints','fulfilment',inquiry,target='final_mode'))
    elif not has_root_resolution and (fulfilment!=parsed['requirement']['fulfilment'] or violates_mode):
        if decide(issue('fulfilment_changed','fulfilment',inquiry),expected=fulfilment):
            effective['constraints']['fulfilment']={'include':[fulfilment],'exclude':[],'uncertain':[]}
    rule=resolve_area(area,business) if fulfilment=='delivery' else None
    if fulfilment=='delivery':
        if not rule:pending.append(issue('area' if not area else 'unknown_area','area',area or inquiry))
        else:
            effective['area']=rule['area']
            original_area=parsed['requirement']['area']
            if original_area and compact(original_area)!=compact(rule['area']):decide(issue('area_changed','area',original_area),expected=rule['area'])
            else:
                for p in root_problems:
                    if p['code'] in {'area','unknown_area'}:automatic(p,rule['area'])
    elif area.strip():raise HTTPException(422,{'code':'pickup_area_must_be_empty'})
    if set(provided)-used:
        # A forged resolved=true, stale choice or unrelated correction is never accepted.
        raise HTTPException(422,{'code':'invalid_correction','issue_ids':sorted(set(provided)-used)})
    ensure_stock(priced,business)
    pending=list({p['id']:p for p in pending}.values())
    for p in pending:
        p['item_index']=bound[p['source_id']][0] if p['source_id'] in bound else p.get('item_index')
        p['message']=QUESTIONS[parsed['language']].get(p['code'],p['code'])
    fact=facts(inquiry,items,effective['area'],fulfilment)
    sources=[i.get('source_id') or (parsed['items'][n]['source_id'] if len(items)==len(parsed['items']) else '') for n,i in enumerate(items)]
    return {'can_quote':not pending,'parser_version':VERSION,'issue_details':pending,'resolutions':resolved,'original':parsed['requirement'],'effective':effective,
            'facts':fact,'sources':sources,'corrections':corrections,'catalog_id':catalog['id'],'business_version':business['id'],
            'quote_id':quote_id or '', 'base_revision':base_revision or 0,'selected_items':priced}


def review(store,db,user,body):
    snapshot=evaluate(store,db,user,body.inquiry,[i.model_dump() for i in body.items],body.area,body.fulfilment,[c.model_dump() for c in body.corrections],body.quote_id,body.expected_revision)
    if not snapshot['can_quote']:return {k:v for k,v in snapshot.items() if k!='selected_items'}
    digest=fingerprint(snapshot['facts'],snapshot['corrections'],snapshot['sources'],snapshot['catalog_id'],snapshot['business_version'],snapshot['quote_id'],snapshot['base_revision'])
    existing=db.execute('SELECT review_id FROM requirement_reviews r WHERE actor=? AND content_hash=? AND NOT EXISTS(SELECT 1 FROM quote_reviews q WHERE q.review_id=r.review_id)',(user['username'],digest)).fetchone()
    review_id=existing[0] if existing else secrets.token_urlsafe(24)
    snapshot.pop('selected_items')
    if not existing:db.execute('INSERT INTO requirement_reviews VALUES(?,?,?,?,?,?,?,?,?,?)',(review_id,user['username'],digest,VERSION,snapshot['catalog_id'],snapshot['business_version'],snapshot['quote_id'],snapshot['base_revision'],dumps(snapshot),now()))
    return {**snapshot,'review_id':review_id,'content_hash':digest}


def validate(store,db,review_id,user,inquiry,items,area,fulfilment,quote_id='',base_revision=0,bound_revision=None):
    if not review_id:stale()
    row=db.execute('SELECT * FROM requirement_reviews WHERE review_id=?',(review_id,)).fetchone()
    if not row:stale()
    row=dict(row);snapshot=json.loads(row['snapshot']);business=get_business(store,db)
    if row['parser_version']!=VERSION or row['catalog_id']!=store.catalog(db)['id'] or row['business_version']!=business['id']:stale()
    if bound_revision is None:
        if row['actor']!=user['username'] or row['quote_id']!=(quote_id or '') or row['base_revision']!=(base_revision or 0):stale()
        if db.execute('SELECT 1 FROM quote_reviews WHERE review_id=?',(review_id,)).fetchone():stale()
    elif not db.execute('SELECT 1 FROM quote_reviews WHERE review_id=? AND quote_id=? AND revision=?',(review_id,quote_id,bound_revision)).fetchone():stale()
    if fulfilment=='delivery':
        rule=resolve_area(area,business)
        if not rule:stale()
        area=rule['area']
    fact=facts(inquiry,items,area,fulfilment)
    digest=fingerprint(fact,snapshot['corrections'],snapshot['sources'],row['catalog_id'],row['business_version'],row['quote_id'],row['base_revision'])
    if digest!=row['content_hash']:stale()
    ensure_stock(items,business)
    return {'review_id':review_id,'actor':row['actor'],'created_at':row['created_at'],**snapshot}


def saved_review(db,quote_id,revision):
    row=db.execute('SELECT r.* FROM quote_reviews q JOIN requirement_reviews r ON r.review_id=q.review_id WHERE q.quote_id=? AND q.revision=?',(quote_id,revision)).fetchone()
    return {**json.loads(row['snapshot']),**{key:row[key] for key in ('review_id','actor','created_at','parser_version','catalog_id','business_version')}} if row else None


def bind(db,quote_id,revision,checked,user):
    db.execute('INSERT INTO quote_reviews VALUES(?,?,?)',(quote_id,revision,checked['review_id']))
    from .store import Store
    Store.event(db,{'id':quote_id,'revision':revision},user['username'],'REQUIREMENTS_REVIEWED',{'review_id':checked['review_id'],'parser_version':VERSION,'resolutions':checked['resolutions']})
