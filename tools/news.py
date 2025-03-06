from betting_pool_generator import NewsSearchQuery, smol_llm


def get_news_search_query(topic: str) -> str:
    """Generate an optimized search query from the topic"""
    prompt = f"""
    I need to search for news articles about this topic:
    "{topic}"

    Please generate a short, focused search query that would work well with a news API.
    The query should:
    - Be 1-3 words maximum
    - Focus on the key searchable terms
    - Remove any unnecessary context or descriptive words
    - Be optimized for finding relevant news articles

    Your response should be the following JSON object and nothing else. Do not include any other text, any markdown, or any comments.
    {{
        "search_query": "" // The optimized search query
    }}
    """

    structured_llm = smol_llm.with_structured_output(NewsSearchQuery)
    result = structured_llm.invoke(prompt)
    return result.search_query


def get_news_for_topic(topic: str) -> list[str]:
    """Get relevant news articles for the topic"""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("Warning: NEWS_API_KEY not found in environment")
        return []

    try:
        # First get an optimized search query
        search_query = get_news_search_query(topic)
        print(f"Using search query: {search_query}")

        url = f"https://newsapi.org/v2/everything?q={search_query}&apiKey={api_key}&pageSize=3"
        print(f"Fetching news from: {url}")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        articles = data.get("articles", [])
        return [
            f"Title: {article['title']}\nDescription: {article['description']}"
            for article in articles
        ]
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []
