"""
eval/run_per_rule_analysis.py

Performs granular, rule-by-rule ablation across all 724 patches.
Measures execution timing, per-tool breakdown, precision, recall, and false alarm rate
for each rule individually against the divergent (positive) vs non-divergent (negative) set.
"""

import sys
import os
import time
import json
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.evaluator import GateEvaluator

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
        
        r_scratch = any('reproduce' in r.lower() or 'test_edge_cases' in r.lower() for r in reasons_s)
        r_test_tamper = any('TEST_FILE_TAMPERING' in r for r in reasons_s)
        r_non_code = any('NON_CODE_FILE_MODIFICATION' in r for r in reasons_s)
        r_out_of_scope = any('OUT_OF_SCOPE_FILE' in r for r in reasons_s)
        r_files = any('EXCESSIVE_FILES_MODIFIED' in r for r in reasons_s)
        r_churn = any('EXCESSIVE_CHURN' in r for r in reasons_s)
        
        r_except = any('EXCEPTION_SUPPRESSION' in r for r in reasons_b or reasons_s)
        r_hardcode = any('HARDCODED_TEST_OVERFIT' in r for r in reasons_b)
        r_sig = any('PUBLIC_API_MUTATION' in r for r in reasons_b)
        r_guard = any('VALIDATION_GUARD_REMOVAL' in r for r in reasons_b)
        
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
            'r_except': r_except,
            'r_hardcode': r_hardcode,
            'r_sig': r_sig,
            'r_guard': r_guard,
        })

total_time = time.perf_counter() - t0
avg_time_ms = (total_time / len(records)) * 1000

print(f"Timing: Evaluated {len(records)} patches in {total_time:.3f}s -> {avg_time_ms:.2f} ms per patch")

rdf = pd.DataFrame(records)
pos_mask = rdf['has_diff_test'] == True
neg_mask = rdf['has_diff_test'] == False
total_pos = pos_mask.sum()
total_neg = neg_mask.sum()

print(f"\nTotal Patches: {len(rdf)} (Divergent: {total_pos}, Non-Divergent: {total_neg})")
print("Per-tool breakdown of all patches:", rdf['tool'].value_counts().to_dict())
print("Per-tool breakdown of divergent patches:", rdf[pos_mask]['tool'].value_counts().to_dict())
print("Per-tool breakdown of scratch file leaks:", rdf[rdf['r_scratch'] == True]['tool'].value_counts().to_dict())

rule_names = [
    ('r_scratch', 'Scratch File Leaked'),
    ('r_test_tamper', 'Test File Tampered'),
    ('r_non_code', 'Non-Code File Modified'),
    ('r_out_of_scope', 'Out-of-Scope File Modified'),
    ('r_files', 'Excessive Files (>4)'),
    ('r_churn', 'Excessive Churn (>250)'),
    ('r_except', 'Exception Suppressed'),
    ('r_hardcode', 'Hardcoded Return Cheat'),
    ('r_sig', 'Public Signature Mutation'),
    ('r_guard', 'Validation Guard Removed'),
]

header = f"{'Rule Name':<28s} | {'Total Flagged':<13s} | {'Divergent (TP)':<16s} | {'Non-Div (FP)':<14s} | {'Precision':<10s} | {'FPR':<6s}"
print("\n" + "=" * len(header))
print(header)
print("-" * len(header))

rule_summary = {}
for col, label in rule_names:
    flagged = rdf[col] == True
    tp = int((flagged & pos_mask).sum())
    fp = int((flagged & neg_mask).sum())
    tot = int(flagged.sum())
    prec = tp / tot if tot > 0 else 0.0
    fpr = fp / total_neg if total_neg > 0 else 0.0
    rec = tp / total_pos if total_pos > 0 else 0.0
    rule_summary[col] = {
        'label': label,
        'total_flagged': tot,
        'tp': tp,
        'fp': fp,
        'recall': round(rec, 4),
        'precision': round(prec, 4),
        'fpr': round(fpr, 4)
    }
    print(f"{label:<28s} | {tot:<13d} | {tp}/{total_pos:<4d} ({rec*100:4.1f}%) | {fp}/{total_neg:<4d} ({fpr*100:4.1f}%) | {prec*100:5.1f}%     | {fpr*100:4.1f}%")
print("=" * len(header))

# Save summary json
with open('eval/per_rule_summary.json', 'w') as f:
    json.dump({'timing_ms_per_patch': round(avg_time_ms, 2), 'rules': rule_summary}, f, indent=4)
