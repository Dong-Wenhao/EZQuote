"""Validate a complete quantity before evaluating it; never sum arbitrary words."""
import re
from decimal import Decimal

EN_SMALL=dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(),range(20)))
EN_TENS=dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10)))
MS_SMALL=dict(zip('kosong satu dua tiga empat lima enam tujuh lapan sembilan sepuluh sebelas'.split(),range(12)))
DIGITS={c:i for i,c in enumerate('零一二三四五六七八九')}


def _en_under_hundred(words):
    if len(words)==1:return EN_SMALL.get(words[0],EN_TENS.get(words[0]))
    if len(words)==2 and words[0] in EN_TENS and 1<=EN_SMALL.get(words[1],0)<=9:
        return EN_TENS[words[0]]+EN_SMALL[words[1]]


def _ms_under_hundred(words):
    if len(words)==1:return MS_SMALL.get(words[0])
    if len(words)==2 and 2<=MS_SMALL.get(words[0],0)<=9 and words[1]=='belas':return MS_SMALL[words[0]]+10
    if len(words) in {2,3} and 2<=MS_SMALL.get(words[0],0)<=9 and words[1]=='puluh':
        if len(words)==2:return MS_SMALL[words[0]]*10
        if 1<=MS_SMALL.get(words[2],0)<=9:return MS_SMALL[words[0]]*10+MS_SMALL[words[2]]


def _under_thousand(words,language):
    small=EN_SMALL if language=='en' else MS_SMALL
    under=_en_under_hundred if language=='en' else _ms_under_hundred
    hundred='hundred' if language=='en' else 'ratus'
    prefix=1 if language=='ms' and words[:1]==['seratus'] else 2 if len(words)>1 and 1<=small.get(words[0],0)<=9 and words[1]==hundred else 0
    if not prefix:return under(words)
    result=100 if prefix==1 else small[words[0]]*100
    tail=words[prefix:]
    if not tail:return result
    if tail[0]==('and' if language=='en' else 'dan'):tail=tail[1:]
    extra=under(tail)
    return result+extra if extra is not None and extra>0 else None


def _words(words,language):
    thousand='thousand' if language=='en' else 'ribu'
    if language=='ms' and words[:1]==['seribu']:words=['satu','ribu',*words[1:]]
    if thousand not in words:return _under_thousand(words,language)
    if words.count(thousand)!=1:return None
    index=words.index(thousand);head=_under_thousand(words[:index],language)
    if head is None or head<=0:return None
    tail=words[index+1:]
    if not tail:return head*1000
    if tail[0]==('and' if language=='en' else 'dan'):tail=tail[1:]
    extra=_under_thousand(tail,language)
    return head*1000+extra if extra is not None and extra>0 else None


def _zh_group(value):
    result='';zero=False
    for size,unit in [(1000,'千'),(100,'百'),(10,'十'),(1,'')]:
        digit,value=divmod(value,size)
        if digit:
            if zero:result+='零'
            result+='零一二三四五六七八九'[digit]+unit;zero=False
        elif result and value:zero=True
    return result


def _chinese(raw):
    raw=raw.replace('两','二').replace('〇','零');negative=raw.startswith('负');raw=raw.removeprefix('负')
    if raw=='零':return Decimal(0)
    total=section=number=0
    for char in raw:
        if char in DIGITS:number=DIGITS[char]
        elif char=='万':total+=(section+number)*10000;section=number=0
        else:section+=(number or 1)*{'十':10,'百':100,'千':1000}[char];number=0
    value=total+section+number
    if value<=0 or value>1000000:return None
    high,low=divmod(value,10000)
    canonical=(_zh_group(high)+'万'+('零' if low and low<1000 else '')+_zh_group(low)) if high else _zh_group(low)
    forms={canonical,canonical.removeprefix('一') if canonical.startswith('一十') else canonical}
    if raw not in forms:return None
    return Decimal(-value if negative else value)


def evidence_number(raw):
    raw=raw.strip().lower()
    if re.fullmatch(r'[+\-]?[0-9]+(?:\.[0-9]+)?',raw):return Decimal(raw)
    if re.fullmatch(r'[1-9][0-9]{0,2}(?:,[0-9]{3})+',raw):return Decimal(raw.replace(',',''))
    if re.fullmatch(r'负?[零〇一二两三四五六七八九十百千万]+',raw):return _chinese(raw)
    if not re.fullmatch(r'[a-z]+(?:[\s-]+[a-z]+)*',raw):return None
    words=re.split(r'[\s-]+',raw);negative=words[0] in {'minus','negative','negatif'}
    if negative:words=words[1:]
    if not words:return None
    for language in ['en','ms']:
        value=_words(words,language)
        if value is not None:return Decimal(-value if negative else value)
    return None
