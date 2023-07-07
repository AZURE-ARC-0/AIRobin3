# AIRobin3

AIRobin3 is a powerful AI chatbot built with OpenAI and Flask. It is capable of handling complex tasks, from writing apps, websites, professional games, papers, and articles. It doesn't stop until the mission is complete (it tries at least).

# Demo Videos
<details>
  <summary>Demo Video</summary>

</details>
## Features

- Uses OpenAI's GPT-4 model for generating responses.
- Supports addons which can be enabled or disabled as per the user's preference, some basic addons are already present.
- Capable of handling complex tasks.
- Supports file uploads.
- Uses FAISS for efficient similarity search.
- Has a memory module that displays relevant messages from the past for context. (needs work)
- Retries on API errors with exponential backoff.

## Dependencies

- Flask
- Flask-SocketIO
- OpenAI
- FAISS
- Joblib
- Tenacity
- Werkzeug
- Requests
- Numpy
- Base64

## Installation

1. Clone the repository
```bash
git clone https://github.com/airobinnet/AIRobin3.git
```
2. Navigate to the project directory
```bash
cd AIRobin3
```
3. Install the required packages
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application
```bash
python main.py
```
2. Open your web browser and visit http://localhost:5001/


## Configuration

The app uses the following environment variables for configuration (copy `config_example.py` to `config.py` and edit the api keys):

- `OPENAI_API_KEY`: Your OpenAI API key.
- `CHATGPT_MODEL`: The model to use for chat completions.
- `OPENWEATHER_API_KEY`: Your OpenWeather API key.
- `GOOGLE_API_KEY`: Google API key
- `GOOGLE_CX`: Google CX key

## To do

- Clean up the code, both frontend and backend
- Rework the logic and prompts for a better reasoning
- Improve the memory module, currently a terrible implementation
- A lot more...

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.