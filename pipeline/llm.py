"""Provider-agnostic JSON completion.

Select the provider with LLM_PROVIDER = openrouter | anthropic | openai | gemini
and the model with LLM_MODEL. API keys are read from the provider's usual
environment variable (OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY,
GEMINI_API_KEY).
"""
import json
import os
import re
import time

PROVIDER = os.environ.get('LLM_PROVIDER', 'anthropic').lower()
DEFAULT_MODEL = {'openrouter': 'deepseek/deepseek-v4-flash-0731', 'anthropic': 'claude-opus-5'}  # openai/gemini: set LLM_MODEL


def model_name():
    m = os.environ.get('LLM_MODEL') or DEFAULT_MODEL.get(PROVIDER)
    if not m:
        raise SystemExit(f'Set LLM_MODEL for provider {PROVIDER!r}')
    return m


def _anthropic(system, user, schema):
    import anthropic
    client = anthropic.Anthropic()
    for attempt in range(5):
        try:
            resp = client.beta.messages.create(
                model=model_name(),
                max_tokens=16000,
                system=system,
                messages=[{'role': 'user', 'content': user}],
                output_config={'effort': os.environ.get('LLM_EFFORT', 'low'),
                               'format': {'type': 'json_schema', 'schema': schema}},
                betas=['server-side-fallback-2026-07-01'],
                fallbacks='default',
            )
            break
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError):
            if attempt == 4:
                raise
            time.sleep(2 ** attempt * 5)
    if resp.stop_reason == 'refusal':
        raise RuntimeError('model declined the request')
    if resp.stop_reason == 'max_tokens':
        raise RuntimeError('output truncated (max_tokens); use a smaller batch')
    return next(b.text for b in resp.content if b.type == 'text')


def _openai(system, user, schema):
    from openai import OpenAI
    resp = OpenAI().chat.completions.create(
        model=model_name(),
        messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        response_format={'type': 'json_object'},
    )
    return resp.choices[0].message.content


def _openrouter(system, user, schema):
    """OpenRouter exposes an OpenAI-compatible API; LLM_MODEL is an OpenRouter model id."""
    from openai import OpenAI, APIConnectionError, APIStatusError, RateLimitError
    client = OpenAI(base_url='https://openrouter.ai/api/v1', api_key=os.environ['OPENROUTER_API_KEY'],
                    default_headers={'X-Title': 'PEM Archive'},
                    timeout=float(os.environ.get('LLM_TIMEOUT', '120')), max_retries=0)
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model_name(),
                messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                response_format={'type': 'json_object'},
                temperature=0,
                max_tokens=16000,
            )
            if not resp.choices:
                raise RuntimeError('empty response')
            return resp.choices[0].message.content or ''
        except (RateLimitError, APIConnectionError, RuntimeError) as e:  # APITimeoutError is an APIConnectionError
            print(f'  openrouter attempt {attempt + 1}: {type(e).__name__}', flush=True)
        except APIStatusError as e:
            if e.status_code < 500:
                raise
        if attempt == 2:
            raise RuntimeError('OpenRouter request failed after 3 attempts')
        time.sleep(2 ** attempt * 5)


def _gemini(system, user, schema):
    from google import genai
    resp = genai.Client().models.generate_content(
        model=model_name(),
        contents=user,
        config={'system_instruction': system, 'response_mime_type': 'application/json'},
    )
    return resp.text


def parse_json(text):
    """Parse a JSON object, tolerating code fences or prose around it (common with small models)."""
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}')
        if start < 0 or end <= start:
            raise
        return json.loads(text[start:end + 1])


def complete_json(system, user, schema):
    fn = {'openrouter': _openrouter, 'anthropic': _anthropic, 'openai': _openai, 'gemini': _gemini}[PROVIDER]
    return parse_json(fn(system, user, schema))
