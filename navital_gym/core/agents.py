"""Model agents for the baseline runner. Standard library only (urllib). Two wire formats:
  OpenAI-compatible /chat/completions (Ollama, vLLM, LM Studio, OpenAI, Groq, OpenRouter, Gemini's OpenAI endpoint)
  Anthropic /v1/messages
One tool loop (ToolChatAgent) sits on top, with the harness protections that stop a format problem being mistaken for lack of task skill:
  - after the tool loop, if the final message has no readable submission (or the env's format_check rejects it), ONE repair retry is made:
    "Your answer did not parse: <error>. Reply now with ONLY the corrected JSON object", tool-free and in JSON mode where the provider has it;
  - running out of turns still gets a forced final answer (tool-free) instead of a blank, and is reported separately (turns_exhausted);
  - provider errors are retried with backoff (429 / 5xx) and, if they persist, reported as `error`, not as a wrong answer.
Every run records meta {repaired, turns, turns_exhausted, error}; the report keeps a strict (no-repair) column next to the headline."""
from __future__ import annotations
import json, os, time, urllib.request, urllib.error
from typing import Any, Callable

def _objects(text: str, strings: bool):
    """(start, end, obj) for each top-level {...} span that parses. strings=True does not count braces inside JSON strings."""
    depth, start, in_str, esc = 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
        elif ch == '"' and depth and strings:
            in_str = True
        elif ch == "{":
            if depth == 0: start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                try: yield start, i, json.loads(text[start:i + 1])
                except (ValueError, RecursionError): pass

def extract_json(text: str) -> Any:
    """The last top-level JSON object in a model message (models wrap it in prose or ``` fences).
    v1.1: braces are counted both plainly and string-aware (a "}" inside a string must not split the object; a stray quote in prose must not
    swallow the answer); the object that ends last wins, the outermost one on a tie."""
    text = text or ""
    found = list(_objects(text, False)) + list(_objects(text, True))
    return max(found, key=lambda c: (c[1], -c[0]))[2] if found else None

REPAIR = ("Your answer did not parse: {err}. Reply now with ONLY the corrected final answer as one JSON object in the required format, "
          "and nothing else. Do not call any tools.")
FINAL = "You have used all your tool calls. Reply now with ONLY your final answer as one JSON object in the required format, and nothing else."

import re as _re
_KEY_ENV_RE = _re.compile(r"(API_KEY|TOKEN|SECRET|ACCOUNT_ID)$")      # the Cloudflare account id is not a credential but is scrubbed from saved files too
_KEY_SHAPES = _re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|gsk_[A-Za-z0-9]{8,}|AIza[0-9A-Za-z_\-]{8,}|AQ\.[0-9A-Za-z_\-]{8,}|hf_[A-Za-z0-9]{8,}|Bearer\s+[A-Za-z0-9_\-\.]{12,})")

def redact(text) -> str:
    """Scrub anything that looks like a credential, and every secret value present in this process's environment, from text that may be
    printed, logged or saved (provider errors, transcripts, settings). Applied wherever the runner writes model or provider text."""
    t = str(text)
    for k, v in os.environ.items():
        if _KEY_ENV_RE.search(k) and len(v) >= 8:
            t = t.replace(v, "***")
    return _KEY_SHAPES.sub("***", t)

class ProviderError(Exception):
    def __init__(self, msg, body=""):
        super().__init__(redact(msg))
        self.body = redact(body)

class QuotaExhausted(ProviderError):
    """A DAILY free-tier allowance is used up (Groq TPD/RPD, Gemini PerDay, Cloudflare daily neurons). Retrying today is pointless: the run stops and is resumed after the reset."""
    wait = None      # seconds the provider said to wait, when it said

_DAILY = _re.compile(r"per day|\bTPD\b|\bRPD\b|PerDay|daily free allocation|daily (?:quota|limit|allowance)", _re.I)
_WAIT = _re.compile(r"try again in\s+(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:([\d.]+)s)?", _re.I)

def _daily_quota_wait(raw: str):
    """(True, seconds-or-None) when a 429 body says the DAILY allowance is gone; (False, None) for an ordinary per-minute limit."""
    if not _DAILY.search(raw or ""):
        return False, None
    m = _WAIT.search(raw or "")
    secs = (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3) or 0)) if m and any(m.groups()) else None
    return True, secs

def _error_text(body: str) -> str:
    """The provider's own error message (JSON error.message when there is one), whitespace-collapsed and cut to 300 characters."""
    msg = body
    try:
        j = json.loads(body)
        j = j[0] if isinstance(j, list) and j else j
        err = j.get("error", j) if isinstance(j, dict) else j
        if isinstance(err, dict):
            msg = str(err.get("message") or err.get("detail") or err)
        else:
            msg = str(err)
    except ValueError:
        pass
    return _re.sub(r"\s+", " ", msg)[:300]

def _post(url: str, headers: dict, body: dict, timeout: int, retries: int = 6) -> dict:
    data = json.dumps(body).encode()
    headers = {"User-Agent": "navital-gym/0.1 (+https://github.com/Navitallabs/navital-gym)", **headers}   # some providers' CDNs (Groq) block urllib's default agent with a 403 "1010"
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            daily, secs = _daily_quota_wait(raw) if e.code == 429 else (False, None)
            if daily:                       # the daily allowance is gone: retrying today only burns calls, so stop at once
                q = QuotaExhausted(f"HTTP 429: daily quota used up: {_error_text(raw)}", raw); q.wait = secs
                raise q
            if e.code in (408, 409, 429, 500, 502, 503, 504, 529) and attempt < retries:
                wait = e.headers.get("Retry-After")
                time.sleep(min(float(wait), 60) if wait and wait.replace(".", "").isdigit() else min(2 ** attempt * 2, 60))
                continue
            raise ProviderError(f"HTTP {e.code}: {_error_text(raw)}", raw)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < retries:
                time.sleep(min(2 ** attempt * 2, 30)); continue
            raise ProviderError(f"network: {type(e).__name__}")
    raise ProviderError("unreachable")

class TokenCapReached(Exception):
    pass

# --- spend control.
# PUBLIC DEFAULT: no hard cap. A user pays their own provider and may set --spend-cap-usd (and --token-cap) themselves.
# OUR OWN caps (the owner's budget for this project) live OUTSIDE the repo in a local file, ~/.navital-gym/caps.json (or the path in NAVITAL_INTERNAL_CAPS):
#     {"anthropic": 65, "openai": 3}
# Whenever that file exists, every run on this machine is capped by it (a flag can only lower a cap). Our run scripts also set NAVITAL_REQUIRE_CAPS=1, which makes a
# paid provider (anthropic, openai) REFUSE to run when no cap is configured for it, so our protection cannot silently go missing.
PAID_PROVIDERS = ("anthropic", "openai")
HARD_CAPS_USD: dict = {}          # intentionally empty in the public code

def internal_caps() -> dict:
    path = os.environ.get("NAVITAL_INTERNAL_CAPS") or os.path.expanduser("~/.navital-gym/caps.json")
    try:
        data = json.load(open(path))
        return {k: float(v) for k, v in data.items() if isinstance(v, (int, float))}
    except (OSError, ValueError, AttributeError):
        return {}

# Conservative USD per million tokens (input, output): deliberately at or above list prices so the ledger over-counts rather than under-counts.
# PRICE_DEFAULTS is the fallback per provider; PRICE_FAMILIES overrides it for a model family (matched on the model name), so a Sonnet run is not priced at the Haiku-level default.
# Pass --price-in / --price-out for any model whose rate you know to differ.
PRICE_DEFAULTS = {"anthropic": (2.0, 10.0), "openai": (0.60, 2.40)}
PRICE_FAMILIES = {"anthropic": (("sonnet", (5.0, 25.0)),)}

def default_price(prov: str, model: str):
    for fam, price in PRICE_FAMILIES.get(prov, ()):
        if fam in model.lower():
            return price
    return PRICE_DEFAULTS[prov]

class Ledger:
    """runs/spend-ledger.json: tokens and dollars spent so far per provider, across runs AND across concurrent processes. Contains no keys.
    Every read goes to the file and every update is read-modify-write under an exclusive file lock, so parallel runs cannot overwrite each other."""
    def __init__(self, path: str = "runs/spend-ledger.json"):
        self.path = path

    def _read(self) -> dict:
        try:
            return json.load(open(self.path))
        except (OSError, ValueError):
            return {}

    @property
    def data(self) -> dict:
        return self._read()

    def total(self, provider: str) -> float:
        return float(self._read().get(provider, {}).get("usd", 0.0))

    def add(self, provider: str, model: str, tin: int, tout: int, usd: float):
        import fcntl
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path + ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = self._read()
            d = data.setdefault(provider, {"usd": 0.0, "input_tokens": 0, "output_tokens": 0, "models": {}})
            d["usd"] = round(d["usd"] + usd, 6); d["input_tokens"] += tin; d["output_tokens"] += tout
            m = d["models"].setdefault(model, {"usd": 0.0, "input_tokens": 0, "output_tokens": 0})
            m["usd"] = round(m["usd"] + usd, 6); m["input_tokens"] += tin; m["output_tokens"] += tout
            d["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=1, sort_keys=True)
            os.replace(tmp, self.path)

class SpendCapReached(Exception):
    pass

_FINAL_TOOL_NAMES = {"json", "final", "final_answer", "answer", "submit", "submit_answer", "output"}

def _salvage_failed_generation(err: "ProviderError"):
    """Some models (gpt-oss on Groq) end by 'calling' a pseudo-tool such as `json` with the answer as its arguments; the provider rejects that with a 400 that
    still carries what the model wrote (`failed_generation`). If that text is a call to one of those pseudo-tools, return its arguments (or the JSON in the text)
    as the final answer; otherwise None. Real tool names are never rewritten."""
    if "failed_generation" not in err.body:
        return None
    try:
        gen = json.loads(err.body).get("error", {}).get("failed_generation")
    except (ValueError, AttributeError):
        return None
    if not isinstance(gen, str):
        return None
    obj = extract_json(gen)
    if isinstance(obj, dict) and str(obj.get("name", "")).lower() in _FINAL_TOOL_NAMES:
        args = obj.get("arguments", obj.get("parameters"))
        if isinstance(args, str):
            return args
        if isinstance(args, dict):
            return json.dumps(args)
    return None

class ToolChatAgent:
    """Subclass supplies _chat(messages, tools, json_mode) -> {"content": str, "tool_calls": [{"id","name","args"}]} over internal messages
    ({"role": user|assistant|tool, "content", "tool_calls", "tool_call_id"})."""
    def __init__(self, model: str, max_turns: int = 40, temperature: float = 0.0, timeout: int = 300, repair: bool = True, json_mode: bool = True, pause: float = 0.0):
        self.name = self.model = model
        self.max_turns, self.temperature, self.timeout, self.repair, self.json_mode, self.pause = max_turns, temperature, timeout, repair, json_mode, pause
        self.validator: Callable[[Any], str | None] | None = None   # set by run_suite from the env: submission -> error text or None
        self.transcript: list = []
        self.meta: dict = {}

    tokens_in = tokens_out = 0
    token_cap: int | None = None      # stop making calls once input+output tokens (all runs of this agent) reach this
    provider = ""                     # set by make_agent; the ledger key
    price: tuple | None = None        # (usd per M input tokens, usd per M output tokens); None = free tier (tokens counted, no dollars)
    spend_cap_usd: float | None = None
    ledger: "Ledger | None" = None
    _tools_spec: list = []
    _last_in = 2500                   # prompt size of the last call, used to project the next call's cost before making it
    _max_out = 4096

    def _count(self, tin, tout):
        tin, tout = int(tin or 0), int(tout or 0)
        self.tokens_in += tin; self.tokens_out += tout; self._last_in = max(tin, 500)
        self.meta["tokens"] = self.meta.get("tokens", 0) + tin + tout
        if self.ledger is not None:
            usd = (tin * self.price[0] + tout * self.price[1]) / 1e6 if self.price else 0.0
            self.ledger.add(self.provider, self.model, tin, tout, usd)
            self.meta["usd"] = round(self.meta.get("usd", 0.0) + usd, 6)
        if self.token_cap and self._tokens_total() >= self.token_cap:
            raise TokenCapReached(f"token cap {self.token_cap} reached")

    def _tokens_total(self) -> int:
        """Tokens used with this provider across ALL runs (the ledger), or this process only when there is no ledger."""
        if self.ledger is not None:
            d = self.ledger.data.get(self.provider, {})
            return int(d.get("input_tokens", 0)) + int(d.get("output_tokens", 0))
        return self.tokens_in + self.tokens_out

    def _precheck(self):
        """Refuse to make a call whose worst case would take the provider's total past its dollar cap or token cap."""
        if self.token_cap and self._tokens_total() + self._last_in + self._max_out >= self.token_cap:
            raise TokenCapReached(f"token cap {self.token_cap} would be exceeded")
        if self.ledger is not None and self.price and self.spend_cap_usd is not None:
            worst = (self._last_in * self.price[0] + self._max_out * self.price[1]) / 1e6
            if self.ledger.total(self.provider) + worst >= self.spend_cap_usd:
                raise SpendCapReached(f"{self.provider} spend cap ${self.spend_cap_usd:.2f} would be exceeded")

    def settings(self) -> dict:
        return {"model": self.model, "temperature": self.temperature, "max_turns": self.max_turns, "repair_retry": self.repair, "json_mode_on_final": self.json_mode}

    def _chat(self, messages, tools, json_mode=False):
        raise NotImplementedError

    def _call(self, messages, tools, json_mode=False):
        self._precheck()
        return self._chat(messages, tools, json_mode)

    def _problem(self, sub):
        if sub is None:
            return "no JSON object found in your reply"
        if not isinstance(sub, dict):
            return "the answer must be one JSON object"
        return self.validator(sub) if self.validator else None

    def solve(self, obs, call_tool, task):
        messages = [{"role": "user", "content": obs["prompt"]}]
        self.transcript, self.meta = messages, {"repaired": False, "turns": 0, "turns_exhausted": False, "error": None}
        self._tools_spec = obs["tools"]
        if self.token_cap and self._tokens_total() >= self.token_cap:
            self.meta.update(error="token cap reached", cap_reached=True)
            return None
        try:
            final, exhausted = None, True
            for _ in range(self.max_turns):
                self.meta["turns"] += 1
                msg = self._call(messages, obs["tools"], False)
                messages.append(msg)
                if not msg.get("tool_calls"):
                    final, exhausted = msg.get("content") or "", False
                    break
                for c in msg["tool_calls"]:
                    messages.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"], "content": json.dumps(call_tool(c["name"], c["args"]))[:12000]})
                if self.pause:
                    time.sleep(self.pause)
            if exhausted:
                self.meta["turns_exhausted"] = True
                messages.append({"role": "user", "content": FINAL})
                msg = self._call(messages, [], self.json_mode); messages.append(msg)
                final = msg.get("content") or ""
            sub = extract_json(final)
            problem = self._problem(sub)
            if problem and self.repair and not exhausted:
                self.meta["repaired"] = True
                messages.append({"role": "user", "content": REPAIR.format(err=problem)})
                msg = self._call(messages, [], self.json_mode); messages.append(msg)
                sub = extract_json(msg.get("content") or "")
            elif problem and exhausted and self.repair:
                self.meta["repaired"] = True
                messages.append({"role": "user", "content": REPAIR.format(err=problem)})
                msg = self._call(messages, [], self.json_mode); messages.append(msg)
                sub = extract_json(msg.get("content") or "")
            return sub
        except QuotaExhausted as e:
            self.meta["error"] = str(e); self.meta["quota_exhausted"] = True; self.meta["quota_wait"] = e.wait
            return None
        except ProviderError as e:
            self.meta["error"] = str(e)
            return None
        except (TokenCapReached, SpendCapReached) as e:
            self.meta["error"] = str(e)
            self.meta["cap_reached"] = True
            return None

class OpenAIChatAgent(ToolChatAgent):
    """OpenAI-compatible endpoint with tool calling."""
    def __init__(self, model, base_url="http://localhost:11434/v1", api_key="none", extra_headers=None, max_tokens=None, **kw):
        super().__init__(model, **kw)
        self.base, self.key, self.extra_headers = base_url.rstrip("/"), api_key, dict(extra_headers or {})
        self.max_tokens = max_tokens          # None = the provider's default (Sarvam's is 2048, which a reasoning model can use up before writing any answer)

    def settings(self):
        return {**super().settings(), "provider": self.provider or "openai-compatible", "base_url": self.base}

    @staticmethod
    def _wire(messages):
        out = []
        for m in messages:
            if m["role"] == "assistant":
                w = {"role": "assistant", "content": m.get("content") or ""}
                if m.get("tool_calls"):
                    w["tool_calls"] = [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["args"])},
                                        **({"extra_content": c["extra"]} if c.get("extra") else {})} for c in m["tool_calls"]]   # Gemini 3 needs its thought_signature sent back
                out.append(w)
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            else:
                out.append({"role": "user", "content": m["content"]})
        return out

    def _chat(self, messages, tools, json_mode=False):
        body = {"model": self.model, "messages": self._wire(messages), "temperature": self.temperature}
        if self.max_tokens: body["max_tokens"] = self.max_tokens
        if tools: body["tools"] = tools
        if json_mode and not tools: body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.key, **self.extra_headers}
        try:
            r = _post(self.base + "/chat/completions", headers, body, self.timeout)
        except ProviderError as e:
            salvaged = _salvage_failed_generation(e)
            if salvaged is not None:
                return {"role": "assistant", "content": salvaged, "tool_calls": []}
            if "Tool messages found but no tools" in str(e) and self._tools_spec:
                # some providers (Sarvam) reject a tool-free call once the history holds tool messages: send the tools again but forbid calling them
                body.pop("response_format", None)
                body["tools"], body["tool_choice"] = self._tools_spec, "none"
                r = _post(self.base + "/chat/completions", headers, body, self.timeout)
                return self._parse(r, messages)
            if json_mode and "response_format" in body and "HTTP 400" in str(e):     # provider without JSON mode: retry plainly
                body.pop("response_format")
                r = _post(self.base + "/chat/completions", headers, body, self.timeout)
            else:
                raise
        return self._parse(r, messages)

    def _parse(self, r, messages):
        self._count(r.get("usage", {}).get("prompt_tokens"), r.get("usage", {}).get("completion_tokens"))
        ch = r["choices"][0]
        m = ch["message"]
        calls = []
        for i, c in enumerate(m.get("tool_calls") or []):
            fn = c.get("function", {})
            try: args = json.loads(fn.get("arguments") or "{}")
            except ValueError: args = {}
            calls.append({"id": c.get("id") or f"call_{len(messages)}_{i}", "name": fn.get("name", ""), "args": args if isinstance(args, dict) else {},
                          **({"extra": c["extra_content"]} if c.get("extra_content") else {})})
        content = _re.sub(r"<think>.*?</think>", "", m.get("content") or "", flags=_re.S)     # reasoning models: thinking is not the answer (reasoning_content is never read either)
        if ch.get("finish_reason") == "length":
            self.meta["truncated"] = self.meta.get("truncated", 0) + 1                       # the output hit max_tokens: reported, never silently scored as a wrong answer
        return {"role": "assistant", "content": content, "tool_calls": calls}

class AnthropicChatAgent(ToolChatAgent):
    """Anthropic Messages API with tool use."""
    URL = "https://api.anthropic.com/v1/messages"
    def __init__(self, model, api_key="", base_url=None, max_tokens=4096, **kw):
        super().__init__(model, **kw)
        self.key, self.url, self.max_tokens = api_key, (base_url.rstrip("/") + "/v1/messages") if base_url else self.URL, max_tokens

    def settings(self):
        return {**super().settings(), "provider": self.provider or "anthropic", "max_tokens": self.max_tokens}

    @staticmethod
    def _wire(messages):
        out = []
        for m in messages:
            if m["role"] == "assistant":
                blocks = ([{"type": "text", "text": m["content"]}] if m.get("content") else []) + [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]} for c in m.get("tool_calls") or []]
                out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": "."}]})
            elif m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) and out[-1]["content"] and out[-1]["content"][0].get("type") == "tool_result":
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            else:
                out.append({"role": "user", "content": m["content"]})
        return out

    def _chat(self, messages, tools, json_mode=False):
        body = {"model": self.model, "max_tokens": self.max_tokens, "messages": self._wire(messages)}
        if not getattr(self, "_no_temperature", False):
            body["temperature"] = self.temperature
        if tools:
            body["tools"] = [{"name": t["function"]["name"], "description": t["function"]["description"], "input_schema": t["function"]["parameters"]} for t in tools]
        headers = {"Content-Type": "application/json", "x-api-key": self.key, "anthropic-version": "2023-06-01"}
        try:
            r = _post(self.url, headers, body, self.timeout)
        except ProviderError as e:
            if "temperature" in str(e) and "temperature" in body:       # newer Claude models reject the parameter: drop it and remember
                self._no_temperature = True
                body.pop("temperature")
                r = _post(self.url, headers, body, self.timeout)
            else:
                raise
        self._count(r.get("usage", {}).get("input_tokens"), r.get("usage", {}).get("output_tokens"))
        text, calls = "", []
        for b in r.get("content", []):
            if b.get("type") == "text": text += b.get("text", "")
            elif b.get("type") == "tool_use": calls.append({"id": b["id"], "name": b["name"], "args": b.get("input") or {}})
        return {"role": "assistant", "content": text, "tool_calls": calls}

# provider shortcuts for the CLI:  <provider>:<model>   (keys come from environment variables, never from the command line)
PROVIDERS = {
    "ollama": ("http://localhost:11434/v1", None),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    "sarvam": ("https://api.sarvam.ai/v1", "SARVAM_API_KEY"),       # Sarvam AI (India); wants the key in BOTH Authorization: Bearer and api-subscription-key
}
EXTRA_HEADERS = {}      # per-provider extra request headers (none needed today). GitHub Models was removed: retired by GitHub on 30 July 2026; its endpoint now answers 200 "OK" to everything.

ALLOWED_ENV_NAMES = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "HF_TOKEN", "SARVAM_API_KEY", "CEREBRAS_API_KEY", "MISTRAL_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"}

def load_env_file(path: str) -> int:
    """Read KEY=VALUE lines into os.environ for the provider key names above ONLY (a stray .env.local cannot set proxies, CA bundles, PYTHON* or
    GIT_* variables). Existing variables win. Values are never printed. Returns how many were set."""
    n = 0
    try:
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k in ALLOWED_ENV_NAMES and v and k not in os.environ:
                os.environ[k] = v; n += 1
    except OSError:
        pass
    return n

def make_agent(spec: str, spend_cap_usd: float | None = None, price_in: float | None = None, price_out: float | None = None, ledger_path: str = "runs/spend-ledger.json", **kw):
    """spec: 'ollama:qwen2.5:7b' | 'groq:<model>' | 'openrouter:<model>:free' | 'gemini:<model>' | 'openai:<model>[@base_url]' | 'anthropic:<model>'.
    Spend rules: no cap in the public default; --spend-cap-usd sets your own. Our owner's caps come from ~/.navital-gym/caps.json (see internal_caps); groq/gemini free tier only
    (we just stop at rate limits); openrouter ':free' models only; spend is counted in a persistent ledger."""
    prov, _, rest = spec.partition(":")
    if prov == "cloudflare":      # Workers AI, OpenAI-compatible; the account id is part of the URL; model ids start with "@cf/" so no "@base" suffix is parsed here
        acct, tok = os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""), os.environ.get("CLOUDFLARE_API_TOKEN", "")
        if not acct or not tok:
            raise ValueError("CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must both be set (put them in .env.local; the CLI loads them). Free daily allowance only.")
        ag = OpenAIChatAgent(rest, f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/v1", tok, **kw)
        ag.provider = "cloudflare"
        ag.ledger = Ledger(ledger_path)
        return ag
    if prov == "openrouter" and not rest.partition("@")[0].endswith(":free"):
        raise ValueError("openrouter is limited to ':free' models (spend rule)")
    if prov == "anthropic":
        ag = AnthropicChatAgent(rest, api_key=os.environ.get("ANTHROPIC_API_KEY", ""), **kw)
    else:
        if prov not in PROVIDERS:
            raise ValueError(f"unknown provider {prov!r}; use one of {sorted(PROVIDERS) + ['anthropic']}")
        model, _, base = rest.partition("@")
        default_base, key_env = PROVIDERS[prov]
        key = os.environ.get(key_env, "") if key_env else "none"
        if key_env and not key:
            raise ValueError(f"{key_env} is not set (put it in .env.local; the CLI loads it)")
        extra = dict(EXTRA_HEADERS.get(prov) or {})
        if prov == "sarvam":
            extra["api-subscription-key"] = key
        if prov == "sarvam":
            kw.setdefault("max_tokens", 32000)       # Sarvam's default of 2048 is used up by reasoning before any answer is written (finish_reason "length", empty content)
        ag = OpenAIChatAgent(model, base or default_base, key, extra_headers=extra, **kw)
    ag.provider = prov
    if prov == "openai":
        ag._max_out = 2048
    ag.ledger = Ledger(ledger_path)
    caps = {**HARD_CAPS_USD, **internal_caps()}
    if prov in PAID_PROVIDERS:
        pi, po = (price_in, price_out) if price_in is not None and price_out is not None else default_price(prov, rest.partition("@")[0])
        ag.price = (float(pi), float(po))
        if os.environ.get("NAVITAL_REQUIRE_CAPS") == "1" and prov not in caps:
            raise ValueError(f"no spend cap is configured for {prov}: this run was started with NAVITAL_REQUIRE_CAPS=1 (our run scripts), which refuses paid providers without one. "
                             f"Put {{\"{prov}\": <usd>}} in ~/.navital-gym/caps.json (or NAVITAL_INTERNAL_CAPS).")
    if prov in caps or spend_cap_usd is not None:
        limits = [x for x in (caps.get(prov), spend_cap_usd) if x is not None]
        ag.spend_cap_usd = min(limits)         # a flag can only lower a configured cap
        if ag.price is None and prov not in PAID_PROVIDERS:
            ag.price = None
    return ag
