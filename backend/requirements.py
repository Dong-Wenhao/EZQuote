"""Evidence-based multilingual requirement matching, independent of paid model APIs."""
import re
from decimal import Decimal

from .ai import evidence_number
from .catalog import CatalogError, UNITS, compact, contains, detect_language, norm

# Text fragments also contain greetings, delivery and product modifiers. Give
# those their own budget instead of consuming the 40 supported product slots.
MAX_REQUIREMENT_ITEMS = 40
MAX_RAW_SEGMENTS = 160
MAX_PENDING_SEGMENTS = 160
MAX_SPLIT_STEPS = 320
MAX_SPLIT_CHARACTERS = 512_000
INQUIRY_TOO_LARGE = "Inquiry is too large. Use at most 40 products and submit smaller batches."

CATEGORIES = {"cement": ["cement", "simen", "水泥"], "pvc_pipe": ["pvc pipe", "pvc", "paip", "水管"],
              "paint": ["paint", "cat", "油漆", "涂料"], "nails": ["nails", "nail", "paku", "钉子", "铁钉"]}
APPLICATIONS = {"plastering": ["plastering", "plaster", "melepa", "lepaan", "抹灰", "粉刷"],
                "masonry": ["masonry", "bricklaying", "bata", "砌墙", "砌筑"],
                "concrete": ["concrete", "konkrit", "混凝土"],
                "indoor": ["indoor", "dalaman", "室内"], "outdoor": ["outdoor", "luaran", "室外"]}
PREFERENCES = {"fast_setting": ["fast setting", "fast-setting", "quick setting", "quick dry", "cepat kering", "cepat mengeras", "速凝", "快干", "快速凝固"],
               "waterproof": ["waterproof", "kalis air", "防水"],
               "low_odour": ["low odour", "low odor", "kurang bau", "低气味", "低味"]}
TAG_LABELS = {
    "zh": {"plastering": "抹灰", "masonry": "砌筑", "concrete": "混凝土", "indoor": "室内", "outdoor": "室外", "fast_setting": "速凝", "waterproof": "防水", "low_odour": "低气味"},
    "en": {"plastering": "plastering", "masonry": "masonry", "concrete": "concrete", "indoor": "indoor", "outdoor": "outdoor", "fast_setting": "fast setting", "waterproof": "waterproof", "low_odour": "low odour"},
    "ms": {"plastering": "melepa", "masonry": "kerja bata", "concrete": "konkrit", "indoor": "dalaman", "outdoor": "luaran", "fast_setting": "cepat kering", "waterproof": "kalis air", "low_odour": "kurang bau"}}
WORDS = ("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen "
         "twenty thirty forty fifty sixty seventy eighty ninety hundred thousand and minus negative "
         "satu dua tiga empat lima enam tujuh lapan sembilan sepuluh sebelas belas puluh ratus ribu seratus seribu negatif").split()
NUMBER_WORD = "(?:" + "|".join(sorted(WORDS, key=len, reverse=True)) + ")"
QUANTITY = r"(?:-?\d+(?:\.\d+)?|负?[零〇一二两三四五六七八九十百千万]+|" + NUMBER_WORD + r"(?:[\s-]+" + NUMBER_WORD + r")*)"
QUESTIONS = {
    "zh": {"quantity": "请补充每种商品的数量和单位。", "invalid_quantity": "请填写有效的正数数量，计件商品需要整数。", "multiple_quantities": "检测到多个数量，请把每种商品分行填写。", "unknown_product": "目录里没有明确匹配的商品，请补充商品类型或选择具体商品。", "spec": "存在不同规格，请确认需要哪一种规格。", "stock": "匹配商品库存不足，请调整数量或选择有库存的备选。", "preference": "有库存商品未完全满足用途或偏好，请确认是否接受备选。", "area": "请补充配送地区，或选择自提。", "unknown_area": "该地区没有配送规则，请选择已有地区或请老板补充配送规则。"},
    "en": {"quantity": "Please specify the quantity and unit for each product.", "invalid_quantity": "Use a positive quantity; counted units need whole numbers.", "multiple_quantities": "Put each product and its quantity on a separate line.", "unknown_product": "No clear catalog match. Specify the product type or select a product.", "spec": "Several specifications exist. Confirm which specification you need.", "stock": "Insufficient stock. Change the quantity or select an available alternative.", "preference": "Available products do not fully match the use or preference. Confirm an alternative.", "area": "Specify the delivery area, or choose collection.", "unknown_area": "No delivery rule for this area. Choose a configured area or ask the owner to add a rule."},
    "ms": {"quantity": "Nyatakan kuantiti dan unit setiap produk.", "invalid_quantity": "Gunakan kuantiti positif; unit bilangan mestilah nombor bulat.", "multiple_quantities": "Tulis setiap produk dan kuantitinya pada baris berasingan.", "unknown_product": "Tiada padanan jelas. Nyatakan jenis produk atau pilih produk.", "spec": "Terdapat beberapa spesifikasi. Sahkan spesifikasi yang diperlukan.", "stock": "Stok tidak mencukupi. Ubah kuantiti atau pilih alternatif yang tersedia.", "preference": "Produk tersedia tidak memenuhi semua kegunaan atau pilihan. Sahkan alternatif.", "area": "Nyatakan kawasan penghantaran atau pilih ambil sendiri.", "unknown_area": "Tiada peraturan penghantaran untuk kawasan ini. Pilih kawasan tersedia atau minta bos menambah peraturan."}}


import hashlib
from .requirement_tokens import VERSION, hits, quantities, polarity

QUESTIONS['zh'].update({'quantity_format': '数量格式不明确，请核对完整数字后填写数量，不能使用数字尾部。', 'multiple_products': '检测到多种商品，请把每种商品及数量分行填写。', 'ambiguous_modifier': '补充条件可能对应多种商品，请把用途或偏好写在对应商品行。', 'negation_ambiguous': '否定条件不明确，请明确选择需要或排除的条件，或修改原文。', 'conflicting_constraints': '需求条件有冲突，请明确最终条件后重新核对。'})
QUESTIONS['en'].update({'quantity_format': 'Check the complete number and enter the confirmed quantity; do not use a numeric suffix.', 'multiple_products': 'Multiple products detected. Put each product and its quantity on a separate line.', 'ambiguous_modifier': 'Put this use or preference on the line of the product it describes.', 'negation_ambiguous': 'Clarify whether this condition is required or excluded, or edit the inquiry.', 'conflicting_constraints': 'Conflicting requirements. Specify the final choice and review again.'})
QUESTIONS['ms'].update({'quantity_format': 'Semak nombor penuh dan masukkan kuantiti yang disahkan, bukan hujung nombor.', 'multiple_products': 'Beberapa produk dikesan. Tulis setiap produk dan kuantiti pada baris berasingan.', 'ambiguous_modifier': 'Tulis kegunaan atau pilihan pada baris produk yang berkaitan.', 'negation_ambiguous': 'Jelaskan sama ada syarat diperlukan atau dikecualikan, atau sunting pertanyaan.', 'conflicting_constraints': 'Keperluan bercanggah. Nyatakan pilihan akhir dan semak semula.'})
QUESTIONS['zh']['uncovered_text']='原文还有未理解的商品或条件，请把每种商品及条件分行写清，再重新整理。'
QUESTIONS['en']['uncovered_text']='Some product or condition text is not understood. Put each product and its conditions on a separate line, then prepare again.'
QUESTIONS['ms']['uncovered_text']='Terdapat teks produk atau syarat yang belum difahami. Tulis setiap produk dan syarat pada baris berasingan, kemudian susun semula.'

def tags(text, vocabulary):
    return [key for key, aliases in vocabulary.items() if hits(text, aliases)]


def product_tags(product, field, vocabulary):
    value=product.get(field,'')
    return {key for key,aliases in vocabulary.items() if key in value.split('|') or contains(value,key.replace('_',' ')) or any(contains(value,a) for a in aliases)}


def resolve_area(value,business):
    for rule in business['delivery']:
        if any(compact(value)==compact(a) for a in [rule['area'],*rule['aliases'].split('|')] if a):return rule
    return None


def issue(code,field,source_text='',span=None,source_id='',target=None):
    key='|'.join([VERSION,code,field,source_id,str(target or ''),str(span or []),source_text])
    return {'id':'i-'+hashlib.sha256(key.encode()).hexdigest()[:16],'code':code,'field':field,'source_text':source_text,'span':span,
            'text_basis':'original','source_id':source_id,'target':target,'severity':'blocking','resolution':None}


def constraint_mentions(text,products,offset=0):
    vocabs={'preferences':PREFERENCES,'applications':APPLICATIONS,
            'fulfilment':{'pickup':['self collect','self collection','pickup','pick up','ambil sendiri','自提','自己来拿'],
                          'delivery':['deliver','delivery','hantar','penghantaran','配送','送到','送往','送货']},'brands':{}}
    for p in products:
        brand=p['brand'];short=re.sub(r'^brand\s*','',brand,flags=re.I).strip()
        vocabs['brands'][brand]=[brand,'Brand '+short,'jenama '+short,short+'牌']
    result=[]
    for field,vocab in vocabs.items():
        for target,aliases in vocab.items():
            for start,end,raw in hits(text,aliases):
                result.append({'field':field,'target':target,'polarity':polarity(text,start,end),'source_text':raw,'span':[offset+start,offset+end]})
    # Explicit short brand corrections such as 不要 A，改 B / not A but B.
    for brand in vocabs['brands']:
        short=re.sub(r'^brand\s*','',brand,flags=re.I).strip()
        if len(short)>3:continue
        for start,end,raw in hits(text,[short]):
            if any(m['field']=='brands' and m['span'][0]<=offset+start<m['span'][1] for m in result):continue
            if re.search(r'(?:不要|不用|改|换|\bnot|\bno|\bbut|\bbukan|\btidak)\s*$',text[max(0,start-15):start],re.I):
                result.append({'field':'brands','target':brand,'polarity':polarity(text,start,end),'source_text':raw,'span':[offset+start,offset+end]})
    return result


def constraints(mentions):
    result={field:{'include':[],'exclude':[],'uncertain':[]} for field in ['brands','preferences','applications','fulfilment']}
    for m in mentions:
        key={'positive':'include','negative':'exclude','uncertain':'uncertain'}[m['polarity']]
        if m['target'] not in result[m['field']][key]:result[m['field']][key].append(m['target'])
    return result


def constraint_issues(text,mentions,source_id='',prefix=''):
    cs=constraints(mentions);out=[]
    for field,c in cs.items():
        for target in sorted(set(c['uncertain'])|set(c['include'])&set(c['exclude'])):
            evidence=next(m for m in mentions if m['field']==field and m['target']==target)
            out.append(issue('negation_ambiguous' if target in c['uncertain'] else 'conflicting_constraints',prefix+field,evidence['source_text'],evidence['span'],source_id,target))
    return cs,out


def product_mentions(text,products):
    found=[(a,b,'category',key) for key,aliases in CATEGORIES.items() for a,b,_ in hits(text,aliases)]
    found += [(a,b,'sku',p['sku']) for p in products for a,b,_ in hits(text,[p['sku']])]
    return sorted(found)


def unexplained_segment(value,products,business,include_products=False):
    """Leave every unclassified fragment visible, even without a catalog alias."""
    remaining=list(value)
    mentions=constraint_mentions(value,products)
    spans=[m['span'] for m in mentions]+[m['span'] for m in quantities(value,UNITS)]
    spans += [list(m.span()) for m in re.finditer(r'\d+(?:\.\d+)?\s*(?:kg|公斤|千克|mm|cm|ml|litre|liter|l|m)(?![a-z])',value,re.I)]
    if include_products:
        aliases=[alias for names in CATEGORIES.values() for alias in names]
        aliases += [alias for p in products for alias in [p['sku'],p['name_zh'],p['name_en'],p['name_ms'],*p['aliases'].split('|')]]
        spans += [[a,b] for a,b,_ in hits(value,aliases)]
    if any(m['field']=='fulfilment' for m in mentions):
        spans += [[a,b] for rule in business['delivery'] for a,b,_ in hits(value,[rule['area'],*rule['aliases'].split('|')])]
    for a,b in spans:remaining[a:b]=[' ']*(b-a)
    residue=''.join(remaining).replace('’',"'").replace('‘',"'")
    filler=(r'\b(?:please|kindly|quantity|qty|kuantiti|prefer|need|want|mahu|tolong|sila|do|does|not|no|don\x27t|'
            r'jangan|tidak|tak|bukan|we|will|I|saya|for|untuk|to|in|ke|and|dan|is|only|required|needed|wanted|'
            r'hi|hello|boss|hai|salam|how\s+much|berapa\s+harga|of|can|could|would|you|me|get|give|quote|price|quotation|'
            r'some|us|a|an|the|are|like|use|using|kami|nak|ingin|kepada|bagi)\b|'
            r'请|数量|需要|要|不要|不用|不需要|我们|我|的|用于|用来|偏好|到|往|以及|还有|和|您好|你好|多少钱')
    residue=re.sub(filler,' ',residue,flags=re.I)
    # Separators are harmless only after all meaningful words have been explained.
    import unicodedata
    return ''.join(c for c in residue if not c.isspace() and unicodedata.category(c)[0] not in 'PS')


def split_segments(text,products,business):
    # Cache original product spans: repeatedly matching the entire right-hand
    # tail of an inquiry was quadratic even before it exhausted recursion.
    if len(text)>12000:raise CatalogError(INQUIRY_TOO_LARGE)
    pending=[]
    for m in re.finditer(r'[^\r\n\v\f\x85\u2028\u2029;；]+',text):
        if m.group().strip():pending.append((m.start(),m.end()))
        if len(pending)>MAX_PENDING_SEGMENTS:raise CatalogError(INQUIRY_TOO_LARGE)
    pending.reverse()
    mentions=product_mentions(text,products)
    def has_goods(start,end):
        return any(start<=a and b<=end for a,b,*_ in mentions)
    raw=[];work=0;scanned=0;goods_count=0
    while pending:
        work+=1
        start,end=pending.pop();scanned+=end-start
        if work>MAX_SPLIT_STEPS or scanned>MAX_SPLIT_CHARACTERS:raise CatalogError(INQUIRY_TOO_LARGE)
        s=text[start:end]
        numeric_spans=[q['span'] for q in quantities(s,UNITS,allow_kg=True)]
        cut=None
        for m in re.finditer(r'\b(?:and|dan)\b|以及|还有|和|、|,(?![0-9])|，(?![0-9])',s,re.I):
            if any(a<=m.start()<b for a,b in numeric_spans):continue
            left=s[:m.start()];right=s[m.end():]
            left_goods=has_goods(start,start+m.start());right_goods=has_goods(start+m.end(),end)
            # A known product on one side does not explain an unknown product
            # on the other. Only classified modifiers/logistics/courtesy may join.
            if left_goods and right_goods or left_goods and unexplained_segment(right,products,business) or right_goods and unexplained_segment(left,products,business):
                cut=m;break
        if cut is not None:
            # LIFO, right first: preserve the original left-to-right leaf spans.
            pending.extend([(start+cut.end(),end),(start,start+cut.start())])
            if len(pending)>MAX_PENDING_SEGMENTS:raise CatalogError(INQUIRY_TOO_LARGE)
            continue
        while start<end and text[start].isspace():start+=1
        while end>start and text[end-1].isspace():end-=1
        if start<end:
            raw.append({'span':[start,end],'source_text':text[start:end]})
            goods_count+=bool(has_goods(start,end))
            if len(raw)>MAX_RAW_SEGMENTS or goods_count>MAX_REQUIREMENT_ITEMS:raise CatalogError(INQUIRY_TOO_LARGE)
    goods=[s for s in raw if product_mentions(s['source_text'],products)]
    groups=[{'source_id':f"s-{s['span'][0]}-{s['span'][1]}",'parts':[s]} for s in goods]
    extra=[]
    for s in raw:
        if s in goods:continue
        value=s['source_text']
        if re.fullmatch(r'(?:hi|hello|hi boss|你好|您好|hai|salam|how much|多少钱|berapa harga)[ !！,.?，。？]*',norm(value)):continue
        mentions=constraint_mentions(value,products)
        modifier=any(m['field']!='fulfilment' for m in mentions) or bool(re.search(r'\d+(?:\.\d+)?\s*(?:kg|公斤|千克|mm|cm|ml|litre|liter|l|m)(?![a-z])',norm(value)))
        qs=quantities(value,UNITS)
        # Classify the entire fragment, not just the prefix before "deliver".
        remainder=unexplained_segment(value,products,business)
        if not modifier and not qs and not remainder:continue
        quantity_only=bool(qs) and not remainder
        if len(groups)==1 and (modifier and not qs and not remainder or quantity_only):
            groups[0]['parts'].append(s)
        elif modifier and not qs and not remainder and groups:
            extra.append(issue('ambiguous_modifier','items',value,s['span']))
        else:
            groups.append({'source_id':f"s-{s['span'][0]}-{s['span'][1]}",'parts':[s]})
            if len(groups)>MAX_REQUIREMENT_ITEMS:raise CatalogError(INQUIRY_TOO_LARGE)
    return groups,extra


def understand(text,products,business,area='',fulfilment='auto'):
    language=detect_language(text);root_issues=[];root_details=[]
    all_mentions=constraint_mentions(text,products)
    global_constraints,global_issues=constraint_issues(text,[m for m in all_mentions if m['field']=='fulfilment'])
    root_details.extend(global_issues);fc=global_constraints['fulfilment']
    positives=set(fc['include'])-set(fc['exclude'])
    if len(fc['include'])>1 or (not positives and 'delivery' in fc['exclude']):
        root_details.append(issue('conflicting_constraints','fulfilment',text,[0,len(text)]))
    method=fulfilment if fulfilment!='auto' else ('pickup' if positives=={'pickup'} and not root_details else 'delivery')
    chosen_area=area.strip()
    if not chosen_area:
        matches=[r for r in business['delivery'] if any(hits(text,[a]) for a in [r['area'],*r['aliases'].split('|')] if a)]
        if len(matches)==1:chosen_area=matches[0]['area']
        elif len(matches)>1:root_details.append(issue('unknown_area','area',text,[0,len(text)]))
        else:
            m=re.search(r'(?:deliver(?:y)?\s+(?:to|in)|hantar\s+ke|送到|送往|配送到)\s*([^\n,.;!?，。！？]{1,100})',text,re.I)
            if m:chosen_area=m.group(1).strip()
    rule=resolve_area(chosen_area,business) if chosen_area else None
    if method=='delivery':
        if not chosen_area:root_details.append(issue('area','area',text,[0,len(text)]))
        elif not rule:root_details.append(issue('unknown_area','area',chosen_area))
        else:chosen_area=rule['area']
    else:chosen_area=''
    groups,extra=split_segments(text,products,business);root_details.extend(extra)
    output=[];structured=[]
    for group in groups:
        sid=group['source_id'];parts=group['parts'];line='\n'.join(p['source_text'] for p in parts)
        category_keys=tags(line,CATEGORIES)
        mentions=[m for p in parts for m in constraint_mentions(p['source_text'],products,p['span'][0]) if m['field']!='fulfilment']
        cs,details=constraint_issues(line,mentions,sid)
        applications=cs['applications']['include'];preferences=cs['preferences']['include']
        sku_matches=[p for p in products if hits(line,[p['sku']])]
        if len(category_keys)>1 or len(sku_matches)>1:details.append(issue('multiple_products','items',line,parts[0]['span'],sid))
        candidates=sku_matches or [p for p in products if p.get('category') in category_keys or any(contains(line,a) for a in [p['name_zh'],p['name_en'],p['name_ms'],*p['aliases'].split('|')] if a)]
        # Preserve a named unknown brand as a blocking condition, never silently ignore it.
        named=re.findall(r'(?:brand|jenama)\s+([a-z0-9]+)|([a-z0-9]+)\s*牌',norm(line))
        known={compact(re.sub(r'^brand\s*','',p['brand'],flags=re.I)) for p in products}
        if any(compact(a or b) not in known for a,b in named):candidates=[]
        if cs['brands']['include']:candidates=[p for p in candidates if p['brand'] in cs['brands']['include']]
        candidates=[p for p in candidates if p['brand'] not in cs['brands']['exclude'] and not(product_tags(p,'preferences',PREFERENCES)&set(cs['preferences']['exclude'])) and not(product_tags(p,'applications',APPLICATIONS)&set(cs['applications']['exclude']))]
        specs=re.findall(r'\d+(?:\.\d+)?\s*(?:kg|公斤|千克|mm|cm|ml|litre|liter|l|m)(?![a-z])',norm(line))
        if specs and not sku_matches:candidates=[p for p in candidates if compact(p['spec']) in {compact(s) for s in specs}]
        qs=[q for part in parts for q in quantities(part['source_text'],UNITS,part['span'][0],bool(candidates and all(p['unit']=='kg' for p in candidates)))]
        quantity,unit=(qs[0]['value'] or '',qs[0]['unit']) if len(qs)==1 else ('','')
        if len(qs)!=1:details.append(issue('quantity' if not qs else 'multiple_quantities','quantity',line,parts[0]['span'],sid))
        elif qs[0]['error']:details.append(issue(qs[0]['error'],'quantity',qs[0]['raw'],qs[0]['span'],sid))
        if unit:candidates=[p for p in candidates if p['unit']==unit]
        if (not specs and not sku_matches and not applications and not preferences and len({p['spec'] for p in candidates})>1) or len({compact(s) for s in specs})>1:
            details.append(issue('spec','sku',line,parts[0]['span'],sid))
        ranked=[]
        for product in candidates:
            inv=business['inventory'].get(product['sku']);in_stock=bool(inv and quantity and not(qs and qs[0]['error']) and Decimal(inv['stock'])>=Decimal(quantity)>0)
            am=[a for a in applications if a in product_tags(product,'applications',APPLICATIONS)];pm=[p for p in preferences if p in product_tags(product,'preferences',PREFERENCES)]
            reasons={lang:[label+': '+TAG_LABELS[lang].get(token,token) for token in am+pm] for lang,label in [('zh','符合需求'),('en','Matches'),('ms','Memenuhi')]}
            stock=inv['stock'] if inv else None
            for lang,label in [('zh','库存'),('en','Stock'),('ms','Stok')]:reasons[lang].append(label+' '+(stock or '?')+' '+product['unit'])
            ranked.append({**product,'stock':stock,'in_stock':in_stock,'match_score':35*len(am)+25*len(pm)+(15 if in_stock else 0),'match_reasons':reasons,'fully_matches':len(am)==len(applications) and len(pm)==len(preferences)})
        ranked.sort(key=lambda p:(not p['in_stock'],not p['fully_matches'],-p['match_score'],Decimal(p['unit_price']),p['sku']))
        best=ranked[0] if ranked else None
        if not best:details.append(issue('unknown_product','sku',line,parts[0]['span'],sid))
        elif quantity and not best['in_stock'] and not any(q['error'] for q in qs):details.append(issue('stock','quantity',line,parts[0]['span'],sid))
        elif not best['fully_matches']:details.append(issue('preference','preferences',line,parts[0]['span'],sid))
        if best:
            scope=[p for p in products if p.get('category')==best.get('category')]
            residue=unexplained_segment(line,scope,business,include_products=True)
            if residue:
                problem=issue('uncovered_text','items',line,parts[0]['span'],sid)
                problem['uncovered_text']=residue;details.append(problem)
        codes=list(dict.fromkeys(i['code'] for i in details))
        item={'source_id':sid,'source_segments':parts,'source_text':line,'sku':best['sku'] if best and not details else '', 'quantity':quantity,'unit':unit,'quantity_mentions':qs,'candidates':ranked,'best_match':best,'alternatives':ranked[1:4],'issues':codes,'issue_details':details,'questions':[QUESTIONS[language][code] for code in codes]}
        item['constraints']=cs
        output.append(item)
        structured.append({'source_id':sid,'source_text':line,'source_segments':parts,'category':category_keys[0] if len(category_keys)==1 else (best or {}).get('category'),'quantity':quantity or None,'unit':unit or None,'quantity_mentions':qs,'application':applications,'specification':specs,'preference':preferences,'brand':cs['brands']['include'][0] if len(cs['brands']['include'])==1 else None,'requested_skus':[p['sku'] for p in sku_matches],'constraints':cs,'constraint_mentions':mentions})
    # Aggregate inventory across repeated product lines as well as per line.
    combined={}
    for item in output:
        if item['sku']:combined[item['sku']]=combined.get(item['sku'],Decimal(0))+Decimal(item['quantity'])
    for sku,qty in combined.items():
        if qty>Decimal(business['inventory'][sku]['stock']):root_details.append(issue('stock','items',text,[0,len(text)],target=sku))
    root_issues=list(dict.fromkeys(i['code'] for i in root_details));all_details=root_details+[d for item in output for d in item['issue_details']]
    ready=bool(output) and not all_details
    return {'language':language,'status':'READY' if ready else 'NEEDS_INFO','can_quote':ready,'parser_version':VERSION,'items':output,
            'requirement':{'items':structured,'area':chosen_area,'fulfilment':method,'constraints':global_constraints,'constraint_mentions':[m for m in all_mentions if m['field']=='fulfilment'],'issues':root_issues},
            'issue_details':all_details,'clarification':'\n'.join(dict.fromkeys(QUESTIONS[language][d['code']] for d in all_details)), 'method':'requirements_rules','ai_state':'disabled'}
