# QA artifacts

Owner: **Juno** (with input from the story's co-owner). Test code lives under `e2e/` and each app's
own test dir; this folder holds QA *planning* artifacts.

| File | Story | Contents |
|---|---|---|
| `qa-matrix.md` | US-QA-D02 | QA matrix v0: personas (buyer, seller, support, admin), critical journeys, accessibility checks, and **RAGAS** metric targets/thresholds for the agent layer. `[REVIEW]`. |

> RAGAS thresholds set here become the acceptance bar for the agent eval suite (golden dataset starts
> US-QA-D05). Keep journeys named so E2E specs (US-QA-D03) can map 1:1 to them.
