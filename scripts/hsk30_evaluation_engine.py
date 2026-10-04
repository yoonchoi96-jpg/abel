#!/usr/bin/env python3
"""Deterministic QA for HSK 3.0 Level 6 written mock exams.

Canonical full written layout:
1-40 listening, 41-80 reading, 81-82 writing.
Semantic Mandarin judgment remains with Gemini.
"""
from __future__ import annotations
import json, math, re
from collections import Counter
from typing import Any

PART_RANGES={"listening":(1,40),"reading":(41,80),"writing":(81,82)}
LISTENING_SUBPARTS={"listening_p1":set(range(1,9)),"listening_p2":set(range(9,29)),"listening_p3":set(range(29,41))}
READING_SUBPARTS={"reading_p1":set(range(41,51)),"reading_p2":set(range(51,61)),"reading_p3":set(range(61,81))}
EXTREME_MARKERS=("完全","彻底","毫无","任何","所有","全部","绝对","必然","从不","从未","永远","唯一","必须","无法","零","最优")

def _num(v:Any)->int|None:
    if isinstance(v,bool): return None
    if isinstance(v,int) and v>0: return v
    if isinstance(v,str) and v.strip().isdigit() and int(v.strip())>0: return int(v.strip())
    return None
def _text(v:Any)->str: return str(v or "").strip()
def _chinese_len(v:Any)->int: return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]",_text(v)))
def _option_text(v:Any)->str: return re.sub(r"^[\\s【\\[]*[ABCD](?:[】\\]\\.、:：\\)）]|[\\.、:：\\)）]|\\s+)", "", _text(v), count=1, flags=re.I)

def evaluate_hsk30_level6(questions:list[dict[str,Any]], *, expected_total:int|None=82, expected_answer_distribution:dict[str,int]|None=None)->dict[str,Any]:
    findings=[]; nums=[_num(q.get("number")) for q in questions]; valid=[n for n in nums if n is not None]
    if expected_total is not None and len(questions)!=expected_total:
        findings.append({"rule_id":"QUESTION_COUNT","severity":"error","message":f"Expected {expected_total} tasks/questions; received {len(questions)}.","question_numbers":valid})
    counts=Counter(valid); dup=sorted(n for n,c in counts.items() if c>1)
    if dup: findings.append({"rule_id":"DUPLICATE_NUMBER","severity":"error","message":"Question numbers must be unique.","question_numbers":dup})
    missing=sorted(set(range(1,83))-set(valid))
    if expected_total==82 and missing: findings.append({"rule_id":"MISSING_NUMBER","severity":"error","message":"Full HSK 3.0 Level 6 mock must contain 1-82.","question_numbers":missing})
    answers=[]
    for q,n in zip(questions,nums):
        if n is None:
            findings.append({"rule_id":"MALFORMED_NUMBER","severity":"error","message":"Every task needs a positive integer number.","question_numbers":[0]}); continue
        part=q.get("part")
        if part not in PART_RANGES:
            findings.append({"rule_id":"INVALID_PART","severity":"error","message":"part must be listening, reading, or writing.","question_numbers":[n]}); continue
        lo,hi=PART_RANGES[part]
        if not lo<=n<=hi: findings.append({"rule_id":"PART_RANGE","severity":"error","message":f"{part} uses range {lo}-{hi}.","question_numbers":[n]})
        if n<=80:
            options=q.get("options"); answer=str(q.get("answer","")).strip().upper()
            if not isinstance(options,list) or len(options)!=4 or answer not in "ABCD":
                findings.append({"rule_id":"MC_FORMAT","severity":"error","message":"Listening/reading items must have exactly four options and an A-D answer.","question_numbers":[n]}); continue
            answers.append((n,answer)); texts=[_option_text(x) for x in options]; lengths=[_chinese_len(x) for x in texts]
            if max(lengths)-min(lengths)>=max(8,math.ceil(max(lengths)*0.45)):
                findings.append({"rule_id":"OPTION_LENGTH_LEAK","severity":"warning","message":"One option is dramatically different in length.","question_numbers":[n]})
            flags=[any(m in x for m in EXTREME_MARKERS) for x in texts]
            if flags[ord(answer)-65]: findings.append({"rule_id":"EXTREME_CORRECT","severity":"warning","message":"Correct option contains absolute/extreme wording; inspect for test-taking clues.","question_numbers":[n]})
    dist=Counter(a for _,a in answers)
    if expected_answer_distribution is not None and dict(dist)!=dict(expected_answer_distribution):
        findings.append({"rule_id":"ANSWER_DISTRIBUTION","severity":"warning","message":f"Actual distribution {dict(sorted(dist.items()))}; expected {expected_answer_distribution}.","question_numbers":[n for n,_ in answers]})
    ordered=sorted(answers); max_run=0
    if ordered:
        run=1
        for (_,a),(_,b) in zip(ordered,ordered[1:]):
            run=run+1 if a==b else 1; max_run=max(max_run,run)
        if max_run>=3: findings.append({"rule_id":"ANSWER_RUN","severity":"warning","message":f"Same answer letter appears {max_run} times consecutively.","question_numbers":[n for n,_ in ordered]})
    if expected_total==82:
        for name,expected in {**LISTENING_SUBPARTS,**READING_SUBPARTS}.items():
            actual={n for n in valid if n in expected}
            if actual!=expected: findings.append({"rule_id":"SUBPART_LAYOUT","severity":"error","message":f"{name} does not cover its canonical range.","question_numbers":sorted(actual^expected)})
        for n in (81,82):
            q=next((x for x in questions if _num(x.get("number"))==n),None)
            if q is None: continue
            expected_type="practical" if n==81 else "topic_opinion"; minimum=150 if n==81 else 300
            if q.get("writing_type") not in (None,expected_type):
                findings.append({"rule_id":"WRITING_TYPE","severity":"error","message":f"Question {n} must be {expected_type} writing.","question_numbers":[n]})
            declared=q.get("minimum_characters",minimum)
            if not isinstance(declared,int) or declared<minimum:
                findings.append({"rule_id":"WRITING_MINIMUM","severity":"error","message":f"Writing task {n} must specify at least {minimum} Chinese characters.","question_numbers":[n]})
    errors=sum(f["severity"]=="error" for f in findings); warnings=sum(f["severity"]=="warning" for f in findings)
    return {"schema_version":"abel.hsk30.qa.v1","engine":"Abel HSK 3.0 Level 6 Evaluation Engine","version":"1.0.0","exam_version":"HSK 3.0","level":6,
            "status":"FAIL" if errors else ("REVIEW" if warnings else "PASS"),"score":max(0,100-errors*25-warnings*5),
            "metrics":{"task_count":len(questions),"question_numbers":sorted(valid),"answer_distribution":dict(sorted(dist.items())),"max_answer_run":max_run,"writing_tasks":len(set(valid)&{81,82})},
            "findings":findings,
            "llm_review_required":["answer uniqueness / multiple valid answers","semantic distractor quality","natural contemporary Mandarin","transcript/passage/question alignment","paraphrase depth","factual accuracy","HSK 3.0 Level 6 difficulty","writing task fulfillment","explanation accuracy","regression after revision"]}

def build_hsk30_llm_review_prompt(questions:list[dict[str,Any]], *, transcript:str="", reference_facts:str="")->str:
    payload={"questions":questions,"transcript":transcript,"reference_facts":reference_facts}
    return """You are Abel's adversarial expert reviewer for an HSK 3.0 Level 6 mock exam.
Use ONLY this structure: 1-40 listening, 41-80 reading, 81 practical writing (>=150 Chinese characters), 82 topic/opinion writing (>=300 Chinese characters).

MANDATORY:
1. Check answer uniqueness; reject any MC item with two defensible answers.
2. Check distractors: plausible but decisively wrong; no absurd/giveaway options.
3. Check natural contemporary Mandarin, collocation, syntax, and register.
4. Check transcript/passage/question alignment; distinguish contradiction from absence.
5. Check paraphrase depth; do not reward copied wording when comprehension is intended.
6. Check option length, grammar shape, punctuation, and token leakage.
7. Check factual claims requiring verification; do not invent verification.
8. Check Level 6 difficulty; do not simplify merely for accessibility.
9. Check Reading Part 1/2/3 skill alignment.
10. Check Task 81 is realistic practical writing with enough information for >=150 characters.
11. Check Task 82 is a genuine topic/opinion task supporting >=300 characters and developed reasoning.
12. Never use legacy HSK 2.0 rules.
13. Return exactly one review per supplied number.

Return JSON only:
{"pass":true,"score":0,"critical_issues":[],"question_reviews":[{"number":0,"status":"pass|revise|reject","answer":"A","issues":[],"recommended_fix":""}],"global_issues":[],"factual_verification_needed":[]}

""" + json.dumps(payload,ensure_ascii=False,indent=2)
