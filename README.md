# AI IPO forecasts

A static page of IPO forecasts for OpenAI, Anthropic, xAI, Databricks, and Perplexity.

`refresh.py` reads the public Polymarket, Kalshi, and Manifold APIs and writes `data.json`. GitHub Actions runs it once a day at 06:17 UTC. The page does not blend venues, because they ask different questions.

Metaculus is no longer included. Its official API (`/api/` and `/api2/`) returns 403 and requires an account token, and the previous HTML scrape was also blocked.

```sh
python3 refresh.py
python3 -m http.server
```
