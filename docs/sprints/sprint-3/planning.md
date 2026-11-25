# Sprint 3 Planning — draft

Owner: Hamza. Updated 16 November 2026 from [Issue #61](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/61), merged contract PR [#63](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/63), and open PR reviews. **Team decision of 18 November: the A2A architecture (contract v1.3) is adopted; the test-repository implementation was merged on branch `feature/S3-arch-a2a-adoption` (264 tests passing), and Sprint 3 closes on 19 November with the per-owner adoption review recorded in [report.md](report.md).**

## Goal and acceptance

Generate an application from a real requirement using the fixed template. The app must
start and perform one or two basic operations. The team checks requirement → decompose
→ assign → worker generation → running application, with evidence from each PC as
requested by #61. The issue says Sprint 2 closing gaps must be resolved before Sprint 3
is declared complete.

## Work and dependencies

| Owner | Work | Evidence / dependency |
| --- | --- | --- |
| Okan | Maintain contract v1.2; decide malformed model response fallback and generated-app launch configuration with the owners. | #63 merged; resolve open contract decisions. |
| Baran + Can | Master decomposition, template copy, inputs, persistence and backend review. | [#64](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/64) open; address its review, then integrated tests. |
| Eray | Coordinate template ownership; worker writes the correct file, validates output and handles unavailable dependency inputs. | [#65](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/65) open, based on #64 branch; fix [#68](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/68). |
| Fatma + Eray | Plain HTML/JavaScript template frontend connected to the generated backend; coordinate changes in `templates/` with its owner Eray. | Demonstrate real create/list operations. |
| Abdurrahman | Real platform CI and smoke, then generated-app smoke mode. | [#27](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/27); `GENERATED APP OK` only on successful basic operations. |
| Everyone | Run a worker and a real generated project on their PC; report reproducible failures and evidence. | #61 acceptance; two-worker integration proof also needed for Sprint 2. |
| Hamza | Maintain plan, status, report and coordinate demo. | Record evidence, owners and remaining blockers; team confirms schedule. |

## Demo checklist

1. Agree the exact sample requirement, master PC, participants and scheduled time.
2. Start the master and workers with their own settings; never publish tokens or `.env`.
3. Create the project, decompose and assign; confirm dependencies complete in order.
4. Generate the files, run the generated application and exercise basic operations.
5. Record commands, test/smoke output, screenshots or logs, failures and follow-up owners.

The Sprint 2 retrospective has not yet confirmed its single improvement; the proposal
in the Sprint 2 report remains pending team agreement.
