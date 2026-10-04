# Preliminary Pilot Results Report
## Oracle-Free Static Checks for Detecting Suspect Patches in LLM Issue-Resolving Agents
**Prepared:** 4 October 2026 | **Author:** Khushi Shukla

---

### Executive Summary

We evaluated oracle-free static checks against candidate patches produced by three state-of-the-art SWE-bench agents (`OpenHands`, `LearnByInteract`, and `CodeStory`) to test whether static scope and syntactic rules can flag suspect patches without developer reference patches (oracles).

### Key Takeaways:
1. **Static Composite Gate Operates Close to Chance Level on Divergence:** On 724 candidate patches evaluated via PatchDiff's differential test suite, 260 patches are divergent (35.9% base rate). The composite static check flagged 47.3% of divergent patches (123/260) and 50.0% of non-divergent patches (232/464), yielding a precision of **34.6%**—effectively random guessing.
2. **Developer-Test Baseline is More Specific:** Existing developer regression tests (RQ1) achieved **63.5% precision at a 7.5% false alarm rate**, significantly outperforming pure static checks in specificity.
3. **Pilot Labeled Sample (RQ34) is Positive-Biased:** On 77 manually inspected instances, the scope check flagged 11 of 22 incorrect patches (50.0%), but the sample contains only 4 non-incorrect patches, precluding a reliable false alarm rate estimate.
4. **Per-Rule Ablation:** High false alarm rates in the composite gate are driven almost entirely by broad file-scope checks (32.3% FPR) and scratch file leaks (28.2% FPR). High-precision syntactic rules (signature mutation, guard deletion) have ~1.0% false alarms but very low recall (<2%).
5. **Commit Hygiene Artifact:** 201 out of 724 patches (27.8%) accidentally commit scratch reproduction files (`reproduce_error.py`, `test_edge_cases.py`), but this occurs at identical rates across divergent (26.9%) and non-divergent (28.2%) patches, indicating it is an agent hygiene artifact rather than a functional defect predictor.
6. **Execution Overhead:** Static checks evaluated at **10.93 ms per patch** (empirically measured across 724 patches in 7.91s).

---

### Table 1: Per-Rule Ablation on Extended Benchmark (N=724, 260 Divergent, 464 Non-Divergent)

| Rule Name | Total Flagged | Divergent (TP) | Non-Divergent (FP) | Precision | False Alarm Rate (FPR) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Scratch File Leaked** | 201 | 70 / 260 (26.9%) | 131 / 464 (28.2%) | 34.8% | 28.2% |
| **Out-of-Scope File Modified** | 229 | 79 / 260 (30.4%) | 150 / 464 (32.3%) | 34.5% | 32.3% |
| **Test File Tampered** | 137 | 54 / 260 (20.8%) | 83 / 464 (17.9%) | 39.4% | 17.9% |
| **Non-Code File Modified** | 60 | 17 / 260 (6.5%) | 43 / 464 (9.3%) | 28.3% | 9.3% |
| **Excessive Files (>4)** | 35 | 9 / 260 (3.5%) | 26 / 464 (5.6%) | 25.7% | 5.6% |
| **Excessive Churn (>250)** | 13 | 3 / 260 (1.2%) | 10 / 464 (2.2%) | 23.1% | 2.2% |
| **Public Signature Mutation** | 10 | 5 / 260 (1.9%) | 5 / 464 (1.1%) | 50.0% | **1.1%** |
| **Validation Guard Removed** | 8 | 4 / 260 (1.5%) | 4 / 464 (0.9%) | 50.0% | **0.9%** |
| **Hardcoded Return Cheat** | 1 | 0 / 260 (0.0%) | 1 / 464 (0.2%) | 0.0% | 0.2% |
| **Exception Suppressed** | 0 | 0 / 260 (0.0%) | 0 / 464 (0.0%) | 0.0% | 0.0% |

---

### Table 2: Benchmark Comparison Against Developer Regression Tests

| Method | Recall on Divergence | Precision | False Alarm Rate (FPR) | Execution Latency |
| :--- | :---: | :---: | :---: | :---: |
| **Composite Static Gate (Raw)** | **47.3%** (123/260) | 34.6% | 50.0% | **10.93 ms** |
| **Composite Static Gate (Sanitized)** | 30.4% (79/260) | 34.5% | 32.3% | **11.45 ms** |
| **Baseline: Developer Regression Tests (RQ1)** | 23.5% (61/260) | **63.5%** | **7.5%** | Minutes to Hours (Docker) |
| **Baseline: Churn > 100 lines** | 8.1% (21/260) | 29.6% | 10.8% | Static |

---

### Research Implications

Pure static checks cannot reliably serve as a stand-alone gate because broad structural rules flag non-divergent patches at the same rate as divergent ones. However, their negligible computational cost (10.93 ms) makes them effective as:
1. **Pre-submission sanitizers:** Removing scratch scripts before creating pull requests.
2. **Soft warnings:** Prompting LLMs to verify whether out-of-scope edits are truly intentional.
3. **Triage filters:** Combining high-specificity syntactic rules with lightweight test execution for a hybrid gate.
