#!/usr/bin/env python3
from pathlib import Path
import json, os, shutil
from datetime import datetime, timezone

HOME=Path.home()
SRC=HOME/'.naver_wordbook/exports/abel_classified.json'
DST=HOME/'.naver_wordbook/exports/abel_gemini_education.json'

def root():
    p=os.environ.get('ABEL_DRIVE_DIR')
    if p: return Path(p).expanduser()
    c=HOME/'Library/CloudStorage'
    xs=sorted(c.glob('GoogleDrive-*/My Drive')) if c.exists() else []
    if xs: return xs[0]/'Abel'
    raise SystemExit('Set ABEL_DRIVE_DIR to your local Google Drive/Abel folder')

def main():
    r=root(); inbox=r/'INBOX'; outbox=r/'OUTBOX'; archive=r/'ARCHIVE'
    for p in (inbox,outbox,archive): p.mkdir(parents=True,exist_ok=True)
    data=json.loads(SRC.read_text(encoding='utf-8')) if SRC.exists() else {'words':[]}
    done=json.loads(DST.read_text(encoding='utf-8')).get('items',[]) if DST.exists() else []
    ids={str(x.get('word_id')) for x in done}
    words=[w for w in data.get('words',[]) if str(w.get('id')) not in ids]
    if words:
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
        (inbox/f'batch-{stamp}.json').write_text(json.dumps({'created_at':datetime.now(timezone.utc).isoformat(),'words':words},ensure_ascii=False,indent=2),encoding='utf-8')
        print('exported',len(words))
    for p in sorted(outbox.glob('*.json')):
        x=json.loads(p.read_text(encoding='utf-8')); items=done+[i for i in x.get('items',[])]
        seen={}; [seen.__setitem__(str(i.get('word_id')),i) for i in items]
        DST.parent.mkdir(parents=True,exist_ok=True); DST.write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(),'api_calls':0,'items':list(seen.values())},ensure_ascii=False,indent=2),encoding='utf-8')
        shutil.move(str(p),str(archive/p.name))
        done=list(seen.values())
        print('imported',len(x.get('items',[])))

if __name__=='__main__': main()
