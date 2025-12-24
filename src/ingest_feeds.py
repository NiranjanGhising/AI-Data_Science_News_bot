
import feedparser

FEEDS = {
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "DeepMind": "https://deepmind.google/blog/feed/",
    "OpenAI News": "https://openai.com/news/rss.xml",
    "Microsoft Research": "https://www.microsoft.com/en-us/research/feed/",
    "Meta Engineering": "https://engineering.fb.com/feed",

    # More AI companies / orgs
    "Anthropic News": "https://www.anthropic.com/news/rss.xml",
    "NVIDIA Developer Blog": "https://developer.nvidia.com/blog/feed/",
    "AWS Machine Learning Blog": "https://aws.amazon.com/blogs/machine-learning/feed/",
    "Google Cloud Blog": "https://cloud.google.com/blog/rss",
    "Microsoft DevBlogs": "https://devblogs.microsoft.com/feed/",
    "Apple Machine Learning Research": "https://machinelearning.apple.com/rss.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "Mistral AI": "https://mistral.ai/news/rss/",
    "Cohere": "https://cohere.com/blog/rss.xml",
    "Stability AI": "https://stability.ai/blog/rss",
    "Databricks Blog": "https://www.databricks.com/blog/rss.xml",
    "Snowflake Blog": "https://www.snowflake.com/blog/rss/",
    "Perplexity": "https://www.perplexity.ai/hub/blog/rss",
    "GitHub Blog (AI)": "https://github.blog/tag/ai/feed/",
    "Weights & Biases": "https://wandb.ai/blog/rss.xml",
    "Pinecone": "https://www.pinecone.io/blog/rss/",
    "Weaviate": "https://weaviate.io/blog/rss.xml",
    "LangChain": "https://blog.langchain.dev/rss/",
}


# Release / changelog feeds (Atom) for “real documentation / library updates”.
RELEASE_FEEDS = {
    "OpenAI Python SDK Releases": "https://github.com/openai/openai-python/releases.atom",
    "OpenAI Node SDK Releases": "https://github.com/openai/openai-node/releases.atom",
    "Transformers Releases": "https://github.com/huggingface/transformers/releases.atom",
    "Diffusers Releases": "https://github.com/huggingface/diffusers/releases.atom",
    "LangChain Releases": "https://github.com/langchain-ai/langchain/releases.atom",
    "Ollama Releases": "https://github.com/ollama/ollama/releases.atom",
    "vLLM Releases": "https://github.com/vllm-project/vllm/releases.atom",
}

def pull_company_posts():
    items = []
    for source, url in {**FEEDS, **RELEASE_FEEDS}.items():
        feed = feedparser.parse(url)
        for e in feed.entries[:15]:
            items.append({
                "title": e.title,
                "summary": getattr(e, "summary", ""),
                "url": e.link,
                "date": getattr(e, "published", getattr(e, "updated", "")),
                "source": source
            })
    return items
