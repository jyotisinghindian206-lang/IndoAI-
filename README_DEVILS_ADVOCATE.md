# Devil's Advocate Mode

Devil's Advocate is an opt-in critical-thinking mode. It is enabled when the user selects a mode named `Devil's Advocate`, `Devils Advocate`, `Challenge`, `Critical Review`, or `Red Team`, or explicitly asks in the current message to challenge/stress-test an idea.

When enabled, Indo identifies assumptions, presents the strongest reasonable counterargument, checks evidence and feasibility, distinguishes facts from inference/speculation, and gives a balanced verdict with a practical improvement or test. It does not disagree automatically, invent evidence, call external tools, or save personal information. The feature adds prompt guidance to the existing `build_prompt` flow and does not alter provider routing or streaming.

Module: `indo_devil_advocate.py`

Validation: `pytest -q` (82 passed; 6 existing FastAPI `on_event` deprecation warnings).
