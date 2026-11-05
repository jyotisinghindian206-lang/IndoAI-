"""User-editable prompt presets with safe variable interpolation."""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Mapping

_NAME = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
_VAR = re.compile(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}")

@dataclass(frozen=True)
class PromptPreset:
    name: str
    title: str
    template: str
    description: str = ""
    max_output_chars: int = 50_000

    def render(self, values: Mapping[str, object] | None = None) -> str:
        supplied = {str(k): str(v) for k, v in (values or {}).items()}
        required = set(_VAR.findall(self.template))
        missing = sorted(required - supplied.keys())
        if missing:
            raise ValueError("Missing template values: " + ", ".join(missing))
        result = self.template.format_map(_SafeMap(supplied))
        if len(result) > self.max_output_chars:
            raise ValueError("Rendered prompt exceeds configured character limit")
        return result

class _SafeMap(dict):
    def __missing__(self, key: str) -> str:
        raise ValueError(f"Unknown template variable: {key}")

class PromptLibrary:
    def __init__(self, presets: list[PromptPreset] | None = None):
        self._presets: dict[str, PromptPreset] = {}
        for preset in presets or self._defaults():
            self.add(preset)

    @staticmethod
    def _defaults() -> list[PromptPreset]:
        return [
            PromptPreset("study_explain", "Explain a topic",
                "Explain {topic} for a {level} student. Use simple language, examples, and a short recap.",
                "Age-appropriate, step-by-step learning."),
            PromptPreset("study_quiz", "Create a quiz",
                "Create {count} questions about {topic} for a {level} student. Mix recall and reasoning. Put answers in a separate answer key.",
                "Practice without immediately revealing answers."),
            PromptPreset("research_brief", "Research brief",
                "Prepare a balanced research brief on {topic}. Separate established facts, uncertainty, and questions to verify.",
                "Structured research notes."),
            PromptPreset("code_review", "Review code",
                "Review this code for correctness, security, maintainability, and performance. Explain findings and propose minimal fixes:\n{code}",
                "Practical code review."),
            PromptPreset("writing_polish", "Polish writing",
                "Improve clarity and flow while preserving the author's meaning and voice. Text:\n{text}",
                "Editing, not replacing the author's intent."),
            PromptPreset("plan_steps", "Break down a goal",
                "Turn this goal into small, measurable, safe steps with checkpoints and a realistic schedule: {goal}",
                "Action planning."),
        ]

    def add(self, preset: PromptPreset, replace: bool = False) -> None:
        name = preset.name.strip().lower()
        if not _NAME.fullmatch(name):
            raise ValueError("Preset names must be 2–48 lowercase letters, digits, '_' or '-'.")
        if name in self._presets and not replace:
            raise ValueError("A preset with this name already exists.")
        if len(preset.template) > 20_000:
            raise ValueError("Preset template is too long.")
        self._presets[name] = PromptPreset(name, preset.title[:100], preset.template,
                                           preset.description[:500], preset.max_output_chars)

    def get(self, name: str) -> PromptPreset:
        try:
            return self._presets[name.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"Unknown prompt preset: {name}") from exc

    def remove(self, name: str) -> bool:
        name = name.strip().lower()
        if name not in self._presets:
            return False
        del self._presets[name]
        return True

    def list(self) -> list[dict[str, str]]:
        return [{"name": p.name, "title": p.title, "description": p.description}
                for p in sorted(self._presets.values(), key=lambda p: p.title.lower())]

    def render(self, name: str, values: Mapping[str, object] | None = None) -> str:
        return self.get(name).render(values)
