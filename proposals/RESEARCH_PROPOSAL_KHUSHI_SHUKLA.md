# Research Proposal
## Oracle-Free Static Checks for Detecting Suspect Patches in LLM Issue-Resolving Agents: A Pilot Study

**Applicant:** Khushi Shukla  
**Prospective Degree:** Postgraduate Research Student / Master's Program  
**Target Lab:** Software Engineering Laboratory, Graduate School of Information Science and Electrical Engineering (ISEE), Kyushu University  
**Prospective Supervisor:** Prof. Jianjun Zhao  
**Date:** October 2026  

---

### 1. Introduction & Research Problem

Recent autonomous software engineering agents (such as OpenHands, CodeStory, and SWE-agent) resolve real-world software defects by interacting with repositories and unit test suites. On benchmarks like SWE-bench Verified, an agent-generated candidate patch is marked as "resolved" if it passes the repository's existing regression suite and reproduction unit tests ($T_{\text{fail} \to \text{pass}} \land T_{\text{pass} \to \text{pass}}$).

However, software test suites are notoriously sparse and incomplete. Consequently, plausible patches frequently suffer from behavioral divergence or test overfitting. Recent empirical studies reveal that 29.6% of plausible patches on SWE-bench Verified behave differently from the developer's reference patch under differential testing (Wang, Pradel, and Liu, ICSE 2026), of which a manually inspected sample found 28.6% certainly incorrect.

Existing differential testing techniques (such as PatchDiff) differentiate candidate patches post-hoc by comparing them against the human developer's reference fix (the Oracle) and executing LLM-generated tests inside heavy Docker environments. In practical deployment, however, **no developer oracle exists**.

**Research Question:** Can lightweight, oracle-free checks—relying solely on the issue text, the pre-patch repository state, pre-patch tests, and the candidate patch diff—reliably flag suspect or overfitted patches at generation time, and at what cost in false alarms?

---

### 2. Related Work & Novelty

| Study / Tool | Approach | Limitations | How My Proposed Work Differs |
| :--- | :--- | :--- | :--- |
| **PatchDiff** (Wang et al., ICSE 2026) | LLM-based differential test generation to differentiate candidate fixes from developer fixes. | Requires the human oracle patch; high compute overhead (~3GB Docker images per task). | I investigate **oracle-free** verification runnable at generation time *without* the developer patch. |
| **AutoCodeRover** (Zhang et al., ISSTA 2024) | Spectrum-based fault localization combined with AST-guided LLM repair. | Focuses on localization and patch generation; does not verify semantic drift outside targeted methods. | I examine post-generation acceptance checks to filter suspect patches before merge. |
| **REFINE** (Wang et al., 2024) | Iterative patch refinement driven by failing test execution feedback. | Can overfit iteratively to the specific test cases used for feedback. | I explore multi-dimensional constraints (AST scope, contract invariance) independent of the test harness. |
| **PAFT** (Jiang et al., 2024) | Patch-aware fine-tuning of LLMs on commit diffs. | Improves syntactic diff structure but cannot guarantee runtime behavioral equivalence. | I evaluate post-hoc verification applicable to any black-box agent. |
| **SpecRover / SWE-ABS** | Synthesizes abstract behavioral specifications prior to patch authoring. | High LLM API cost and prompt latency for full formal specification recovery. | I focus on cheap, deterministic static rules (structural bounds, contract preservation) before invoking heavy test generation. |
| **Search-Based APR & Overfitting** (e.g., Zhao et al., GECCO 2024) | Explores patch space search and overfitting reduction in automated program repair. | Primarily evaluated on classic benchmarks (Defects4J); needs translation to repo-level LLM agents. | Connects foundational APR overfitting insights to LLM agent outputs on SWE-bench Verified. |

---

### 3. Preliminary Results (Pilot Study)

I evaluated static checks on patches from three agents (`OpenHands`, `LearnByInteract`, and `CodeStory`) on SWE-bench Verified:

- **On 77 manually validated instances** (22 incorrect, 4 non-incorrect, 51 uncertain): the scope check flagged 11 of 22 incorrect patches, but the set contains too few negatives to estimate false alarms reliably.
- **On 724 patches labelled divergent or non-divergent by PatchDiff's differential tests**: the composite static check flagged 47.3% of divergent patches (123/260) and 50.0% of non-divergent patches (232/464), which is **close to chance** (precision 34.6% vs. 35.9% base rate). In contrast, a developer-test regression baseline reached 63.5% precision at a 7.5% false alarm rate.
- **Granular Per-Rule Analysis:** Isolating individual static rules revealed that file-mention scope checks and scratch-file rules drove nearly all false alarms (FPR 32.3% and 28.2%, respectively). Syntactic rules (public signature mutation, error guard removal) showed high specificity (FPR ~1.0%) but low recall (<2%).
- **Commit Hygiene Observation:** I observed that 201 out of 724 patches (27.8%) accidentally leak temporary scratch reproduction scripts (`reproduce_error.py`, `test_edge_cases.py`) into their unified diffs (CodeStory: 85/258, OpenHands: 58/217, LearnByInteract: 58/249). However, this leakage occurs equally across divergent (26.9%) and non-divergent (28.2%) patches, indicating it is an artifact of agent working-tree hygiene rather than a predictor of functional correctness.
- **Execution Overhead:** Static checks evaluated at an average latency of **10.93 ms per patch**, confirming they are computationally negligible compared to test execution.

**Interpretation:** These results demonstrate that naive static rules cannot serve as a stand-alone rejection gate without causing unacceptable false rejections. However, their ultra-low computational cost makes them well-suited as **soft warnings** or early heuristic filters within a hybrid verification pipeline.

---

### 4. Proposed Master's Research Plan

My proposed research addresses the limitations revealed by the pilot study through three sequential objectives:

1. **Objective 1: Identifying High-Precision Oracle-Free Signals (Months 1–6)**  
   Systematically benchmark individual static and lightweight dynamic signals on a balanced dev/test split of SWE-bench Verified. Hand-label 40 resolved non-divergent patches to establish an accurate negative baseline. Measure which specific AST invariants carry predictive power beyond chance.
2. **Objective 2: Hybrid Static-Dynamic Gate Design (Months 7–14)**  
   Combine high-specificity static filters (e.g., signature mutation, guard deletion) with pre-existing test execution and targeted assertion synthesis, calibrating rejection thresholds to keep false alarm rates below 5%.
3. **Objective 3: Agent Integration & In-the-Loop Evaluation (Months 15–24)**  
   Deploy the calibrated gate inside an open-source agent repair loop (such as AutoSWE or Agentless). Compare the resolve rate, regression rate, and patch quality of agent runs with and without gate feedback.

---

### 5. Alignment with Prof. Jianjun Zhao's Laboratory

Prof. Jianjun Zhao's laboratory at Kyushu University has conducted rigorous research in software analysis, program repair, and patch evaluation (such as recent work on patch search spaces in GECCO 2024). 

My goal is to bring empirical discipline to the evaluation of LLM coding agents by bridging modern LLM benchmarks with classical program repair insights. Working under Prof. Zhao's mentorship will provide the rigorous academic foundation needed to develop sound, verifiable techniques for autonomous software engineering.

---

### 6. Limitations & Threats to Validity
- **Differential Divergence vs. Incorrectness:** Automated differential tests flag behavioral differences, but not all differences represent bugs; some are valid alternative implementations.
- **Label Scarcity:** Hand-labeled correctness ground truth is currently restricted to 77 instances; expanding this negative sample is essential to shrink confidence intervals.
- **Static Analysis Scope:** Python's dynamic typing and meta-programming limit the reach of pure AST pattern matching, reinforcing the need for lightweight dynamic hybrid checks.
