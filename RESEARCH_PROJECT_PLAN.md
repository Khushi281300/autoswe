# Research Project Plan
## Oracle-free checks for LLM issue-resolving agents: a pilot study on SWE-bench Verified
**Author:** Khushi Shukla | **Prepared:** 4 October 2026 | **Target:** Report and code ready by mid-November 2026

---

### 1. Where You Are Now
- **Environment:** ~190 GB free on `C:`, Python 3.12.5, Git 2.46.0, Docker 29.7.2, WSL2 Ubuntu.
- **Repositories Cloned:** `PatchDiff` and `SWE-bench` inside `c:\D_Drive\projects\apr_overfitting_study\`.
- **Zenodo Replication Data:** Downloaded and unpacked into `PatchDiff/results/`:
  - `RQ34.csv`: 77 manually validated instances.
  - `RQ1_*_runall.json`: Developer-test failure records for OpenHands, LearnByInteract, CodeStory.
  - `RQ2_*_difftests.json`: Differential test outputs for 217 instances.
  - Baseline test-generation outputs (`coverup`, `libro`, `pynguin`).
- **SWE-bench Verified Dataset & Tool Patches:** Present under `PatchDiff/data/dataset/swebench_verified` and `PatchDiff/data/tool_results/`.
- **Configuration:** `PatchDiff/src/config.py` path-portable, `OPENAI_API_KEY` read from environment variables, and `AutoSWE` entry added.
- **Local Virtual Environment:** `.venv/` created; core dependencies (`tree-sitter`, `tree-sitter-python`, `unidiff`, `datasets`, `pandas`) verified and functioning.

---

### 2. What Exists and What You Build

| Need | Reuse (Already Exists) | You Build |
| :--- | :--- | :--- |
| **Benchmark data** | SWE-bench Verified inside `PatchDiff/data` | Nothing |
| **Patches from other agents** | Patches & resolution results for `OpenHands`, `LearnByInteract`, `CodeStory` | Your AutoSWE patches in the same format |
| **Divergence & correctness labels** | `RQ34.csv` labels and `RQ2` differential-test outputs from Zenodo | Negative set construction & any extra sample |
| **Developer-test regression records** | `RQ1` runall files | Nothing |
| **Running tests in Docker** | SWE-bench harness | Thin wrapper scripts |
| **Code parsing** | Tree-sitter, PatchDiff parser & extractor | Your scope-check & invariant logic |
| **The checks themselves** | Nothing in PatchDiff repo | `scope_checker.py` and `behavior_checker.py` (**Your Contribution**) |
| **Evaluation and statistics** | None | `evaluator.py`, tables, figures |

> [!NOTE]
> **Licence & Credit:** Use PatchDiff for research with full citation, ask the authors before redistributing code or data, and clearly document all reused versus newly developed components.

---

### 3. Study Design
**Research Question:** Can oracle-free checks, using only information an agent could see at generation time, flag incorrect or behaviourally divergent patches on SWE-bench Verified, and at what cost in wrongly flagged correct patches?
- **RQ1 (Offline):** How many incorrect patches do the checks flag, and how many correct ones do they wrongly flag, on patches that already have labels?
- **RQ2 (Comparison):** Do the checks beat simple baselines (patch size threshold, developer-test regression failures)?
- **RQ3 (Cost):** False rejections and the effect on resolve rate if the checks were used as an acceptance gate.
- **RQ4 (Optional):** Running the checks inside the AutoSWE repair loop on a small subset (if time and budget permit).

---

### 4. Design Decisions That Need Care
1. **No Oracle at Check Time:** The checks may only use the issue text, the pre-patch repository snapshot, pre-patch tests, and the candidate patch. They must never use the gold patch, the hidden `FAIL_TO_PASS` tests, or PatchDiff labels.
2. **Defining the Scope Region Without the Oracle:** Derive expected edit regions from issue text, stack traces, and symbol mentions (classes, functions, files, nearby callers) alongside structural metrics.
3. **Ground-Truth Label Sampling & Negative Set:** `RQ34.csv` contains 77 manually validated instances (mostly divergent). To measure False Positives accurately, construct a balanced negative set from resolved, non-divergent patches in RQ2.
4. **Small Samples & Confidence Intervals:** Report Wilson score or bootstrap 95% confidence intervals and clearly frame the study as a rigorous pilot.
5. **Disk & Cost Constraints:** Use single-instance runs, remove Docker images post-run, mute heavy runall caching, and use `.env` for secrets.

---

### 5. Step-by-Step Timeline (Oct 4 - Nov 15, 2026)

| Dates | Tasks | Deliverables / Milestone |
| :--- | :--- | :--- |
| **Oct 4-6** | Finish setup & Data Dictionary | Single instance tested, [DATA_DICTIONARY.md](file:///c:/D_Drive/projects/apr_overfitting_study/DATA_DICTIONARY.md) created, git repo committed. |
| **Oct 4-11** | Literature Reading | Read PatchDiff paper and related APR/SWE papers (REFINE, PAFT, SpecRover, etc.). Fill 12-row reading table. |
| **Oct 4-8** | Application Emails | Send international office email to Kyushu University; draft Prof. Zhao email. |
| **Oct 7-17** | Core Gate Implementation | Build `gates/scope_checker.py`, `gates/behavior_checker.py`, `eval/evaluator.py`, and unit tests. |
| **Oct 18-27** | Offline Evaluation | Run checks across labeled dataset; compute precision, recall, FPR, Wilson 95% CIs vs baselines. |
| **Oct 28 - Nov 5**| Optional In-Loop Pilot | (Optional) Dry-run AutoSWE on 10 instances; evaluate C0 vs C1 on 30-50 instances. |
| **Nov 1-10** | Analysis & Writing | Error analysis of false positives/negatives; write 4-6 page report draft. |
| **Nov 10-15** | Packaging & Submission | Clean repo, README for reproducibility, release tag, proposal finalization. |

---

### 6. Module Specifications

#### `gates/scope_checker.py`
- **Input:** Issue text, repository snapshot before patch, candidate patch.
- **Output:** Structural measures (files, functions, hunks, lines), list of out-of-scope edits, flag + explanation string.
- **Rule:** Thresholds calibrated on a development split, then frozen before evaluating the test split.

#### `gates/behavior_checker.py`
- **Input:** Repository snapshot, pre-existing test suite, candidate patch.
- **Output:** Tests whose outcome changed, API signature changes, exception suppression detection.
- **Rule:** Never read or execute hidden `FAIL_TO_PASS` tests.

#### `eval/evaluator.py`
- Reads patches, labels, and gate outputs.
- Computes Precision, Recall, FPR, 95% CIs, confusion matrices, and comparison against baseline heuristics.
- Records random seeds and git commit hash for full reproducibility.
