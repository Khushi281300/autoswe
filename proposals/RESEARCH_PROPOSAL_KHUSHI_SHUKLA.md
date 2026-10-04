# Research Proposal
## Mitigating Test Overfitting in Autonomous Software Engineering Agents via Oracle-Free Verification Gates

**Applicant:** Khushi Shukla  
**Prospective Degree:** Postgraduate Research Student / Master's Program  
**Target Lab:** Software Engineering Laboratory, Graduate School of Information Science and Electrical Engineering (ISEE), Kyushu University  
**Prospective Supervisor:** Prof. Jianjun Zhao  
**Date:** October 2026  

---

### 1. Introduction & Research Problem

Recent breakthroughs in Large Language Models (LLMs) and multi-agent scaffolding (such as SWE-agent, OpenHands, and CodeStory) have driven rapid progress on automated issue resolution benchmarks like SWE-bench. On these benchmarks, an AI-generated patch is considered "resolved" if it passes the repository's pre-existing regression tests and issue-reproducing unit tests ($T_{\text{fail} \to \text{pass}} \land T_{\text{pass} \to \text{pass}}$).

However, real-world software test suites are inherently sparse and incomplete. Consequently, LLM issue-resolving agents frequently suffer from **test overfitting**—producing patches that satisfy existing test assertions but silently introduce semantic regressions, mutate public API signatures, delete validation guards, or swallow exceptions. Recent differential testing studies (such as PatchDiff) reveal that over 30% of benchmark-resolved patches behaviorally diverge from developer specifications.

Existing techniques for detecting patch divergence rely heavily on **post-hoc differential testing against human developer reference patches (the Oracle)** or expensive test generation inside multi-gigabyte Docker environments. In a realistic deployment setting, however, **no developer oracle exists**. 

**Primary Research Question:**  
*Can oracle-free verification gates, operating solely on generation-time information (the user issue description, the pre-patch AST, and the candidate diff), effectively detect and reject overfitted patches without suppressing genuine fixes?*

---

### 2. Proposed Methodology

We propose a multi-stage, lightweight verification architecture that acts as an automated acceptance gate during the agentic repair loop:

```
[Candidate Patch Diff] 
          │
          ▼
   ┌───────────────┐
   │ PatchSanitizer│ ──► Prunes accidental scratch test scripts (e.g., reproduce.py)
   └──────┬────────┘
          │
          ▼
   ┌───────────────┐
   │ ScopeChecker  │ ──► Enforces AST-level hunk bounds, issue lexical alignment,
   └──────┬────────┘     and non-test/code file constraints
          │
          ▼
   ┌─────────────────┐
   │ BehaviorChecker │ ──► Prevents public API signature drift, exception swallowing,
   └──────┬──────────┘     and hardcoded test literal return cheats
          │
          ▼
[Accept / Reject with Diagnostic Feedback to LLM Loop]
```

1. **Automated Scratch Sanitization:** Dynamically prunes untracked scratch reproduction scripts generated during agent chain-of-thought verification before bundling the pull request.
2. **Oracle-Free AST Scope Checking:** Uses Tree-Sitter AST parsing and lexical extraction from issue problem statements to ensure the patch does not modify files or functions alien to the reported defect.
3. **Behavioral Contract Invariance:** Syntactically checks for semantic cheating patterns, including silent exception suppression (`except Exception: pass`), deletion of error guards (`raise ValueError`), and backward-incompatible public signature mutations.

---

### 3. Preliminary Empirical Results (Pilot Study)

To validate the feasibility of this approach, we conducted an empirical pilot evaluation on **SWE-bench Verified** using candidate patches from three state-of-the-art agents (`OpenHands`, `LearnByInteract`, and `CodeStory`) and ground-truth divergence labels from the PatchDiff dataset.

#### Summary of Key Findings:
- **50.0% Detection Rate on Confirmed Overfitted Fixes:** On the 22 human-verified incorrect patches, our oracle-free gate successfully caught **11 out of 22 (50.0% Recall)** with **91.67% Precision** (95% CI: `[64.6%, 98.5%]`).
- **5.5x Superiority Over Traditional Heuristics:** A conventional patch size baseline (>100 lines churn) only caught **9.09% (2/22)** of overfitted patches.
- **Instantaneous Execution:** Unlike differential test execution requiring hours of Docker runtime, our gate executes statically in **under 0.15 seconds per patch**.
- **Discovery of Scratch Script Pollution:** Evaluated across 724 candidate patches, we discovered that over **150 patches** from state-of-the-art tools inadvertently commit temporary test scripts (`reproduce_error.py`, `test_edge_cases.py`) into their final diffs, demonstrating a widespread flaw in current agent commit hygiene.

---

### 4. Proposed Research Plan & Master's Thesis Objectives

During my graduate studies under Prof. Jianjun Zhao's supervision, I plan to expand this pilot into a comprehensive framework:

1. **Phase 1: In-the-Loop Agent Repair Integration:**  
   Integrate the composite gate into an open-source autonomous agent (e.g., AutoSWE / Agentless). When a gate rejects a patch, provide structured diagnostic feedback directly to the LLM context to guide self-correction.
2. **Phase 2: Contract-Driven Invariant Synthesis:**  
   Investigate lightweight dynamic contracts (pre/post-conditions) extracted automatically from existing docstrings and typing annotations.
3. **Phase 3: Large-Scale Benchmark Evaluation:**  
   Evaluate across diverse language ecosystems (Python, Java via Defects4J) and submit findings to top software engineering conferences (ICSE / FSE / ASE / ISSTA).

---

### 5. Why Prof. Jianjun Zhao's Laboratory at Kyushu University?

Prof. Jianjun Zhao's laboratory is globally recognized for its foundational and pioneering work in program analysis, automated program repair (APR), and software testing rigor (including recent publications at GECCO, ISSTA, and ICSE). My research interest lies at the intersection of modern LLM-driven coding agents and classical program analysis. 

Prof. Zhao's deep expertise in patch validation, search-based software engineering, and software analysis provides the ideal academic environment for me to develop rigorous, publication-grade solutions to the critical problem of test overfitting in autonomous software engineering.
