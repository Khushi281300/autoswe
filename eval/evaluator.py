"""
eval/evaluator.py

Offline evaluation harness for oracle-free APR verification gates.
Evaluates gate precision, recall, and false-alarm rates against:
1. The 77 manually verified instances in RQ34.csv.
2. The full RQ2 differential testing benchmark across 724 instances.
Compares:
- ScopeChecker alone
- BehaviorChecker alone
- CompositeVerificationGate (Raw)
- CompositeVerificationGate (Sanitized)
- Baselines (Size Churn > 100, Developer-test Regression)
"""

import os
import sys
import json
import math
from typing import Dict, List, Any, Tuple
import pandas as pd
from datasets import load_from_disk

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from gates.scope_checker import ScopeChecker
from gates.behavior_checker import BehaviorChecker
from gates.composite_gate import CompositeVerificationGate


def wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Computes Wilson score 95% confidence interval for a binomial proportion."""
    if total == 0:
        return 0.0, 0.0
    z = 1.95996  # 95% confidence
    p = successes / total
    denom = 1 + (z**2) / total
    center = (p + (z**2) / (2 * total)) / denom
    margin = (z * math.sqrt((p * (1 - p) / total) + (z**2) / (4 * (total**2)))) / denom
    return round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)


class GateEvaluator:
    def __init__(self, workspace_root: str = WORKSPACE_ROOT):
        self.workspace_root = workspace_root
        self.patchdiff_dir = os.path.join(workspace_root, "PatchDiff")
        self.verified_ds_path = os.path.join(self.patchdiff_dir, "data", "dataset", "swebench_verified")
        self.tool_results_path = os.path.join(self.patchdiff_dir, "data", "tool_results")
        self.results_dir = os.path.join(self.patchdiff_dir, "results")
        
        self.tools = {
            "OpenHands": "20241029_OpenHands-CodeAct-2.1-sonnet-20241022_verified",
            "LearnByInteract": "20250110_learn_by_interact_claude3.5",
            "CodeStory": "20241221_codestory_midwit_claude-3-5-sonnet_swe-search",
        }
        
        self.scope_checker = ScopeChecker()
        self.behavior_checker = BehaviorChecker()
        self.composite_raw = CompositeVerificationGate(auto_sanitize_scratch_files=False)
        self.composite_sanitized = CompositeVerificationGate(auto_sanitize_scratch_files=True)

        self.ds = None
        self.ds_dict = {}
        self.rq34_df = None
        self.rq1_records = {}
        self.rq2_records = {}

    def load_datasets(self):
        """Loads SWE-bench verified, RQ34 labels, RQ1 failure records, and RQ2 diff tests."""
        print("Loading SWE-bench Verified dataset...")
        self.ds = load_from_disk(self.verified_ds_path)
        self.ds_dict = {item["instance_id"]: item for item in self.ds}

        rq34_file = os.path.join(self.results_dir, "RQ34.csv")
        self.rq34_df = pd.read_csv(rq34_file)

        for tool in self.tools:
            rq1_file = os.path.join(self.results_dir, f"RQ1_{tool}_runall.json")
            if os.path.exists(rq1_file):
                with open(rq1_file, "r", encoding="utf-8") as f:
                    self.rq1_records[tool] = json.load(f)
            else:
                self.rq1_records[tool] = {}

            rq2_file = os.path.join(self.results_dir, f"RQ2_{tool}_difftests.json")
            if os.path.exists(rq2_file):
                with open(rq2_file, "r", encoding="utf-8") as f:
                    self.rq2_records[tool] = json.load(f)
            else:
                self.rq2_records[tool] = {}

    def load_tool_patches(self, tool_name: str) -> Dict[str, Dict[str, Any]]:
        """Loads agent predictions and resolution status for a given tool."""
        tool_folder = os.path.join(self.tool_results_path, self.tools[tool_name])
        preds_file = os.path.join(tool_folder, "all_preds.jsonl")
        res_file = os.path.join(tool_folder, "results.json")

        with open(res_file, "r", encoding="utf-8") as f:
            res_data = json.load(f)
        resolved_set = set(res_data.get("resolved", []))

        patches = {}
        with open(preds_file, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                iid = item["instance_id"]
                patches[iid] = {
                    "instance_id": iid,
                    "model_patch": item.get("model_patch", ""),
                    "model_name_or_path": item.get("model_name_or_path", ""),
                    "is_resolved": iid in resolved_set,
                }
        return patches

    def evaluate_extended(self) -> pd.DataFrame:
        """Evaluates all gates across the benchmark."""
        if not self.ds_dict:
            self.load_datasets()

        records = []
        all_tool_patches = {tool: self.load_tool_patches(tool) for tool in self.tools}

        rq34_map = {}
        for _, row in self.rq34_df.iterrows():
            rq34_map[(row["tool"], row["instance_id"])] = row

        for tool, rq2_data in self.rq2_records.items():
            tool_patches = all_tool_patches.get(tool, {})
            for iid, test_attempts in rq2_data.items():
                patch_info = tool_patches.get(iid)
                if not patch_info:
                    continue

                instance_meta = self.ds_dict.get(iid, {})
                problem_statement = instance_meta.get("problem_statement", "")
                model_patch = patch_info["model_patch"]

                # 1. Scope Checker
                scope_res = self.scope_checker.check(model_patch, problem_statement=problem_statement)

                # 2. Behavior Checker
                behavior_res = self.behavior_checker.check(model_patch)

                # 3. Composite Raw (rejects scratch files)
                comp_raw_res = self.composite_raw.evaluate(model_patch, problem_statement=problem_statement)

                # 4. Composite Sanitized (prunes scratch files before checking)
                comp_san_res = self.composite_sanitized.evaluate(model_patch, problem_statement=problem_statement)

                # Ground Truth info
                has_diff_test = any(len(item.get("differential_tests", [])) > 0 for item in test_attempts)
                rq1_data = self.rq1_records.get(tool, {}).get(iid, {})
                rq1_has_regression = len(rq1_data.get("oracle_pass_model_fail", [])) > 0

                manual_label = rq34_map.get((tool, iid))
                diff_pattern = manual_label["diff_pattern"] if manual_label is not None else ("divergent" if has_diff_test else "non_divergent")
                correctness = manual_label["correctness"] if manual_label is not None else ("unlabeled_divergent" if has_diff_test else "likely_correct_nondivergent")

                records.append({
                    "tool": tool,
                    "instance_id": iid,
                    "diff_pattern": diff_pattern,
                    "correctness": correctness,
                    "has_diff_test": has_diff_test,
                    "in_rq34_manual_set": manual_label is not None,
                    "is_resolved_in_bench": patch_info["is_resolved"],
                    # Gate Decisions (Flagged = True means rejected as overfitted)
                    "scope_flagged": not scope_res.is_valid,
                    "behavior_flagged": not behavior_res.is_valid,
                    "composite_raw_flagged": not comp_raw_res.is_valid,
                    "composite_sanitized_flagged": not comp_san_res.is_valid,
                    "pruned_scratch_count": len(comp_san_res.pruned_scratch_files),
                    "reasons_scope": "|".join(scope_res.rejection_reasons),
                    "reasons_behavior": "|".join(behavior_res.rejection_reasons),
                    "reasons_composite_sanitized": "|".join(comp_san_res.rejection_reasons),
                    # Baselines
                    "baseline_churn_flagged": scope_res.metrics.total_churn > 100,
                    "baseline_rq1_regression_flagged": rq1_has_regression,
                })

        return pd.DataFrame(records)

    @staticmethod
    def compute_metrics_for_slice(df: pd.DataFrame, flag_col: str, positive_mask: pd.Series, negative_mask: pd.Series) -> Dict[str, Any]:
        positives = df[positive_mask]
        negatives = df[negative_mask]

        tp = int((positives[flag_col] == True).sum())
        fn = int((positives[flag_col] == False).sum())
        fp = int((negatives[flag_col] == True).sum())
        tn = int((negatives[flag_col] == False).sum())

        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0

        return {
            "total_positives": len(positives),
            "total_negatives": len(negatives),
            "true_positives": tp,
            "false_negatives": fn,
            "false_positives": fp,
            "true_negatives": tn,
            "recall": round(recall, 4),
            "recall_95ci": wilson_score_interval(tp, tp + fn),
            "false_alarm_rate": round(fpr, 4),
            "fpr_95ci": wilson_score_interval(fp, fp + tn),
            "precision": round(precision, 4),
            "precision_95ci": wilson_score_interval(tp, tp + fp),
        }


def main():
    evaluator = GateEvaluator()
    print("Executing unified offline gate evaluation...")
    df = evaluator.evaluate_extended()

    output_dir = os.path.join(WORKSPACE_ROOT, "eval")
    os.makedirs(output_dir, exist_ok=True)
    df.to_csv(os.path.join(output_dir, "extended_eval_results.csv"), index=False)

    # RQ34 slice (Confirmed incorrect vs confirmed correct)
    rq34_mask = df["in_rq34_manual_set"] == True
    rq34_pos = rq34_mask & df["correctness"].str.startswith("incorrect")
    rq34_neg = rq34_mask & df["correctness"].str.startswith("correct")

    # RQ2 slice (Divergent vs Non-Divergent)
    rq2_pos = df["has_diff_test"] == True
    rq2_neg = df["has_diff_test"] == False

    gates_to_test = [
        ("scope_flagged", "ScopeChecker Alone"),
        ("behavior_flagged", "BehaviorChecker Alone"),
        ("composite_raw_flagged", "Composite Gate (Raw)"),
        ("composite_sanitized_flagged", "Composite Gate (Sanitized)"),
        ("baseline_churn_flagged", "Baseline: Churn > 100"),
        ("baseline_rq1_regression_flagged", "Baseline: RQ1 Regression"),
    ]

    print("\n" + "="*85)
    print("PILOT RQ34 CONFIRMED INSTANCES EVALUATION (N=77)")
    print("="*85)
    print(f"{'Gate / Baseline':<32s} | {'TP/Pos':<8s} | {'Recall':<8s} | {'FP/Neg':<8s} | {'FPR':<8s} | {'Precision':<8s}")
    print("-" * 85)

    summary_rq34 = {}
    for col, name in gates_to_test:
        m = evaluator.compute_metrics_for_slice(df, col, rq34_pos, rq34_neg)
        summary_rq34[name] = m
        print(f"{name:<32s} | {m['true_positives']}/{m['total_positives']:<5d} | {m['recall']*100:5.1f}%  | {m['false_positives']}/{m['total_negatives']:<5d} | {m['false_alarm_rate']*100:5.1f}% | {m['precision']*100:5.1f}%")

    print("\n" + "="*85)
    print("EXTENDED BENCHMARK: DIVERGENT VS NON-DIVERGENT (N=724)")
    print("="*85)
    print(f"{'Gate / Baseline':<32s} | {'TP/Pos':<8s} | {'Recall':<8s} | {'FP/Neg':<8s} | {'FPR':<8s} | {'Precision':<8s}")
    print("-" * 85)

    summary_rq2 = {}
    for col, name in gates_to_test:
        m = evaluator.compute_metrics_for_slice(df, col, rq2_pos, rq2_neg)
        summary_rq2[name] = m
        print(f"{name:<32s} | {m['true_positives']}/{m['total_positives']:<5d} | {m['recall']*100:5.1f}%  | {m['false_positives']}/{m['total_negatives']:<5d} | {m['false_alarm_rate']*100:5.1f}% | {m['precision']*100:5.1f}%")
    print("=" * 85)

    with open(os.path.join(output_dir, "unified_summary_metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"rq34_pilot": summary_rq34, "rq2_extended": summary_rq2}, f, indent=4)
    print(f"\nSaved unified summary metrics to {os.path.join(output_dir, 'unified_summary_metrics.json')}")


if __name__ == "__main__":
    main()
