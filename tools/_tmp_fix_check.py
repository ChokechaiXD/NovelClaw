"""Debug ch12 and ch58 failures"""
import json
import sys
sys.path.insert(0, 'tools')
from scorer import score_chapter

for ch in [12, 58]:
    data = json.load(open(f'novels/global-descent/chapters/{ch:04d}.th.json'))
    sp = f'novels/global-descent/chapters/{ch:04d}.cn.json'
    src = None
    try:
        src = open(sp).read()
        print(f'Ch {ch}: source {len(src)} chars')
    except:
        print(f'Ch {ch}: NO SOURCE')
    
    result = score_chapter(data, source_text=src)
    print(f'  Score: {result.weighted_total}/100, Passed: {result.passed}')
    for d in result.dimensions:
        if d.score < 0.8 or not d.passed:
            print(f'  ❌ {d.name}={d.score:.2f} pass={d.passed}')
            print(f'     {d.detail[:150]}')
    print(f'  Errors: {result.errors[:5]}')
    print()
    
    # Show paragraph info
    paras = data.get('paragraphs', [])
    print(f'  Paragraphs: {len(paras)}')
    print(f'  Total output chars: {sum(len(p) for p in paras if p != "(จบบท)")}')
    print()
