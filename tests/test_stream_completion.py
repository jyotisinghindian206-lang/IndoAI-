import unittest

from indo_brain.completion import (
    configured_continuation_limit, finish_reason_name, is_length_finish_reason,
    trim_continuation_overlap, response_looks_truncated,
    should_continue_response, is_retryable_stream_error,
)


class StreamCompletionTests(unittest.TestCase):
    def test_openai_length_finish_reason(self):
        self.assertTrue(is_length_finish_reason("length"))
        self.assertFalse(is_length_finish_reason("stop"))

    def test_gemini_enum_finish_reason(self):
        class FinishReason:
            name = "MAX_TOKENS"
        self.assertEqual(finish_reason_name(FinishReason()), "MAX_TOKENS")
        self.assertTrue(is_length_finish_reason(FinishReason()))

    def test_continuation_limit_is_bounded(self):
        self.assertEqual(configured_continuation_limit("2"), 2)
        self.assertEqual(configured_continuation_limit("99"), 3)
        self.assertEqual(configured_continuation_limit("-5"), 0)
        self.assertEqual(configured_continuation_limit("bad"), 2)

    def test_exact_overlap_is_removed(self):
        previous = "The answer ends with this phrase"
        continuation = "with this phrase and continues correctly."
        self.assertEqual(trim_continuation_overlap(previous, continuation), " and continues correctly.")

    def test_short_exact_sentence_boundary_overlap(self):
        previous = "Gemini begins. "
        continuation = "Gemini begins. It now finishes."
        self.assertEqual(trim_continuation_overlap(previous, continuation), "It now finishes.")

    def test_word_overlap_with_punctuation_difference(self):
        previous = "We should preserve the existing table rows."
        continuation = "existing table rows, then add the final summary."
        self.assertEqual(trim_continuation_overlap(previous, continuation), ", then add the final summary.")

    def test_no_overlap_is_preserved(self):
        self.assertEqual(trim_continuation_overlap("Hello there", " A separate answer."), " A separate answer.")

    def test_detects_mid_sentence_endings(self):
        self.assertTrue(response_looks_truncated("The answer is incomplete because"))
        self.assertTrue(response_looks_truncated("A code example:\n```python\nprint('hi')"))
        self.assertFalse(response_looks_truncated("The answer is complete."))

    def test_explicit_limit_always_requests_continuation(self):
        self.assertTrue(should_continue_response("length", "A complete sentence."))
        self.assertTrue(should_continue_response("MAX_TOKENS", "Finished."))
        self.assertFalse(should_continue_response("stop", "Finished."))

    def test_retryable_network_errors_only(self):
        self.assertTrue(is_retryable_stream_error(TimeoutError("read timed out")))
        self.assertTrue(is_retryable_stream_error(ConnectionError("connection reset")))
        self.assertFalse(is_retryable_stream_error(RuntimeError("429 quota exceeded")))
        self.assertFalse(is_retryable_stream_error(RuntimeError("401 unauthorized")))


if __name__ == "__main__":
    unittest.main()
