"""
eval/run_per_rule_analysis.py

Performs granular, rule-by-rule ablation across all 724 patches.
Computes 95% Wilson score confidence intervals for Precision, Recall, and False Alarm Rate (FPR).
Categorizes rules rigorously, including rarely-triggered rules.
"""

import sys
import os
import time
import json
import math
from typing import Tuple
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.evaluator import GateEvaluator, wilson_score_interval

evaluator = GateEvaluator()
evaluator.load_datasets()

tools = ['OpenHands', 'LearnByInteract', 'CodeStory']
all_tool_patches = {tool: evaluator.load_tool_patches(tool) for tool in tools}

records = []
t0 = time.perf_counter()

for tool, rq2_data in evaluator.rq2_records.items():
    tool_patches = all_tool_patches.get(tool, {})
    for iid, test_attempts in rq2_data.items():
        patch_info = tool_patches.get(iid)
        if not patch_info:
            continue
        instance_meta = evaluator.ds_dict.get(iid, {})
        problem_statement = instance_meta.get('problem_statement', '')
        model_patch = patch_info['model_patch']
        has_diff_test = any(len(item.get('differential_tests', [])) > 0 for item in test_attempts)
        
        # Check individual scope rules
        s_res = evaluator.scope_checker.check(model_patch, problem_statement=problem_statement)
        b_res = evaluator.behavior_checker.check(model_patch)
        
        reasons_s = s_res.rejection_reasons
        reasons_b = b_res.rejection_reasons
        all_reasons = reasons_s + reasons_b  # Fixed bug: concatenated lists
        
        r_scratch = any('reproduce' in r.lower() or 'test_edge_cases' in r.lower() for r in reasons_s)
        r_test_tamper = any('TEST_FILE_TAMPERING' in r for r in reasons_s)
        r_non_code = any('NON_CODE_FILE_MODIFICATION' in r for r in reasons_s)
        r_out_of_scope = any('OUT_OF_SCOPE_FILE' in r for r in reasons_s)
        r_files = any('EXCESSIVE_FILES_MODIFIED' in r for r in reasons_s)
        r_churn = any('EXCESSIVE_CHURN' in r for r in reasons_s)
        
        r_empty = any('EMPTY_PATCH' in r for r in all_reasons)
        r_except = any('EXCEPTION_SUPPRESSION' in r for r in all_reasons)
        r_hardcode = any('HARDCODED_TEST_OVERFIT' in r for r in all_reasons)
        r_sig = any('PUBLIC_API_MUTATION' in r for r in all_reasons)
        r_guard = any('VALIDATION_GUARD_REMOVAL' in r for r in all_reasons)
        
        records.append({
            'tool': tool,
            'instance_id': iid,
            'has_diff_test': has_diff_test,
            'r_scratch': r_scratch,
            'r_test_tamper': r_test_tamper,
            'r_non_code': r_non_code,
            'r_out_of_scope': r_out_of_scope,
            'r_files': r_files,
            'r_churn': r_churn,
            'r_empty': r_empty,
            'r_except': r_except,
            'r_hardcode': r_hardcode,
            'r_sig': r_sig,
            'r_guard': r_guard,
        })

total_time = time.perf_counter() - t0
avg_time_ms = (total_time / len(records)) * 1000

rdf = pd.DataFrame(records)
pos_mask = rdf['has_diff_test'] == True
neg_mask = rdf['has_diff_test'] == False
total_pos = int(pos_mask.sum())
total_neg = int(neg_mask.sum())

rule_names = [
    ('r_scratch', 'Scratch File Leaked'),
    ('r_out_of_scope', 'Out-of-Scope File Modified'),
    ('r_test_tamper', 'Test File Tampered'),
    ('r_non_code', 'Non-Code File Modified'),
    ('r_files', 'Excessive Files (>4)'),
    ('r_churn', 'Excessive Churn (>250)'),
    ('r_sig', 'Public Signature Mutation'),
    ('r_guard', 'Validation Guard Removed'),
    ('r_hardcode', 'Hardcoded Return Cheat'),
    ('r_empty', 'Empty Patch'),
    ('r_except', 'Exception Suppressed'),
]

header = f"{'Rule Name':<28s} | {'Total':<6s} | {'Divergent (TP)':<10s} | {'Recall [95% CI]':<20s} | {'Non-Div (FP)':<12s} | {'FPR [95% CI]':<20s} | {'Precision [95% CI]':<22s} | {'Assessment'}"
print("=" * len(header))
print(f"GRANULAR PER-RULE ABLATION (N=724, Positives={total_pos}, Negatives={total_neg})")
print(f"Timing: {total_time:.3f}s total ({avg_time_ms:.2f} ms/patch)")
print("=" * len(header))
print(header)
print("-" * len(header))

rule_summary = {}
for col, label in rule_names:
    flagged = rdf[col] == True
    tp = int((flagged & pos_mask).sum())
    fp = int((flagged & neg_mask).sum())
    tot = int(flagged.sum())
    
    rec = tp / total_pos if total_pos > 0 else 0.0
    rec_ci = wilson_score_interval(tp, total_pos)
    
    fpr = fp / total_neg if total_neg > 0 else 0.0
    fpr_ci = wilson_score_interval(fp, total_neg)
    
    prec = tp / tot if tot > 0 else 0.0
    prec_ci = wilson_score_interval(tp, tot) if tot > 0 else (0.0, 0.0)

    if tot == 0:
        assessment = "Never triggered"
    elif tot < 20:
        assessment = "Rarely triggered, inconclusive"
    elif abs(prec - (total_pos / len(rdf))) < 0.05:
        assessment = "At chance level (uninformative)"
    else:
        assessment = "Weak signal"

    rule_summary[col] = {
        'label': label,
        'total_flagged': tot,
        'tp': tp,
        'fp': fp,
        'recall': round(rec, 4),
        'recall_95ci': rec_ci,
        'fpr': round(fpr, 4),
        'fpr_95ci': fpr_ci,
        'precision': round(prec, 4),
        'precision_95ci': prec_ci,
        'assessment': assessment,
    }
    
    rec_str = f"{rec*100:4.1f}% [{rec_ci[0]*100:4.1f}%,{rec_ci[1]*100:4.1f}%]"
    fpr_str = f"{fpr*100:4.1f}% [{fpr_ci[0]*100:4.1f}%,{fpr_ci[1]*100:4.1f}%]"
    prec_str = f"{prec*100:4.1f}% [{prec_ci[0]*100:4.1f}%,{prec_ci[1]*100:4.1f}%]" if tot > 0 else "N/A"
    
    print(f"{label:<28s} | {tot:<6d} | {tp:<10d} | {rec_str:<20s} | {fp:<12d} | {fpr_str:<20s} | {prec_str:<22s} | {assessment}")

print("=" * len(header))

with open('eval/per_rule_summary.json', 'w') as f:
    json.dump({'timing_ms_per_patch': round(avg_time_ms, 2), 'rules': rule_summary}, f, indent=4)
