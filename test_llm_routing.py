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
        if "googleapis.com" in kwargs["base_url"]:
            provider_name = "gemini"
        elif "cloudflare.com" in kwargs["base_url"]:
            provider_name = "cloudflare_workers_ai"
        else:
            provider_name = "openrouter"
        return SimpleNamespace(
            chat=SimpleNamespace(
                completions=FakeCompletions(outcome, self.calls, provider_name)
            )
        )


def providers():
    return [
        LLMProvider("gemini", "gemini-3.5-flash", "https://generativelanguage.googleapis.com/v1beta/openai/", "g-key"),
        LLMProvider("cloudflare_workers_ai", "@cf/mistralai/mistral-small-3.1-24b-instruct", "https://api.cloudflare.com/client/v4/accounts/account-id/ai/v1", "c-key"),
        LLMProvider("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free", "https://openrouter.ai/api/v1", "o-key"),
        LLMProvider("openrouter", "nvidia/nemotron-3-super-120b-a12b:free", "https://openrouter.ai/api/v1", "o-key"),
    ]


class ProviderChainTests(unittest.TestCase):
    def test_configured_order_and_separate_credentials(self):
        env = {
            "GEMINI_API_KEY": "gemini-secret",
            "GEMINI_MODEL": "gemini-3.5-flash",
            "CLOUDFLARE_WORKERS_AI_API_KEY": "cloudflare-secret",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_WORKERS_AI_MODEL": "workers-model",
            "OPENROUTER_API_KEY": "openrouter-secret",
            "OPENROUTER_MODELS": "model-first,model-second",
        }
        with patch.dict(os.environ, env, clear=True):
            chain = openai_chatgpt.build_provider_chain()
        self.assertEqual(
            [(item.name, item.model) for item in chain],
            [
                ("gemini", "gemini-3.5-flash"),
                ("cloudflare_workers_ai", "workers-model"),
                ("openrouter", "model-first"),
                ("openrouter", "model-second"),
            ],
        )
        self.assertEqual(chain[0].api_key, "gemini-secret")
        self.assertEqual(chain[1].api_key, "cloudflare-secret")
        self.assertEqual([item.api_key for item in chain[2:]], ["openrouter-secret", "openrouter-secret"])
        self.assertEqual(
            chain[1].base_url,
            "https://api.cloudflare.com/client/v4/accounts/account-id/ai/v1",
        )
        self.assertEqual(len({item.base_url for item in chain}), 3)

    def test_gemini_success_stops_chain(self):
        factory = FakeFactory(["Is AI ready?"])
        result = openai_chatgpt.generate_with_provider_chain("prompt", providers(), factory)
        self.assertEqual(result, "Is AI ready?")
        self.assertEqual(factory.calls, [("gemini", "gemini-3.5-flash")])
        self.assertEqual(factory.client_kwargs[0]["max_retries"], 0)

    def test_gemini_retryable_failure_uses_cloudflare(self):
        factory = FakeFactory([FakeHTTPError(429), "Fallback title?"])
        result = openai_chatgpt.generate_with_provider_chain("prompt", providers(), factory)
        self.assertEqual(result, "Fallback title?")
        self.assertEqual(
            factory.calls,
            [("gemini", "gemini-3.5-flash"), ("cloudflare_workers_ai", "@cf/mistralai/mistral-small-3.1-24b-instruct")],
        )

    def test_cloudflare_retryable_failure_uses_ultra(self):
        factory = FakeFactory([FakeHTTPError(503), FakeHTTPError(429), "Second fallback?"])
        result = openai_chatgpt.generate_with_provider_chain("prompt", providers(), factory)
        self.assertEqual(result, "Second fallback?")
        self.assertEqual(
            factory.calls,
            [
                ("gemini", "gemini-3.5-flash"),
                ("cloudflare_workers_ai", "@cf/mistralai/mistral-small-3.1-24b-instruct"),
                ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
            ],
        )

    def test_ultra_retryable_failure_uses_super(self):
        factory = FakeFactory([
            FakeHTTPError(503), FakeHTTPError(403), FakeHTTPError(404), "Final fallback?"
        ])
        result = openai_chatgpt.generate_with_provider_chain("prompt", providers(), factory)
        self.assertEqual(result, "Final fallback?")
        self.assertEqual(
            factory.calls,
            [
                ("gemini", "gemini-3.5-flash"),
                ("cloudflare_workers_ai", "@cf/mistralai/mistral-small-3.1-24b-instruct"),
                ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
                ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free"),
            ],
        )

    def test_non_retryable_malformed_status_does_not_fallback(self):
        for status in (400, 422):
            with self.subTest(status=status):
                factory = FakeFactory([FakeHTTPError(status), "must not be used"])
                with self.assertRaises(FakeHTTPError):
                    openai_chatgpt.generate_with_provider_chain("bad request", providers(), factory)
                self.assertEqual(factory.calls, [("gemini", "gemini-3.5-flash")])

    def test_cloudflare_malformed_request_stops_chain(self):
        factory = FakeFactory([FakeHTTPError(429), FakeHTTPError(422), "must not be used"])
        with self.assertRaises(FakeHTTPError):
            openai_chatgpt.generate_with_provider_chain("bad request", providers(), factory)
        self.assertEqual(
            factory.calls,
            [("gemini", "gemini-3.5-flash"), ("cloudflare_workers_ai", "@cf/mistralai/mistral-small-3.1-24b-instruct")],
        )

    def test_auth_model_quota_and_network_errors_fall_through(self):
        class FakeNetworkError(Exception):
            pass

        FakeNetworkError.__module__ = "openai.test"
        for error in (FakeHTTPError(401), FakeHTTPError(403), FakeHTTPError(404), FakeHTTPError(429), FakeNetworkError("offline")):
            with self.subTest(error=error.__class__.__name__, status=getattr(error, "status_code", None)):
                factory = FakeFactory([error, "Fallback title?"])
                self.assertEqual(
                    openai_chatgpt.generate_with_provider_chain("prompt", providers(), factory),
                    "Fallback title?",
                )
                self.assertEqual(len(factory.calls), 2)


if __name__ == "__main__":
    unittest.main()
