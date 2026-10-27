#!/usr/bin/env python3
"""How long a resume loop should sleep after a daily-quota stop (exit code 75). usage: quota_sleep.py <provider> <wait-seconds-from-the-provider or 0>
The provider's own "try again in" wins; otherwise the next daily reset: Cloudflare 00:00 UTC, Gemini midnight Pacific (08:00 UTC, the later of PDT/PST), Groq a rolling day (retry hourly)."""
import sys, datetime as dt
prov, wait = sys.argv[1], float(sys.argv[2] or 0)
now = dt.datetime.now(dt.timezone.utc)
def until(hour):
    t = now.replace(hour=hour, minute=10, second=0, microsecond=0)
    return (t if t > now else t + dt.timedelta(days=1)) - now
if wait > 0: secs = wait + 120
elif prov == "cloudflare": secs = until(0).total_seconds()
elif prov == "gemini": secs = until(8).total_seconds()
else: secs = 3600
print(int(min(max(secs, 600), 86400)))
