#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path

HOME=Path.home(); INPUT=HOME/'.naver_wordbook'/'exports'/'abel_classified.json'; OUTPUT=HOME/'.naver_wordbook'/'exports'/'abel_gemini_education.json'
MODEL=os.environ.get('GEMINI_MODEL','gemini-3.6-flash'); URL='https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
SYSTEM="You are Abel's Chinese education engine for an advanced Korean learner preparing for HSK 6 and HSK 3.0 7–9. Be precise about nuance, register, collocation, grammar and natural usage. Never invent an HSK level. Return only valid JSON."
SCHEMA='{"definition_ko":"","nuance_ko":"","collocations":[{"zh":"","ko":""}],"examples":[{"zh":"","ko":""}],"contrast":[{"word":"","difference_ko":""}],"common_error":"","mnemonic":"","mini_quiz":{"question_ko":"","options":["","","",""],"answer":"","explanation_ko":""}}'

def now(): return datetime.now(timezone.utc).isoformat()
def load(p,d): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else d
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix('.tmp'); t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); t.replace(p)
def parse_json(s):
    s=s.strip()
    if s.startswith('```'): s='\n'.join(s.splitlines()[1:-1]).strip()
    return json.loads(s)
def get_key():
    key=os.environ.get('GEMINI_API_KEY')
    if key: return key
    p=HOME/'.naver_wordbook'/'gemini_api_key'
    if p.exists(): return p.read_text(encoding='utf-8').strip() or None
    return None

def call(w):
    key=get_key()
    if not key: raise RuntimeError('Gemini API key is not configured')
    prompt=f'''{SYSTEM}\n\nCreate one high-quality Chinese-learning card. Use supplied facts; do not fabricate. Korean explanations, Chinese examples. Give 4–6 collocations, 3 examples of increasing difficulty, and one unambiguous 4-choice quiz. Contrast only genuinely useful near-synonyms.\n\nSOURCE\nword: {w.get('word','')}\nhsk_band: {w.get('hsk_band','미매칭')}\npinyin: {w.get('pronunciation','')}\npart_of_speech: {w.get('part_of_speech','')}\nnaver_meaning: {w.get('meaning','')}\nnaver_example: {w.get('example','')}\n\nJSON SCHEMA\n{SCHEMA}'''
    body={'systemInstruction':{'parts':[{'text':SYSTEM}]},'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'temperature':0.35,'maxOutputTokens':1800,'responseMimeType':'application/json'}}
    req=urllib.request.Request(URL.format(model=MODEL),data=json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','x-goog-api-key':key},method='POST')
    with urllib.request.urlopen(req,timeout=90) as r: data=json.load(r)
    return parse_json(data['candidates'][0]['content']['parts'][0]['text'])
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--word'); ap.add_argument('--limit',type=int,default=int(os.environ.get('ABEL_GEMINI_LIMIT','20'))); ap.add_argument('--all',action='store_true'); ap.add_argument('--dry-run',action='store_true'); a=ap.parse_args()
    words=load(INPUT,{}).get('words',[]); out=load(OUTPUT,{'schema_version':1,'items':[]}); items=out.get('items',[]); done={str(x.get('word_id')) for x in items}
    targets=[w for w in words if w.get('word')==a.word] if a.word else [w for w in words if str(w.get('id')) not in done][:a.limit if not a.all else None]
    print(f'[gemini] model={MODEL} targets={len(targets)}')
    if a.dry_run: [print(w.get('word'),'|',w.get('hsk_band')) for w in targets]; return
    if not get_key(): print('[gemini] Gemini API key is not configured; nothing sent.'); return
    for w in targets:
        try: items.append({'word_id':w.get('id'),'word':w.get('word'),'hsk_band':w.get('hsk_band'),'generated_at':now(),'model':MODEL,'education':call(w)}); print('[ok]',w.get('word'))
        except (urllib.error.HTTPError,urllib.error.URLError,KeyError,ValueError,RuntimeError) as e: print('[error]',w.get('word'),e)
    save(OUTPUT,{'schema_version':1,'updated_at':now(),'source':str(INPUT),'model':MODEL,'api_calls':len(items),'items':items})
if __name__=='__main__': main()
