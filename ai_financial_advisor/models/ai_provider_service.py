# -*- coding: utf-8 -*-
"""
AI Provider Service Module
Handles integration with multiple AI providers: Claude, ChatGPT, DeepSeek, Grok, and Gemini
"""

import json
import logging
import requests
from abc import ABC, abstractmethod
from datetime import datetime

_logger = logging.getLogger(__name__)


class AIProviderBase(ABC):
    """Abstract base class for all AI providers."""

    def __init__(self, api_key, model=None):
        self.api_key = api_key
        self.model = model or self.get_default_model()
        self.timeout = 90

    @abstractmethod
    def get_default_model(self):
        """Return the default model for this provider."""
        pass

    @abstractmethod
    def get_available_models(self):
        """Return list of available models."""
        pass

    @abstractmethod
    def call_api(self, prompt, max_tokens=4096):
        """
        Call the AI API with the given prompt.
        Returns: (success: bool, response: str, error: str or None)
        """
        pass

    @abstractmethod
    def validate_api_key(self):
        """Validate the API key."""
        pass


class ClaudeProvider(AIProviderBase):
    """Anthropic Claude API provider."""

    API_URL = 'https://api.anthropic.com/v1/messages'

    def get_default_model(self):
        return 'claude-sonnet-4-6'

    def get_available_models(self):
        # NOTE: Claude Sonnet 4 / Opus 4 (the original "4.0" releases) and the
        # entire Claude 3.x line (3.7 Sonnet, 3.5 Sonnet, 3.5 Haiku, 3 Sonnet,
        # 3 Haiku) have been formally retired by Anthropic and return hard
        # API errors — they are intentionally left out of this list so the
        # dropdown never offers a model id that is guaranteed to fail.
        return [
            ('claude-opus-4-8', 'Claude Opus 4.8 (Flagship — Most Capable)'),
            ('claude-opus-4-7', 'Claude Opus 4.7'),
            ('claude-opus-4-6', 'Claude Opus 4.6'),
            ('claude-opus-4-5', 'Claude Opus 4.5'),
            ('claude-opus-4-1', 'Claude Opus 4.1 (Deprecated — retiring Aug 5, 2026)'),
            ('claude-sonnet-4-6', 'Claude Sonnet 4.6 (Recommended — Balanced)'),
            ('claude-sonnet-4-5', 'Claude Sonnet 4.5'),
            ('claude-haiku-4-5-20251001', 'Claude Haiku 4.5 (Fastest)'),
        ]

    def call_api(self, prompt, max_tokens=4096):
        try:
            headers = {
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }

            payload = {
                'model': self.model,
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': prompt}],
            }

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            ai_text = data['content'][0]['text']

            return True, ai_text, None

        except requests.exceptions.Timeout:
            return False, '', 'Claude API request timed out after 90 seconds'
        except requests.exceptions.HTTPError as e:
            error = f'Claude API error: {e.response.status_code} - {e.response.text}'
            _logger.error(error)
            return False, '', error
        except requests.exceptions.RequestException as e:
            error = f'Failed to connect to Claude API: {str(e)}'
            _logger.error(error)
            return False, '', error
        except KeyError:
            return False, '', 'Invalid response format from Claude API'

    def validate_api_key(self):
        """Validate Claude API key by making a minimal API call."""
        try:
            headers = {
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }

            payload = {
                'model': self.model,
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}],
            }

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True, 'Claude API key is valid'
        except Exception as e:
            return False, f'Claude API key validation failed: {str(e)}'


class ChatGPTProvider(AIProviderBase):
    """OpenAI ChatGPT API provider."""

    API_URL = 'https://api.openai.com/v1/chat/completions'

    # GPT-5.x and o-series "reasoning" models use a stricter Chat Completions
    # parameter surface than gpt-4o/gpt-4-turbo: they reject any non-default
    # `temperature` with a 400 error ("Only the default (1) value is
    # supported") and require `max_completion_tokens` instead of the legacy
    # `max_tokens` ("Unsupported parameter: 'max_tokens' ... Use
    # 'max_completion_tokens' instead"). Without this check, every GPT-5.x
    # model below would fail on the very first call.
    REASONING_PREFIXES = ('gpt-5', 'o1', 'o3', 'o4')

    def _is_reasoning_model(self):
        model = (self.model or '').lower()
        return model.startswith(self.REASONING_PREFIXES)

    def get_default_model(self):
        return 'gpt-5.5'

    def get_available_models(self):
        # NOTE: gpt-4-turbo and gpt-3.5-turbo have been dropped — they are
        # long superseded (in price *and* quality) by gpt-5.4-nano/mini, and
        # OpenAI's retirement cadence makes them unreliable going forward.
        # gpt-4o is kept as a clearly-labelled legacy option: OpenAI removed
        # it from ChatGPT but has stated the base model "continues to be
        # available in the API" for now.
        return [
            ('gpt-5.5', 'GPT-5.5 (Default — Frontier)'),
            ('gpt-5.5-pro', 'GPT-5.5 Pro (Highest Reasoning)'),
            ('gpt-5.4', 'GPT-5.4'),
            ('gpt-5.4-mini', 'GPT-5.4 Mini (Cheaper & Faster)'),
            ('gpt-5.4-nano', 'GPT-5.4 Nano (Fastest & Cheapest)'),
            ('gpt-5.3-codex', 'GPT-5.3 Codex (Agentic Coding Specialist)'),
            ('gpt-4o', 'GPT-4o (Legacy)'),
        ]

    def call_api(self, prompt, max_tokens=4096):
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            payload = {
                'model': self.model,
                'messages': [{'role': 'user', 'content': prompt}],
            }
            if self._is_reasoning_model():
                payload['max_completion_tokens'] = max_tokens
            else:
                payload['max_tokens'] = max_tokens
                payload['temperature'] = 0.7

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            ai_text = data['choices'][0]['message']['content']

            return True, ai_text, None

        except requests.exceptions.Timeout:
            return False, '', 'ChatGPT API request timed out after 90 seconds'
        except requests.exceptions.HTTPError as e:
            error = f'ChatGPT API error: {e.response.status_code} - {e.response.text}'
            _logger.error(error)
            return False, '', error
        except requests.exceptions.RequestException as e:
            error = f'Failed to connect to ChatGPT API: {str(e)}'
            _logger.error(error)
            return False, '', error
        except (KeyError, IndexError):
            return False, '', 'Invalid response format from ChatGPT API'

    def validate_api_key(self):
        """Validate ChatGPT API key."""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            payload = {
                'model': self.model,
                'messages': [{'role': 'user', 'content': 'Hi'}],
            }
            if self._is_reasoning_model():
                payload['max_completion_tokens'] = 10
            else:
                payload['max_tokens'] = 10

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True, 'ChatGPT API key is valid'
        except Exception as e:
            return False, f'ChatGPT API key validation failed: {str(e)}'


class DeepSeekProvider(AIProviderBase):
    """DeepSeek API provider."""

    API_URL = 'https://api.deepseek.com/chat/completions'

    def get_default_model(self):
        return 'deepseek-v4-flash'

    def get_available_models(self):
        # deepseek-chat / deepseek-reasoner are rolling aliases (DeepSeek
        # silently upgrades what they point to over time) rather than
        # pinned snapshots — that's why there's no separate selectable
        # entry for "V3.2" or "R1"; they were never independently
        # addressable model ids on the hosted API, only these alias names.
        return [
            ('deepseek-v4-flash', 'DeepSeek V4 Flash (Recommended — Fast & Cheap)'),
            ('deepseek-v4-pro', 'DeepSeek V4 Pro (Most Capable)'),
            ('deepseek-chat', 'DeepSeek Chat (Legacy alias — sunsetting Jul 24, 2026)'),
            ('deepseek-reasoner', 'DeepSeek Reasoner (Legacy alias — sunsetting Jul 24, 2026)'),
            ('deepseek-coder', 'DeepSeek Coder (Legacy)'),
        ]

    def call_api(self, prompt, max_tokens=4096):
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            payload = {
                'model': self.model,
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
            }

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            ai_text = data['choices'][0]['message']['content']

            return True, ai_text, None

        except requests.exceptions.Timeout:
            return False, '', 'DeepSeek API request timed out after 90 seconds'
        except requests.exceptions.HTTPError as e:
            error = f'DeepSeek API error: {e.response.status_code} - {e.response.text}'
            _logger.error(error)
            return False, '', error
        except requests.exceptions.RequestException as e:
            error = f'Failed to connect to DeepSeek API: {str(e)}'
            _logger.error(error)
            return False, '', error
        except (KeyError, IndexError):
            return False, '', 'Invalid response format from DeepSeek API'

    def validate_api_key(self):
        """Validate DeepSeek API key."""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            payload = {
                'model': self.model,
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}],
            }

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True, 'DeepSeek API key is valid'
        except Exception as e:
            return False, f'DeepSeek API key validation failed: {str(e)}'


class GrokProvider(AIProviderBase):
    """X (Twitter) Grok API provider."""

    API_URL = 'https://api.x.ai/v1/chat/completions'

    def get_default_model(self):
        return 'grok-4.3'

    def get_available_models(self):
        # xAI is unusually lenient with old slugs: retired model ids are
        # not hard-deleted, they're silently redirected to grok-4.3 (billed
        # at grok-4.3 rates) instead of returning an error. That makes it
        # safe to keep the older names selectable for continuity even
        # though grok-4.3 is what actually answers the request.
        return [
            ('grok-4.3', 'Grok 4.3 (Default — Latest)'),
            ('grok-4.20', 'Grok 4.20'),
            ('grok-4', 'Grok 4 (Legacy — now served by Grok 4.3)'),
            ('grok-3', 'Grok 3 (Legacy — now served by Grok 4.3)'),
            ('grok-2', 'Grok 2 (Legacy — now served by Grok 4.3)'),
        ]

    def call_api(self, prompt, max_tokens=4096):
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            payload = {
                'model': self.model,
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
            }

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            ai_text = data['choices'][0]['message']['content']

            return True, ai_text, None

        except requests.exceptions.Timeout:
            return False, '', 'Grok API request timed out after 90 seconds'
        except requests.exceptions.HTTPError as e:
            error = f'Grok API error: {e.response.status_code} - {e.response.text}'
            _logger.error(error)
            return False, '', error
        except requests.exceptions.RequestException as e:
            error = f'Failed to connect to Grok API: {str(e)}'
            _logger.error(error)
            return False, '', error
        except (KeyError, IndexError):
            return False, '', 'Invalid response format from Grok API'

    def validate_api_key(self):
        """Validate Grok API key."""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }

            payload = {
                'model': self.model,
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}],
            }

            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True, 'Grok API key is valid'
        except Exception as e:
            return False, f'Grok API key validation failed: {str(e)}'


class GeminiProvider(AIProviderBase):
    """Google Gemini API provider (via REST)."""

    API_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/models'

    def get_default_model(self):
        return 'gemini-3.1-pro-preview'

    def get_available_models(self):
        # gemini-2.0-flash / gemini-2.0-flash-lite were shut down by Google
        # on June 1, 2026 (404 on every request), and the entire Gemini 1.5
        # line was shut down earlier still — both are intentionally left
        # out so the dropdown never offers a dead model id. "-preview"
        # entries can be swapped out with shorter notice than GA models,
        # which is why gemini-3.5-flash (GA, no "-preview" suffix) is the
        # recommended choice rather than the current default.
        return [
            ('gemini-3.5-flash', 'Gemini 3.5 Flash (Recommended — GA)'),
            ('gemini-3.5-pro-preview', 'Gemini 3.5 Pro (Preview — rolling out)'),
            ('gemini-3.1-pro-preview', 'Gemini 3.1 Pro Preview (Current Default)'),
            ('gemini-3.1-flash-lite', 'Gemini 3.1 Flash-Lite (Fast & Cheap)'),
            ('gemini-2.5-pro', 'Gemini 2.5 Pro'),
            ('gemini-2.5-flash', 'Gemini 2.5 Flash'),
            ('gemini-2.5-flash-lite', 'Gemini 2.5 Flash-Lite (Economical)'),
        ]

    def _get_api_url(self, endpoint='generateContent'):
        return f'{self.API_BASE_URL}/{self.model}:{endpoint}?key={self.api_key}'

    def call_api(self, prompt, max_tokens=4096):
        import re
        import time

        url = self._get_api_url('generateContent')

        payload = {
            'contents': [
                {
                    'parts': [{'text': prompt}],
                    'role': 'user',
                }
            ],
            'generationConfig': {
                'maxOutputTokens': max_tokens,
                'temperature': 0.7,
            },
        }

        max_retries = 3
        retry_delay = 16  # seconds — slightly above the typical 15 s Gemini retry window

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers={'Content-Type': 'application/json'},
                    json=payload,
                    timeout=self.timeout,
                )

                # ── 429 Rate-limit / Quota ─────────────────────────────
                if response.status_code == 429:
                    try:
                        err_data = response.json()
                        raw_msg  = err_data.get('error', {}).get('message', '')
                    except Exception:
                        raw_msg = response.text

                    # Try to parse "retry in X seconds" from the message
                    match = re.search(r'retry[^\d]*(\d+(?:\.\d+)?)\s*s', raw_msg, re.IGNORECASE)
                    wait = float(match.group(1)) + 1 if match else retry_delay

                    # Detect free-tier hard limit (limit: 0)  ← the user's exact case
                    free_tier_blocked = 'free_tier' in raw_msg and 'limit: 0' in raw_msg

                    if free_tier_blocked:
                        # No point retrying — quota is 0 on this key/project
                        user_msg = (
                            "Gemini API Error: Your Google Cloud project has a free-tier quota of 0 "
                            "for this model, which means billing is not yet enabled or the paid quota "
                            "has not been activated.\n\n"
                            "How to fix this:\n"
                            "1. Go to https://console.cloud.google.com/billing and confirm a billing "
                            "account is linked to your project.\n"
                            "2. Visit https://ai.dev/rate-limit to check your current quota.\n"
                            "3. If billing is already enabled, wait a few minutes for quota to "
                            "propagate, then retry.\n"
                            "4. Alternatively, switch to a different AI provider in Settings."
                        )
                        _logger.warning("Gemini free-tier quota=0 detected. Not retrying.")
                        return False, '', user_msg

                    if attempt < max_retries:
                        _logger.warning(
                            "Gemini 429 rate-limit (attempt %d/%d). Retrying in %.1fs …",
                            attempt, max_retries, wait,
                        )
                        time.sleep(wait)
                        continue

                    # All retries exhausted
                    return False, '', (
                        f"Gemini API rate limit exceeded after {max_retries} attempts. "
                        f"Please wait a moment and try again, or switch to another AI provider."
                    )

                response.raise_for_status()
                data = response.json()
                ai_text = data['candidates'][0]['content']['parts'][0]['text']
                return True, ai_text, None

            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    _logger.warning("Gemini timeout (attempt %d/%d). Retrying …", attempt, max_retries)
                    time.sleep(5)
                    continue
                return False, '', 'Gemini API request timed out after 90 seconds.'

            except requests.exceptions.HTTPError as e:
                try:
                    error_body = e.response.json().get('error', {}).get('message', e.response.text)
                except Exception:
                    error_body = e.response.text
                error = f'Gemini API error: {e.response.status_code} - {error_body}'
                _logger.error(error)
                return False, '', error

            except requests.exceptions.RequestException as e:
                error = f'Failed to connect to Gemini API: {str(e)}'
                _logger.error(error)
                return False, '', error

            except (KeyError, IndexError) as e:
                return False, '', f'Invalid response format from Gemini API: {str(e)}'

        return False, '', 'Gemini API call failed after all retries.'

    def validate_api_key(self):
        """Validate Gemini API key with a minimal call."""
        try:
            url = self._get_api_url('generateContent')

            payload = {
                'contents': [
                    {
                        'parts': [{'text': 'Hi'}],
                        'role': 'user',
                    }
                ],
                'generationConfig': {'maxOutputTokens': 10},
            }

            response = requests.post(
                url,
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True, 'Gemini API key is valid'
        except requests.exceptions.HTTPError as e:
            try:
                msg = e.response.json().get('error', {}).get('message', e.response.text)
            except Exception:
                msg = e.response.text
            return False, f'Gemini API key validation failed: {msg}'
        except Exception as e:
            return False, f'Gemini API key validation failed: {str(e)}'


class AIProviderFactory:
    """Factory class to create and manage AI providers."""

    PROVIDERS = {
        'claude': ClaudeProvider,
        'chatgpt': ChatGPTProvider,
        'deepseek': DeepSeekProvider,
        'grok': GrokProvider,
        'gemini': GeminiProvider,
    }

    @classmethod
    def get_provider(cls, provider_name, api_key, model=None):
        """
        Get an AI provider instance.

        Args:
            provider_name: 'claude', 'chatgpt', 'deepseek', 'grok', or 'gemini'
            api_key: API key for the provider
            model: Optional specific model to use

        Returns:
            AIProviderBase instance or None if provider not found
        """
        provider_class = cls.PROVIDERS.get(provider_name.lower())
        if not provider_class:
            _logger.error(f'Unknown AI provider: {provider_name}')
            return None

        return provider_class(api_key, model)

    @classmethod
    def get_available_providers(cls):
        """Return list of available provider names."""
        return list(cls.PROVIDERS.keys())

    @classmethod
    def get_provider_info(cls, provider_name):
        """Get information about a specific provider."""
        provider_class = cls.PROVIDERS.get(provider_name.lower())
        if not provider_class:
            return None

        instance = provider_class('')  # Dummy instance for introspection
        return {
            'name': provider_name,
            'default_model': instance.get_default_model(),
            'available_models': instance.get_available_models(),
        }