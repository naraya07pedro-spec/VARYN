"""17S-39: fixed OpenAI-compatible Chat Completions endpoints. NO redirects."""
import json
import urllib.request
import re

from varyn.providers import ProviderError, ModelReply

URLS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
    "9router": "http://127.0.0.1:20128/v1/chat/completions",
}
KEY_ENVS = {
    "openrouter": "OPENROUTER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "9router": "VARYN_9ROUTER_API_KEY",
}
MAX_BYTES = 131072
_MODEL_LABEL = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:/+-]{0,119}\Z")


def reported_model(raw):
    """Only a provider-CLAIMED model label, never authenticated upstream identity."""
    try:
        model = json.loads(raw).get("model")
        if (type(model) is str and _MODEL_LABEL.fullmatch(model) and
                ".." not in model and "//" not in model):
            return model
    except (ValueError, AttributeError, TypeError, UnicodeError):
        pass
    return None



def prepare(model, question, *, max_tokens):
    if (type(question) is not str or not question.startswith("SYNTHETIC:") or
            not 1 <= len(question) <= 4000 or type(max_tokens) is not int or
            not 16 <= max_tokens <= 2048):
        raise ValueError("Only bounded SYNTHETIC: input is permitted")
    return {
        "model": model, "stream": False, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": question}],
    }


def post(provider, payload, key, timeout):
    if provider not in URLS:
        raise ProviderError("Unsupported fixed provider")
    request = urllib.request.Request(
        URLS[provider], data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"},
    )
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    # Loopback should NEVER honor HTTPS_PROXY/HTTP_PROXY environment values.
    # On remote HTTPS API requests normal OS proxy configuration still applies.
    handlers = [NoRedirect]
    if provider == "9router":
        handlers.append(urllib.request.ProxyHandler({}))
    with urllib.request.build_opener(*handlers).open(
        request, timeout=timeout,
    ) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ProviderError("Oversized provider response")
    return body


def parse(provider, model, raw):
    try:
        if provider not in URLS or type(raw) is not bytes or len(raw) > MAX_BYTES:
            raise ValueError()
        result = json.loads(raw)
        choices = result["choices"]
        if type(choices) is not list or len(choices) != 1:
            raise ValueError()
        candidate = choices[0]
        message = candidate["message"]
        if candidate.get("finish_reason") != "stop" or message.get("tool_calls"):
            raise ValueError()
        text = message["content"]
        if type(text) is not str or not 1 <= len(text.strip()) <= 20000:
            raise ValueError()
        supplied = result.get("usage", {})
        supplied = supplied if type(supplied) is dict else {}
        usage = {}
        for key, native in (("input_tokens", "prompt_tokens"),
                            ("output_tokens", "completion_tokens")):
            count = supplied.get(native)
            if type(count) is int and 0 <= count <= 100000000:
                usage[key] = count
        return ModelReply(text.strip(), provider, model, usage)
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ProviderError("Invalid or incomplete provider response") from None
