import requests

description = "Fetches the current Bitcoin price in a user-specified currency"

parameters = {
    "type": "object",
    "properties": {
        "currency": {
            "type": "string",
            "description": "The currency in which the user wants the Bitcoin price (USD, EUR, GBP, etc.))",
        },
    },
    "required": ["currency"],
}

def get_current_bitcoin_price(currency="USD"):
    url = f"https://api.coindesk.com/v1/bpi/currentprice/{currency}.json"
    response = requests.get(url).json()
    # round to 2 decimal places
    price = f"{round(response['bpi'][currency]['rate_float'], 2)} {currency}"
    return price