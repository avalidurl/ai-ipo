# AI IPO forecasts

A static page of IPO forecasts for OpenAI, Anthropic, xAI, Databricks, and Perplexity.

`refresh.py` reads Polymarket, Kalshi, Manifold, and Metaculus and writes `data.json`. GitHub Actions runs it every six hours. The page does not blend venues, because they ask different questions.

```sh
python3 refresh.py
python3 -m http.server
```
