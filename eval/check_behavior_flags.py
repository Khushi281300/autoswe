import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.evaluator import GateEvaluator

evaluator = GateEvaluator()
evaluator.load_datasets()

tools = ['OpenHands', 'LearnByInteract', 'CodeStory']
all_tool_patches = {tool: evaluator.load_tool_patches(tool) for tool in tools}

flagged_behavior = []

for tool, rq2_data in evaluator.rq2_records.items():
    tool_patches = all_tool_patches.get(tool, {})
    for iid, test_attempts in rq2_data.items():
        patch_info = tool_patches.get(iid)
        if not patch_info:
            continue
        model_patch = patch_info['model_patch']
        has_diff_test = any(len(item.get('differential_tests', [])) > 0 for item in test_attempts)
        b_res = evaluator.behavior_checker.check(model_patch)
        if not b_res.is_valid:
            flagged_behavior.append({
                'tool': tool,
                'instance_id': iid,
                'has_diff_test': has_diff_test,
                'reasons': b_res.rejection_reasons
            })

df_b = pd.DataFrame(flagged_behavior)
print('Total patches flagged by BehaviorChecker:', len(df_b))
print('Divergent (TP):', int((df_b['has_diff_test'] == True).sum()))
print('Non-Divergent (FP):', int((df_b['has_diff_test'] == False).sum()))
for idx, row in df_b.iterrows():
    print(f"[{row['tool']}] {row['instance_id']} (DiffTest={row['has_diff_test']}): {row['reasons']}")
