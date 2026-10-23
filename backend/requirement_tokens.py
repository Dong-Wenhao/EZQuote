"""Complete numeric tokens and local polarity evidence, with offsets in original text."""
import re
import unicodedata
from decimal import Decimal
from .number_words import evidence_number

VERSION = 'requirements_rules_v5'
NUMBER_WORDS = ('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand and minus negative kosong satu dua tiga empat lima enam tujuh lapan sembilan sepuluh sebelas belas puluh ratus ribu seratus seribu negatif dan million billion trillion juta bilion trilion').split()
WORD = '(?:' + '|'.join(sorted(NUMBER_WORDS, key=len, reverse=True)) + ')'
WORD_NUMBER = WORD + '(?:[\\s-]+' + WORD + ')*'
NUMERIC = r'[+\-−]?(?:\d[\d,.，]*(?:[ \u00a0\u202f]+\d[\d,.，]*)*|\.\d+|NaN|Infinity|Inf)'
CHINESE_NUMBER = r'负?[零〇一二两三四五六七八九十百千万]+'
NUMBER = '(?:'+NUMERIC+'|'+CHINESE_NUMBER+'|'+WORD_NUMBER+')'
RANGE = NUMBER+r'\s*(?:\b(?:or|to|atau|hingga|sampai)\b|或者|或|到|至|[~～–—/])\s*'+NUMBER
# A numeric pair is ambiguous too; do not split the valid words "two hundred and twenty".
RANGE += '|'+NUMERIC+r'\s*(?:\b(?:and|dan)\b|和|与|及|[\-+×*])\s*'+NUMERIC
NEGATIVE = r"do\s+not|don['’‘]t|does\s+not|doesn['’‘]t|without|not|no|tidak|bukan|jangan|tak|不要|不用|不是|没有|无需|不|无"


def hits(text, aliases):
    found=[]
    for alias in aliases:
        if not alias: continue
        boundary_left=r'(?<![a-z0-9])' if alias[0].isascii() and alias[0].isalnum() else ''
        boundary_right=r'(?![a-z0-9])' if alias[-1].isascii() and alias[-1].isalnum() else ''
        for m in re.finditer(boundary_left+re.escape(alias)+boundary_right,text,re.I):
            found.append((m.start(),m.end(),m.group()))
    # Overlapping aliases describe the same mention; equal values at separate positions do not.
    result=[]
    for item in sorted(found,key=lambda x:(x[0],-(x[1]-x[0]))):
        if any(item[0]<p[1] and p[0]<item[1] for p in result):continue
        result.append(item)
    return result


CONNECTORS = {'and','or','to','dan','atau','hingga','sampai'}
CHINESE_CHARS = set('负零〇一二两三四五六七八九十百千万或到至和与及')


def _word_piece(token):
    words=re.findall(r'[a-z]+',token,re.I)
    residue=re.sub(r'[a-z]+','',token,flags=re.I)
    return bool(words) and any(w.lower() not in CONNECTORS for w in words) and all(
        w.lower() in NUMBER_WORDS+list(CONNECTORS) for w in words) and all(
        unicodedata.category(c)[0] in 'PSC' for c in residue)


def _numeric_piece(token):
    """A whole numeric token, including unsupported punctuation, never a suffix."""
    if token.lower().lstrip('+-') in {'nan','inf','infinity'}:return True
    if not token or not any(c.isnumeric() for c in token):return False
    if re.fullmatch(r'[0-9]+(?:\.[0-9]+)?(?:kg|mm|cm|ml|litre|liter|l|m)',token,re.I):return False
    numeric_start=token.lstrip('+−-')[:1]
    return bool(numeric_start and numeric_start.isnumeric()) or all(
        c.isnumeric() or c in CHINESE_CHARS or unicodedata.category(c)[0] in 'PSC' for c in token)


def _quantity_expression(text, unit_start):
    # Scan backwards from the unit. Lexical tokens are consumed in full before
    # validating their syntax, so 1_020, 1e3, 20／30 and unknown separators cannot
    # restart at 020, 3 or 30. Do not cross a newline or consume a preceding SKU.
    prefix=text[:unit_start].rstrip(' \t\r\u00a0\u202f')
    if not prefix or prefix[-1]=='\n':return None
    tokens=list(re.finditer(r'\S+',prefix[prefix.rfind('\n')+1:]))
    base=prefix.rfind('\n')+1
    if not tokens:return None
    last=tokens[-1];start=base+last.start();end=len(prefix);token=last.group()
    # Chinese has no word spaces: keep the numeric suffix after an introducer,
    # but retain all following characters, even when the format is unsupported.
    if any('\u4e00'<=c<='\u9fff' and c not in CHINESE_CHARS for c in token):
        first=next((i for i,c in enumerate(token) if c.isnumeric() or c=='负'),None)
        if first is None:return None
        boundaries=list(re.finditer(r'[\u4e00-\u9fff]+',token))
        boundary=next((b for b in reversed(boundaries) if any(c not in CHINESE_CHARS for c in b.group())),None)
        # A Han separator directly between numbers (1点020) is not an introducer.
        cut=first if boundary.start() and token[boundary.start()-1].isnumeric() else boundary.end()
        # A Chinese numeral may share its introducer's run (我要二十).
        if boundary.end()==len(token):cut=first
        start+=cut;token=token[cut:]
    numeric=any(c.isnumeric() for c in token)
    if not numeric and not _word_piece(token) and token.lower() not in ['nan','infinity','inf']:return None
    for index in range(len(tokens)-2,-1,-1):
        previous=tokens[index].group();word=previous.lower()
        ordinary=_word_piece(previous)
        if _numeric_piece(previous) or ordinary:
            start=base+tokens[index].start();continue
        symbol=all(unicodedata.category(c)[0] in 'PSC' for c in previous)
        if word in CONNECTORS or symbol:
            before=tokens[index-1].group() if index else ''
            if _numeric_piece(before) or _word_piece(before):
                start=base+tokens[index].start();continue
            if previous in {'+','-','−'}:start=base+tokens[index].start()
        break
    return start,end,text[start:end]


def quantities(text, units, offset=0, allow_kg=False):
    found=[]
    for unit,aliases in units.items():
        if unit=='kg' and not allow_kg:continue
        ending='(?:'+'|'.join(sorted(map(re.escape,aliases),key=len,reverse=True))+')(?![a-z])'
        for m in re.finditer(ending,text,re.I):
            expression=_quantity_expression(text,m.start())
            if expression is None:continue
            start,end,raw=expression;value=None;error=None
            # Normalization is only used to recognise ambiguous syntax. Values
            # and evidence offsets always refer to the original, unmodified text.
            normalized=unicodedata.normalize('NFKC',raw)
            if re.fullmatch(RANGE,normalized,re.I):error='multiple_quantities'
            elif re.fullmatch(r'[1-9][0-9]{0,2}(,[0-9]{3})+',raw):value=Decimal(raw.replace(',',''))
            elif re.fullmatch(r'[+\-]?[0-9]+(?:\.[0-9]+)?',raw):value=Decimal(raw)
            elif re.fullmatch(CHINESE_NUMBER+'|'+WORD_NUMBER,raw,re.I):
                value=evidence_number(raw)
                if value is None:error='quantity_format'
            else:error='quantity_format'
            if value is None and error is None:continue
            if value is not None and (not value.is_finite() or value<=0 or value>1000000 or -value.as_tuple().exponent>3 or unit!='kg' and value!=value.to_integral_value()):error='invalid_quantity'
            found.append({'raw':raw,'value':format(value,'f') if value is not None else None,'unit':unit,'span':[offset+start,offset+m.end()],'error':error})
    result=[]
    for item in sorted(found,key=lambda x:(x['span'][0],-(x['span'][1]-x['span'][0]))):
        if any(item['span'][0]<p['span'][1] and p['span'][0]<item['span'][1] for p in result):continue
        result.append(item)
    return result


def polarity(text,start,end):
    # Scope ends at punctuation, contrast and a following coordinated target.
    prefix=text[:start]
    parts=list(re.finditer(r'[.;\n!?，。；！？]|,(?![0-9])|\b(?:but|instead|tetapi|tapi|and|dan)\b|但是|而是|改为|改成|改|还有|以及|和',prefix,re.I))
    prefix=prefix[parts[-1].end():] if parts else prefix
    if re.search(r'not\s+only|不仅|不只是|bukan\s+sahaja|不确定|not\s+sure|maybe|mungkin',prefix,re.I):return 'uncertain'
    negatives=list(re.finditer(NEGATIVE,prefix,re.I))
    # English negators must be words, e.g. "no" must not match "know".
    negatives=[m for m in negatives if not m.group()[0].isascii() or not (m.start() and prefix[m.start()-1].isalpha()) and not (m.end()<len(prefix) and prefix[m.end()].isalpha())]
    suffix=text[end:]
    post_negative=re.match(r'\s*(?:不要|不用|不想要|不需要|(?:is\s+)?not\s+wanted\b|(?:tidak|tak)\s+mahu\b)',suffix,re.I)
    if re.match(r'\s*(?:is\s+)?not\s+(?:required|needed)\b',suffix,re.I):return 'uncertain'
    if len(negatives)>1 or negatives and post_negative:return 'uncertain'
    return 'negative' if post_negative or negatives and len(prefix)-negatives[-1].end()<60 else 'positive'
