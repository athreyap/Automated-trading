from __future__ import annotations

def explain_signal(signal: dict, api_key: str = "", model: str = "gpt-4o-mini") -> str:
    """Explain a signal. Local deterministic fallback works without an API key."""
    local = (
        f"Signal: {signal.get('signal', 'WAIT')}. "
        f"Reason: {signal.get('reason', 'No reason available')} "
        "This is a rule-based observation, not a prediction or an instruction to trade."
    )
    if not api_key:
        return local + " AI provider is not configured; showing the local explanation."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "Explain the supplied technical signal neutrally in plain language. Do not recommend a trade or predict returns. Mention uncertainty."},
                {"role": "user", "content": str(signal)},
            ],
        )
        return response.choices[0].message.content or local
    except Exception as exc:
        return local + f" AI explanation unavailable ({type(exc).__name__}); using local explanation."
