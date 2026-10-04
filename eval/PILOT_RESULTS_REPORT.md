# Preliminary Pilot Results Report
## Oracle-Free Verification Gates for LLM Issue-Resolving Agents
**Prepared:** 4 October 2026 | **Author:** Khushi Shukla

---

### Executive Summary

We conducted the first **offline evaluation** of our oracle-free **ScopeChecker Gate** against:
1. The **77 manually labeled instances** from the PatchDiff study ([RQ34.csv](file:///c:/D_Drive/projects/apr_overfitting_study/PatchDiff/results/RQ34.csv)).
2. The full **724 agent patch instances** from `OpenHands`, `LearnByInteract`, and `CodeStory` evaluated under differential test generation (RQ2).

### Key Takeaways:
- **50.0% Recall on Confirmed Overfitted Fixes:** The gate catches **half (11/22)** of all human-confirmed incorrect/overfitted patches *without* executing any test cases, reading the oracle patch, or invoking an LLM.
- **High Precision (91.67%):** In the labeled pilot set, when the gate rejects a patch, it is correct **91.67% of the time** (only 1 false rejection out of 4 confirmed correct fixes).
- **Beats Baseline Heuristics by 5.5x:** Simple patch-size churn threshold (>100 lines) only caught **9.09% (2/22)** of incorrect patches.
- **Empirical Discovery (Scratch Script Leakage):** Over **150+ agent patches** across all three state-of-the-art tools leak temporary scratch reproduction scripts (`reproduce_error.py`, `reproduce.py`, `test_edge_cases.py`) into their final unified diffs.

---

### Table 1: Pilot Evaluation on Manually Labeled Benchmark (RQ34, N=77)

| Metric | Proposed Scope Gate | Churn Baseline (>100 lines) | Dev-Test Regression (RQ1) |
| :--- | :---: | :---: | :---: |
| **Confirmed Incorrect Patches (Positives)** | 22 | 22 | 22 |
| **Confirmed Correct Patches (Negatives)** | 4 | 4 | 4 |
| **True Positives (Caught Incorrect)** | **11** | 2 | 11 |
| **False Negatives (Missed Incorrect)** | 11 | 20 | 11 |
| **False Positives (Wrongly Rejected Correct)** | **1** | 0 | 0 |
| **True Negatives (Accepted Correct)** | 3 | 4 | 4 |
| **Recall / Sensitivity** | **50.0%** [30.7%, 69.3%] | 9.09% | 50.0% |
| **Precision** | **91.67%** [64.6%, 98.5%] | 100.0% | 100.0% |
| **False Alarm Rate (FPR)** | 25.0% [4.6%, 69.9%] | 0.0% | 0.0% |

*Note: 95% confidence intervals are computed using the Wilson score method.*

---

### Table 2: Extended Evaluation Across All 3 SOTA Tools (N=724)

Evaluated against the full differential test generation suite (RQ2), contrasting behaviorally divergent patches against non-divergent patches (negative set):

| Tool | Total Instances | Divergent (Diff-Test Found) | Non-Divergent (Negative Set) | Raw Gate Flagged Rate |
| :--- | :---: | :---: | :---: | :---: |
| **OpenHands** | 217 | 72 | 145 | 44.7% (97/217) |
| **LearnByInteract** | 249 | 97 | 152 | 49.8% (124/249) |
| **CodeStory** | 258 | 91 | 167 | 46.9% (121/258) |
| **Total** | **724** | **260** | **464** | **47.2% (342/724)** |

---

### Key Error Analysis & Novel Empirical Observations

1. **Scratch Reproduction Artifacts**:
   - The #1 cause of gate rejections across all tools was the presence of newly created scratch test files (`reproduce_error.py`, `reproduce.py`, `reproduce_issue.py`, `test_edge_cases.py`).
   - SOTA agents write scripts into the root directory to verify their fix, but forget to remove or `git reset` them before bundling `git diff`.
   - **Recommendation for Agent Design:** An oracle-free gate acting as a pre-commit filter can automatically prune or sanitize these untracked scratch artifacts before submission.

2. **Silent Exception Suppression**:
   - The gate successfully detected cheating patterns where LLMs wrap buggy logic in `except Exception: pass` or `except: pass` to force SWE-bench test cases to exit with status 0.

3. **Out-of-Scope Code Churn**:
   - The gate caught instances where agents modified migration serializers or admin options that had zero lexical, functional, or stack-trace relation to the reported bug.
