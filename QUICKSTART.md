# Quick Start Guide

## 30-Second Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USER/arxiv-agent.git
cd arxiv-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Get a free Gemini API key
# Go to https://aistudio.google.com/apikey, create a key, then:
export GEMINI_API_KEY="your-key-here"

# 4. Run
python main.py "recent work on efficient transformers"
```

## First Run Example

```bash
$ python main.py "2310.12345"

arXiv Autonomous Digest & QA Agent
======================================================================

[arxiv_agent.main] Query: 2310.12345
[arxiv_agent.main] Using LLM provider: (auto)
[arxiv_agent.main] Using embedding provider: local

[arxiv_agent.graph] running node: query_understanding
[arxiv_agent.graph] running node: arxiv_retrieval
[arxiv_agent.graph] running node: fetch_parse
[arxiv_agent.graph] running node: chunk_embed
[arxiv_agent.graph] running node: summarize

======================================================================
BRIEFING
======================================================================

# Efficient Attention with FlashAttention-3
**arXiv ID:** 2310.12345 | **Published:** 2023-10-15 | Link: https://arxiv.org/abs/2310.12345
**Authors:** Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra

## Why this paper matters
...

> Now in QA mode. Ask questions about the paper, or type 'exit'/'quit'.
> What is the main contribution?
This paper proposes FlashAttention-3, an IO-aware attention algorithm that...

> How does it scale?
[grounded answer based on the paper]

> exit

Full state saved to: ./arxiv_output/state.json
Done.
```

## Common Use Cases

### Digest by Topic
```bash
python main.py "recent work on KV-cache compression for LLMs"
```

### Digest by arXiv ID
```bash
python main.py 2310.12345
python main.py "https://arxiv.org/abs/2310.12345"
```

### Use Local Ollama (No API Key Needed)
```bash
# In terminal 1:
ollama serve

# In terminal 2:
export LLM_PROVIDER=ollama
export OLLAMA_MODEL="qwen2.5:7b-instruct"
python main.py "your topic"
```

### Save Output to Custom Directory
```bash
python main.py "your topic" --output-dir ./my_results
```

### Skip Interactive QA
```bash
python main.py "your topic" --no-qa
```

### Resume QA Later (Without Re-downloading)
```bash
# This time, just load the saved state and ask more questions
python main.py --load-state ./arxiv_output/state.json
```

## Troubleshooting

### "GEMINI_API_KEY is not set"
1. Get a free key: https://aistudio.google.com/apikey
2. Set it: `export GEMINI_API_KEY="your-key"`
3. Or use Ollama instead: see "Use Local Ollama" above

### "Could not reach Ollama"
- Make sure `ollama serve` is running in another terminal
- Check that you've pulled a model: `ollama pull qwen2.5:7b-instruct`

### "Almost no extractable text found"
- Some old papers are scanned PDFs; the agent gracefully degrades to abstract-only mode
- You'll still get a briefing and can ask questions, but it's thinner

### "Topic returned zero results"
- Try a broader query or remove quotes
- Example: instead of `"KV-cache compression"`, try `KV-cache compression transformers`

## Next Steps

- Read the [README.md](README.md) for architecture & design details
- Check [examples/](examples/) for more sample runs
- Look at [tests/](tests/) to see how the components work
- See the 4-min video reflection for a walkthrough of the design

## Support

- Stuck? Check the FAQ in README.md "Getting Help" section
- Want to extend it? See "What's Not Implemented Yet" in README.md

Enjoy! 🚀
