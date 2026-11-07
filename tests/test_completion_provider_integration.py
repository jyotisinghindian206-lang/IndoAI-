import json
import unittest
from unittest.mock import patch

import indo


class FakeResponse:
    def __init__(self, events):
        self.events = list(events)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def __iter__(self):
        for event in self.events:
            if isinstance(event, BaseException):
                raise event
            yield ("data: " + json.dumps(event) + "\n\n").encode("utf-8")
        yield b"data: [DONE]\n\n"


def chunk(text=None, finish=None):
    choice = {"delta": {"content": text} if text is not None else {}}
    if finish is not None:
        choice["finish_reason"] = finish
    return {"choices": [choice]}


class OpenAICompletionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict("os.environ", {"INDO_MAX_CONTINUATIONS": "2"})
        self.env.start()
        self.key = patch.object(indo, "OPENAI_API_KEY", "test-key")
        self.key.start()

    def tearDown(self):
        self.key.stop()
        self.env.stop()

    def test_token_limit_continues_and_joins(self):
        responses = [
            FakeResponse([chunk("The answer stops mid", None), chunk(finish="length")]),
            FakeResponse([chunk("mid-sentence and finishes.", None), chunk(finish="stop")]),
        ]
        with patch.object(indo, "_post_json", side_effect=responses):
            result = "".join(indo._openai_stream("test prompt"))
        self.assertEqual(result, "The answer stops mid-sentence and finishes.")

    def test_mid_sentence_stop_gets_one_soft_continuation(self):
        responses = [
            FakeResponse([chunk("The answer is incomplete because", None), chunk(finish="stop")]),
            FakeResponse([chunk("the second segment completes it.", None), chunk(finish="stop")]),
        ]
        with patch.object(indo, "_post_json", side_effect=responses):
            result = "".join(indo._openai_stream("test prompt"))
        self.assertEqual(result, "The answer is incomplete because the second segment completes it.")


    def test_does_not_claim_completion_when_soft_continuation_still_looks_cut(self):
        responses = [
            FakeResponse([chunk("The answer stops because", None), chunk(finish="stop")]),
            FakeResponse([chunk("the answer still ends with and", None), chunk(finish="stop")]),
        ]
        with patch.object(indo, "_post_json", side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, "still appears unfinished"):
                "".join(indo._openai_stream("test prompt"))

    def test_transient_read_error_recovers_from_partial_text(self):
        responses = [
            FakeResponse([chunk("Partial answer because", None), TimeoutError("read timed out")]),
            FakeResponse([chunk("the stream resumed.", None), chunk(finish="stop")]),
        ]
        with patch.object(indo, "_post_json", side_effect=responses):
            result = "".join(indo._openai_stream("test prompt"))
        self.assertEqual(result, "Partial answer because the stream resumed.")


class FakeGeminiTypes:
    class GenerateContentConfig:
        def __init__(self, **kwargs): self.kwargs = kwargs
    class Part:
        def __init__(self, text=None): self.text = text
        @classmethod
        def from_bytes(cls, data, mime_type): return cls(text="attachment")
    class Content:
        def __init__(self, role=None, parts=None): self.role, self.parts = role, parts


class FakeGeminiModels:
    def __init__(self, responses): self.responses = list(responses); self.calls = 0
    def generate_content_stream(self, **kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        for item in response:
            if isinstance(item, BaseException): raise item
            yield item


class GeminiCompletionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict("os.environ", {"INDO_MAX_CONTINUATIONS": "2", "INDO_FALLBACK_MODELS": ""})
        self.env.start()
        self.patches = [
            patch.object(indo, "genai", object()),
            patch.object(indo, "types", FakeGeminiTypes),
            patch.object(indo, "API_KEYS", ["test-key"]),
            patch.object(indo, "MODEL", "test-model"),
        ]
        for item in self.patches: item.start()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.env.stop()

    @staticmethod
    def response(text, finish):
        candidate = type("Candidate", (), {"finish_reason": finish})()
        return type("Chunk", (), {"text": text, "candidates": [candidate]})()

    def run_fake(self, responses):
        models = FakeGeminiModels(responses)
        client = type("Client", (), {"models": models})()
        with patch.object(indo, "_get_cached_gemini_client", return_value=client):
            answer = "".join(indo._gemini_stream("test prompt"))
        return answer, models.calls

    def test_gemini_max_tokens_continues(self):
        answer, calls = self.run_fake([
            [self.response("Gemini answer starts", "MAX_TOKENS")],
            [self.response(" and then finishes.", "STOP")],
        ])
        self.assertEqual(answer, "Gemini answer starts and then finishes.")
        self.assertEqual(calls, 2)

    def test_gemini_mid_sentence_stop_continues(self):
        answer, calls = self.run_fake([
            [self.response("This answer stops because", "STOP")],
            [self.response(" it was incomplete.", "STOP")],
        ])
        self.assertEqual(answer, "This answer stops because it was incomplete.")
        self.assertEqual(calls, 2)

    def test_gemini_transient_stream_failure_recovers(self):
        answer, calls = self.run_fake([
            [self.response("The network interrupted because", None), TimeoutError("read timed out")],
            [self.response(" the retry completed it.", "STOP")],
        ])
        self.assertEqual(answer, "The network interrupted because the retry completed it.")
        self.assertEqual(calls, 2)

    def test_gemini_does_not_silently_accept_still_incomplete_tail(self):
        models = FakeGeminiModels([
            [self.response("This ends because", "STOP")],
            [self.response("the answer still ends with and", "STOP")],
        ])
        client = type("Client", (), {"models": models})()
        with patch.object(indo, "_get_cached_gemini_client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "still appears unfinished"):
                "".join(indo._gemini_stream("test prompt"))


if __name__ == "__main__":
    unittest.main()
