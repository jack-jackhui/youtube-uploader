import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import openai_chatgpt
from openai_chatgpt import LLMProvider


class FakeHTTPError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class FakeCompletions:
    def __init__(self, outcome, calls, provider_name):
        self.outcome = outcome
        self.calls = calls
        self.provider_name = provider_name

    def create(self, **kwargs):
        self.calls.append((self.provider_name, kwargs["model"]))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.outcome))]
        )


class FakeFactory:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.client_kwargs = []

    def __call__(self, **kwargs):
        self.client_kwargs.append(kwargs)
        outcome = self.outcomes.pop(0)
        provider_name = "gemini" if "googleapis.com" in kwargs["base_url"] else "openrouter"
        return SimpleNamespace(
            chat=SimpleNamespace(
                completions=FakeCompletions(outcome, self.calls, provider_name)
            )
        )


def providers():
    return [
        LLMProvider("gemini", "gemini-3.5-flash", "https://generativelanguage.googleapis.com/v1beta/openai/", "g-key"),
        LLMProvider("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free", "https://openrouter.ai/api/v1", "o-key"),
        LLMProvider("openrouter", "nvidia/nemotron-3-super-120b-a12b:free", "https://openrouter.ai/api/v1", "o-key"),
    ]


class ProviderChainTests(unittest.TestCase):
    def test_configured_order_and_separate_credentials(self):
        env = {
            "GEMINI_API_KEY": "gemini-secret",
            "GEMINI_MODEL": "gemini-3.5-flash",
            "OPENROUTER_API_KEY": "openrouter-secret",
            "OPENROUTER_MODELS": "model-first,model-second",
        }
        with patch.dict(os.environ, env, clear=True):
            chain = openai_chatgpt.build_provider_chain()
        self.assertEqual(
            [(item.name, item.model) for item in chain],
            [("gemini", "gemini-3.5-flash"), ("openrouter", "model-first"), ("openrouter", "model-second")],
        )
        self.assertEqual(chain[0].api_key, "gemini-secret")
        self.assertEqual([item.api_key for item in chain[1:]], ["openrouter-secret", "openrouter-secret"])
        self.assertNotEqual(chain[0].base_url, chain[1].base_url)

    def test_gemini_success_stops_chain(self):
        factory = FakeFactory(["Is AI ready?"])
        result = openai_chatgpt.generate_with_provider_chain("prompt", providers(), factory)
        self.assertEqual(result, "Is AI ready?")
        self.assertEqual(factory.calls, [("gemini", "gemini-3.5-flash")])
        self.assertEqual(factory.client_kwargs[0]["max_retries"], 0)

    def test_gemini_retryable_failure_uses_first_openrouter(self):
        factory = FakeFactory([FakeHTTPError(429), "Fallback title?"])
        result = openai_chatgpt.generate_with_provider_chain("prompt", providers(), factory)
        self.assertEqual(result, "Fallback title?")
        self.assertEqual(
            factory.calls,
            [("gemini", "gemini-3.5-flash"), ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free")],
        )

    def test_first_fallback_failure_uses_second_fallback(self):
        factory = FakeFactory([FakeHTTPError(503), FakeHTTPError(429), "Second fallback?"])
        result = openai_chatgpt.generate_with_provider_chain("prompt", providers(), factory)
        self.assertEqual(result, "Second fallback?")
        self.assertEqual(
            factory.calls,
            [
                ("gemini", "gemini-3.5-flash"),
                ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
                ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free"),
            ],
        )

    def test_non_retryable_400_does_not_fallback(self):
        factory = FakeFactory([FakeHTTPError(400), "must not be used"])
        with self.assertRaises(FakeHTTPError):
            openai_chatgpt.generate_with_provider_chain("bad request", providers(), factory)
        self.assertEqual(factory.calls, [("gemini", "gemini-3.5-flash")])


if __name__ == "__main__":
    unittest.main()
