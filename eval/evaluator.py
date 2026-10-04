"""
eval/evaluator.py

Offline evaluation harness for oracle-free APR verification gates.
Evaluates gate precision, recall, and false-alarm rates against:
1. The 77 manually verified instances in RQ34.csv.
2. The full RQ2 differential testing benchmark across 200+ instances per tool.
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
        self.ds = None
        self.ds_dict = {}
        self.rq34_df = None
        self.rq1_records = {}
        self.rq2_records = {}

    def load_datasets(self):
        """Loads SWE-bench verified, RQ34 labels, RQ1 failure records, and RQ2 diff tests."""
        print(f"Loading SWE-bench Verified dataset...")
        self.ds = load_from_disk(self.verified_ds_path)
        self.ds_dict = {item["instance_id"]: item for item in self.ds}

        rq34_file = os.path.join(self.results_dir, "RQ34.csv")
        self.rq34_df = pd.read_csv(rq34_file)

        # Load RQ1 developer-test failure records & RQ2 differential tests
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
        """
        Evaluates the gate on both:
        1. Confirmed manual instances (RQ34).
        2. All RQ2 evaluated instances (divergent vs non-divergent negative set).
        """
        if not self.ds_dict:
            self.load_datasets()

        records = []
        all_tool_patches = {tool: self.load_tool_patches(tool) for tool in self.tools}

        # Build mapping of RQ34 labels: (tool, instance_id) -> row
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

                # Run ScopeChecker gate
                check_res = self.scope_checker.check(model_patch, problem_statement=problem_statement)

                # Has differential test generated in RQ2?
                has_diff_test = any(len(item.get("differential_tests", [])) > 0 for item in test_attempts)

                # Check RQ1 developer-test failure
                rq1_data = self.rq1_records.get(tool, {}).get(iid, {})
                rq1_has_regression = len(rq1_data.get("oracle_pass_model_fail", [])) > 0

                # Check RQ34 manual label if present
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
                    # Gate Decision
                    "gate_passed": check_res.is_valid,
                    "gate_flagged": not check_res.is_valid,
                    "rejection_reasons": "|".join(check_res.rejection_reasons),
                    # Metrics
                    "num_files": check_res.metrics.num_files_modified,
                    "total_churn": check_res.metrics.total_churn,
                    "test_file_tampering": len(check_res.metrics.modified_test_files) > 0,
                    "non_code_files": len(check_res.metrics.modified_non_code_files) > 0,
                    "unrelated_files": len(check_res.metrics.files_unrelated_to_issue) > 0,
                    "exception_suppressed": check_res.metrics.broad_exception_swallows > 0,
                    # Baselines
                    "baseline_churn_flagged": check_res.metrics.total_churn > 100,
                    "baseline_rq1_regression_flagged": rq1_has_regression,
                })

        return pd.DataFrame(records)

    @staticmethod
    def compute_metrics_for_slice(df: pd.DataFrame, positive_col: str, negative_col: str) -> Dict[str, Any]:
        positives = df[df[positive_col] == True]
        negatives = df[df[negative_col] == True]

        tp = len(positives[positives["gate_flagged"] == True])
        fn = len(positives[positives["gate_passed"] == True])
        fp = len(negatives[negatives["gate_flagged"] == True])
        tn = len(negatives[negatives["gate_passed"] == True])

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
    print("Executing comprehensive offline gate evaluation...")
    df = evaluator.evaluate_extended()

    output_dir = os.path.join(WORKSPACE_ROOT, "eval")
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "extended_eval_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"Saved {len(df)} instance evaluation records to {csv_path}")

    # 1. Pilot subset: RQ34 confirmed instances
    rq34_df = df[df["in_rq34_manual_set"] == True].copy()
    rq34_df["is_pos"] = rq34_df["correctness"].str.startswith("incorrect")
    rq34_df["is_neg"] = rq34_df["correctness"].str.startswith("correct")
    pilot_metrics = evaluator.compute_metrics_for_slice(rq34_df, "is_pos", "is_neg")

    # 2. Extended dataset: Divergent vs Non-Divergent (Negative Set)
    df["is_divergent"] = df["has_diff_test"] == True
    df["is_nondivergent"] = df["has_diff_test"] == False
    extended_metrics = evaluator.compute_metrics_for_slice(df, "is_divergent", "is_nondivergent")

    # Save summary
    summary_report = {
        "pilot_rq34_manual_metrics": pilot_metrics,
        "extended_rq2_benchmark_metrics": extended_metrics,
    }
    with open(os.path.join(output_dir, "extended_summary_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=4)

    print("\n" + "="*65)
    print("PILOT RQ34 CONFIRMED INSTANCES (N=77)")
    print("="*65)
    for k, v in pilot_metrics.items():
        print(f"  {k:24s}: {v}")

    print("\n" + "="*65)
    print("EXTENDED BENCHMARK: DIVERGENT VS NON-DIVERGENT (N={})".format(len(df)))
    print("="*65)
    for k, v in extended_metrics.items():
        print(f"  {k:24s}: {v}")
    print("="*65)


if __name__ == "__main__":
    main()
