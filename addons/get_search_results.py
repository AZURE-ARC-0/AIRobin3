import requests
import config

description = "Search the web using Google Search"

parameters = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query",
        },
    },
    "required": ["query"],
}

def get_search_results(query):
    google_api_key = config.GOOGLE_API_KEY
    google_cx = config.GOOGLE_CX
    url = f"https://www.googleapis.com/customsearch/v1?key={google_api_key}&cx={google_cx}&q={query}"
    response = requests.get(url).json()

    if 'items' not in response:
        return "No results found"

    results = []
    for item in response['items'][:5]:
        result = {
            'title': item['title'],
            'link': item['link'],
            'snippet': item['snippet']
        }
        results.append(result)

    # convert to string
    results = str(results)
    return results