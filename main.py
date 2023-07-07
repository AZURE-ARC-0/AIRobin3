import base64
from flask import Flask, render_template, request
from flask_socketio import SocketIO, send
import numpy as np
import openai
import json
import time
import config
import requests
import os
import re
import importlib.util
import faiss
import joblib
from tenacity import retry, wait_random_exponential, stop_after_attempt
import datetime
import textwrap
from werkzeug.utils import secure_filename

#create some asci color codes
class asciicolors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    PINK = '\033[95m'
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    BROWN = '\033[93m'
    PURPLE = '\033[95m'
    GREY = '\033[90m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    WARNING = '\033[93m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

max_retry_attempts = 10
current_retry_attempt = 0

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
socketio = SocketIO(app, engineio_logger=False, transports=['websocket'], ping_timeout=600, ping_interval=10)

openai.api_key = config.OPENAI_API_KEY
chosen_model = config.CHATGPT_MODEL
openweather_api_key = config.OPENWEATHER_API_KEY

function_dict = {}
function_metadata = []

print("""
 █████╗ ██╗██████╗  ██████╗ ██████╗ ██╗███╗   ██╗
██╔══██╗██║██╔══██╗██╔═══██╗██╔══██╗██║████╗  ██║
███████║██║██████╔╝██║   ██║██████╔╝██║██╔██╗ ██║
██╔══██║██║██╔══██╗██║   ██║██╔══██╗██║██║╚██╗██║
██║  ██║██║██║  ██║╚██████╔╝██████╔╝██║██║ ╚████║
╚═╝  ╚═╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝
                                                 
version 0.1.7                         airobin.net
""")

# Initialize the FAISS index
if not os.path.exists('memory'):
    os.makedirs('memory')
dimension = 1536  # dimension of the embeddings
f_index = faiss.IndexFlatL2(dimension) if not os.path.exists('memory/index.faiss') else faiss.read_index('memory/index.faiss')
database = [] if not os.path.exists('memory/database.joblib') else joblib.load('memory/database.joblib')  # to store the original strings and their embeddings

def load_addons():
    function_dict = {}
    function_metadata = []
    module_timestamps = {}
    # Load the settings
    with open('settings.json', 'r') as f:
        settings = json.load(f)

    # Check if addons in settings exist in addons folder
    for addon in list(settings.keys()):
        if not os.path.exists(os.path.join('addons', f"{addon}.py")):
            # If addon doesn't exist, remove it from settings
            del settings[addon]
            # Write the new settings back to the file
            with open('settings.json', 'w') as f:
                json.dump(settings, f)
            # Send an update to the frontend
            try:
                send(json.dumps({'settings': settings}))
            except:
                pass


    for filename in os.listdir('addons'):
        if filename.endswith('.py'):
            addon_name = filename[:-3]
            # Check if the addon is in the settings
            if addon_name not in settings:
                # If not, add it with a default value of True
                settings[addon_name] = True
                # Write the new settings back to the file
                with open('settings.json', 'w') as f:
                    json.dump(settings, f)
                # Send an update to the frontend
                try:
                    send(json.dumps({'settings': settings}))
                except:
                    pass
            if settings.get(addon_name, True):
                file_path = os.path.join('addons', filename)
                spec = importlib.util.spec_from_file_location(filename[:-3], file_path)
                module = importlib.util.module_from_spec(spec)

                # Check if the module has been modified since it was last imported
                file_timestamp = os.path.getmtime(file_path)
                if filename in module_timestamps and file_timestamp > module_timestamps[filename]:
                    module = importlib.reload(module)
                module_timestamps[filename] = file_timestamp

                spec.loader.exec_module(module)
                
                # Check if the module name exists in the module's dictionary
                if module.__name__ in module.__dict__:
                    function_dict[module.__name__] = module.__dict__[module.__name__]
                    
                    # Check if the module has a doc and parameters attribute
                    function_metadata.append({
                        "name": module.__name__,
                        "description": getattr(module, 'description', 'No description'),
                        "parameters": getattr(module, 'parameters', 'No parameters'),
                    })
                else:
                    print(f"Module {module.__name__} does not have a function with the same name.")
    
    return function_dict, function_metadata

function_dict, function_metadata = load_addons()


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def get_embedding(text: str, model="text-embedding-ada-002") -> list[float]:
    return openai.Embedding.create(input=[text], model=model)["data"][0]["embedding"]


def store_embedding(input_string):
    # Split the input string into chunks of 350 characters with a 45 character overlap
    chunks = textwrap.wrap(input_string, width=350, break_long_words=False, max_lines=1)
    
    for chunk in chunks:
        embedding = get_embedding(chunk)
        embedding_np = np.array(embedding, dtype=np.float32).reshape(1, -1)  # convert the list to a numpy array
        f_index.add(embedding_np)  # add the embedding to the FAISS index
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # get the current timestamp
        database.append((chunk, embedding_np, timestamp))  # store the original string, its embedding, and the timestamp

    faiss.write_index(f_index, 'memory/index.faiss')  # save the FAISS index to disk
    joblib.dump(database, 'memory/database.joblib')  # save the database to disk

def retrieve_embeddings(input_string):
    if os.path.exists('memory/index.faiss'):
        f_index = faiss.read_index('memory/index.faiss')
    else:
        return []
    embedding = get_embedding(input_string)
    embedding_np = np.array(embedding, dtype=np.float32).reshape(1, -1)

    # Search the top 3 most similar embeddings in the FAISS index
    D, I = f_index.search(embedding_np, 5)
    
    # Retrieve the original strings of the most similar embeddings
    results = [(database[i][0], database[i][2]) for i in I[0]]  # use the indices to retrieve the strings and their timestamps
    return results

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    if file:
        filename = secure_filename(file.filename)
        # create the uploads folder if it doesn't exist
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        # check if file with same name exists
        basename, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
            # if file with same name exists, append (1), (2), etc. to the filename
            filename = f"{basename}({counter}){ext}"
            counter += 1
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        print(f'{asciicolors.PINK}File {filename} saved successfully{asciicolors.END}')
        socketio.sleep(0.1)
        return app.config['UPLOAD_FOLDER'] + '/' + filename


@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    # send the content of settings.json
    with open('settings.json', 'r') as f:
        settings = json.load(f)
        send(json.dumps({'settings': settings}))
        print(f'{asciicolors.GREEN}Client connected{asciicolors.END}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'{asciicolors.RED}Client disconnected{asciicolors.END}')

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
@socketio.on('change_addon_status')
def change_addon_status(data):
    addon = data['addon']
    enabled = data['enabled']
    with open('settings.json', 'r+') as f:
        settings = json.load(f)
        settings[addon] = enabled
        f.seek(0)
        json.dump(settings, f)
        f.truncate()
        global function_dict
        global function_metadata
        function_dict, function_metadata = load_addons()
        send(json.dumps({'settings': settings}))

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
@socketio.on('message')
def handle_message(message):
    global current_retry_attempt
    global max_retry_attempts
    og_message = message
    file_attached = ''
    data = json.loads(message)
    message = data['message']   
    # check for attached_file
    if data.get('attached_file'):
        file_attached = data['attached_file']
        message = f'Attached File: {file_attached}\n{message}' 
    m_results = retrieve_embeddings(message)
    #print(f'{asciicolors.PINK}Retrieving based on: {message} {asciicolors.END}')
    memory_results = list(set(m_results))  # remove duplicates
    # convert the list to a string
    memory_results = '\n'.join(' '.join(map(str, t)) for t in memory_results)
    #print(f'{asciicolors.PINK}Retrieved: {memory_results} {asciicolors.END}')

    history = data.get('history', '') 
    current_date_time = time.strftime("%d/%m/%Y %H:%M:%S")
    response = None
    response_message = ''
    function_dict, function_metadata = load_addons()
    if not function_metadata:
        # add a default function
        function_metadata.append({
            "name": "none",
            "description": "you have no available functions",
            "parameters": {
                "type": "object",
                "properties": {
                },
            },
        })
    try:
        print(f'{asciicolors.YELLOW}This is your memory, it displays 5 related messages from the past:\n-----\n{memory_results}\n-----\nUse this memory only for context, do not react to it! You can use it to answer the last user question though.\n{history}\n{file_attached}\n{message}\nBot: {asciicolors.END}')
        response = openai.ChatCompletion.create(
            model=chosen_model,
            messages=[
                {'role': 'system', 'content': f'You are an autobot AIRobin. You are able to display everything in markdown. (your current base url is http://localhost:5001/ append it path + file to display them in markdown) You are a professional AI capable of handling complex tasks, from writing apps to websites to writing professional games, papers and articles and not stopping until your mission is complete. You can use tools one by one to provide accurate and comprehensive responses. Tool usage does not go in the message. Do not tell the user you can\'t do something because you can! You are smarten than you think. The current date and time: {current_date_time}. An automatic history and memory module will display relevant messages in front of the user input.'},
                {'role': 'user', 'content': f'This is your memory, it displays 5 related messages from the past:\n-----\n{memory_results}\n-----\nUse this memory only for context, do not react to it! You can use it to answer the last user question though.\n{history}\n{file_attached}\n{message}\nBot: '}
            ],
            functions=function_metadata,
            function_call="auto",
            max_tokens=1500,
            temperature=0.2,
            stream=True,
        )
    except (openai.error.APIError, openai.error.APIConnectionError, openai.error.RateLimitError) as e:
        error_messages = {
            openai.error.APIError: f"OpenAI API returned an API Error: {e}\nRetrying...",
            openai.error.APIConnectionError: f"Failed to connect to OpenAI API: {e}\nRetrying..",
            openai.error.RateLimitError: f"OpenAI API request exceeded rate limit: {e}\nRetrying.."
        }
        print(error_messages[type(e)])
        current_retry_attempt += 1
        if current_retry_attempt < max_retry_attempts:
            handle_message(og_message)
        else:
            print(f'Failed to send message: {message}')
        return
    current_retry_attempt = 0
    ##process_response(response, message)
    # check the chunks of the response
    function_call_arguments = ''
    function_call_name = ''
    function_response = ''
    try:
        for chunk in response:
            #print(f'{asciicolors.RED}chunk: {chunk}{asciicolors.END}')
            #chunk = chunk.to_dict()
            if 'function_call' in chunk['choices'][0]['delta']:
                #print(f'function call: {chunk["choices"][0]["delta"]["function_call"]}')
                # Accumulate the arguments
                #check if the name exists
                if 'name' in chunk["choices"][0]["delta"]["function_call"]:
                    function_call_name = chunk["choices"][0]["delta"]["function_call"]["name"]
                    print(f'function call name: {function_call_name}')
                function_call_arguments += chunk["choices"][0]["delta"]["function_call"]["arguments"]
                
            elif chunk['choices'][0]['finish_reason'] == 'function_call':
                print(f'{asciicolors.GREEN}full message: {function_call_arguments}{asciicolors.END}')
                # If the function call is finished being constructed, process it
                print(f'finish reason: {chunk["choices"][0]["finish_reason"]}')
                if chunk['choices'][0]['finish_reason'] is not None:
                    # put the function call arguments in the right format
                    converted_function_call_arguments = None
                    try:
                        converted_function_call_arguments = json.loads(function_call_arguments)
                    except json.JSONDecodeError as e:
                        function_call_arguments = function_call_arguments.replace('\n', '')
                        try:
                            converted_function_call_arguments = json.loads(function_call_arguments)
                        except json.JSONDecodeError as e:
                            print(f"JSONDecodeError: {e}")
                            print(f"Invalid JSON: {converted_function_call_arguments}")

                    #convert msg to content: msg json
                    function_call_arguments_json = json.dumps(converted_function_call_arguments)
                    converted_message = f'\n[using addon: {function_call_name} with arguments: {function_call_arguments_json}]'
                    new_message = json.dumps({'content': converted_message})

                    print(f'{asciicolors.BLUE}function {function_call_name} call arguments: {str(function_call_arguments)}{asciicolors.END}')
                    #process_response(function_call_arguments, message)
                    send(new_message) 
                    socketio.sleep(0.1)
                    function = function_dict[function_call_name]
                    function_response = function(**converted_function_call_arguments)

                    message_history = f'start of chat history:\n{history} end of chat history\n'
                    
                    process_functions("", function_call_name, function_response, message, function_dict, function_metadata, message_history, function_call_arguments_json)
                    break
            else:
                send(chunk['choices'][0]['delta'])
                # check if the delta has content
                if 'content' in chunk['choices'][0]['delta']:
                    response_message += chunk['choices'][0]['delta']['content']
                socketio.sleep(0.1)
        store_embedding(f"User: {message}")
        if response_message:
            store_embedding(f"Bot: {response_message}")

    except (openai.error.APIError, openai.error.APIConnectionError, openai.error.RateLimitError) as e:
        error_messages = {
            openai.error.APIError: f"OpenAI API returned an API Error: {e}\nRetrying...",
            openai.error.APIConnectionError: f"Failed to connect to OpenAI API: {e}\nRetrying..",
            openai.error.RateLimitError: f"OpenAI API request exceeded rate limit: {e}\nRetrying.."
        }
        print(error_messages[type(e)])
        current_retry_attempt += 1
        if current_retry_attempt < max_retry_attempts:
            handle_message(og_message)
        else:
            print(f'Failed to send message: {message}')
        return


def process_response(response, message):
    print(f'{asciicolors.YELLOW}processing: {response}{asciicolors.END}')
    response_message = response["choices"][0]["message"]
    if response_message.get('content'):
        send(response_message.get('content', ''))
        
    if response_message.get("function_call"):
        function_name = response_message["function_call"]["name"]
        reply_content = response.choices[0].message
        
        funcs = reply_content.to_dict()['function_call']['arguments']
        funcs = json.loads(funcs)
        
        send(f'\n[using addon: {function_name} with arguments: {funcs}]') 
        socketio.sleep(0.1)

        function = function_dict[function_name]
        function_response = function(**funcs)
        
        process_functions(response_message, function_name, function_response, message, function_dict, function_metadata)

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def process_functions(response_message, function_name, function_response, message, function_dict, function_metadata, message_history = "", function_call_arguments_json = ""):
    global current_retry_attempt
    global max_retry_attempts
    second_response = None
    function_dict, function_metadata = load_addons()
    try:
        second_response = openai.ChatCompletion.create(
            model=chosen_model,
            messages=[
                {"role": "user", "content": f'{message}'},
                {
                    "role": "function",
                    "name": function_name,
                    "content": str(function_response),
                },
            ],
            temperature=0.2,
            functions=function_metadata,
            function_call="auto",
        )
    except (openai.error.APIError, openai.error.APIConnectionError, openai.error.RateLimitError) as e:
        error_messages = {
            openai.error.APIError: f"OpenAI API returned an API Error: {e}\nRetrying...",
            openai.error.APIConnectionError: f"Failed to connect to OpenAI API: {e}\nRetrying...",
            openai.error.RateLimitError: f"OpenAI API request exceeded rate limit: {e}\nRetrying..."
        }
        print(error_messages[type(e)])
        current_retry_attempt += 1
        if current_retry_attempt < max_retry_attempts:
            process_functions(response_message, function_name, function_response, message, function_dict, function_metadata, message_history, function_call_arguments_json)
        else:
            print(f'Failed to send message: {message}')
        return

    current_retry_attempt = 0
    print(f'{asciicolors.YELLOW}second_response: {second_response}{asciicolors.END}')
    final_response = second_response["choices"][0]["message"]
    # add the final response and the response message together
    #might need to remove the 
    final_response = f'{response_message}'
    process_function_message(final_response, function_name, function_response, message, function_dict, function_metadata, message_history, function_call_arguments_json)

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def process_function_message(response_message, function_name, function_response, message, function_dict, function_metadata, message_history = "", function_call_arguments_json = ""):
    global current_retry_attempt
    global max_retry_attempts
    third_response = None
    function_dict, function_metadata = load_addons()
    if not function_metadata:
        # add a default function
        function_metadata.append({
            "name": "none",
            "description": "you have no available functions",
            "parameters": {
                "type": "object",
                "properties": {
                },
            },
        })
    try:
        third_response = openai.ChatCompletion.create(
            model=chosen_model,
            messages=[
                {"role": "system", "content": f'You are capable of handling complex queries and can use tools one by one to provide accurate and comprehensive responses. You will be presented results of your previous tool usage. If you need to use another tool or need to fix bugs, do so now. Tool usage does not go into the chat. If you dont need any more tools or changes, then reply to the users last message with all previous responses, the user did not see the previous responses yet, only you did, so be sure to keep the user up to date'},
                {"role": "user", "content": f'{message_history}\nthe user asked for: \'{message}\'\n\nthe previous tool ({function_name})(args:{function_call_arguments_json}) returned: "{function_response}"\nand previous tools returned: "{response_message}"\nIf you need another tool or do adjustments, do so now, else reply to the user\'s last message with all previous responses, the user did not see the previous responses yet, only you did, so be sure to keep the user up to date'},
            ],
            functions=function_metadata,
            function_call="auto",
            temperature=0.2,
            stream=True,
        )
    except (openai.error.APIError, openai.error.APIConnectionError, openai.error.RateLimitError) as e:
        error_messages = {
            openai.error.APIError: f"OpenAI API returned an API Error: {e}\nRetrying...",
            openai.error.APIConnectionError: f"Failed to connect to OpenAI API: {e}\nRetrying...",
            openai.error.RateLimitError: f"OpenAI API request exceeded rate limit: {e}\nRetrying..."
        }
        print(error_messages[type(e)])
        current_retry_attempt += 1
        if current_retry_attempt < max_retry_attempts:
            process_function_message(response_message, function_name, function_response, message, function_dict, function_metadata, message_history, function_call_arguments_json)
        else:
            print(f'Failed to send message: {message}')
        return
    current_retry_attempt = 0
    print(f'{message_history}\nthe user asked for: {message}; the previous function ({function_name})(args:{function_call_arguments_json}) returned: "{function_response}"\nand previous function calls returned: "{response_message}"\nIf you need to use another function call, do so now. If you dont need any more function calls, then reply to the users last message with all previous responses, the user did not see the previous responses yet, only you did, so be sure to keep the user up to date.')
    
    previous_responses = f'{function_name} (args{function_call_arguments_json}): "{function_response}\n{response_message}\n'
    function_call_arguments = ''
    function_call_name = ''
    for chunk in third_response:
        #print(f'chunk: {chunk}')
        chunk = chunk.to_dict()
        if 'function_call' in chunk['choices'][0]['delta']:
            #print(f'function call: {chunk["choices"][0]["delta"]["function_call"]}')
            # Accumulate the arguments
            #check if the name exists
            if 'name' in chunk["choices"][0]["delta"]["function_call"]:
                function_call_name = chunk["choices"][0]["delta"]["function_call"]["name"]
                print(f'function call name: {function_call_name}')
            function_call_arguments += chunk["choices"][0]["delta"]["function_call"]["arguments"]
            
        elif chunk['choices'][0]['finish_reason'] == 'function_call':
            print(f'full message: {function_call_arguments}')
            # If the function call is finished being constructed, process it
            print(f'finish reason: {chunk["choices"][0]["finish_reason"]}')
            if chunk['choices'][0]['finish_reason'] is not None:
                # put the function call arguments in the right format
                function_call_arguments = json.loads(function_call_arguments)

                #convert msg to content: msg json
                function_call_arguments_json = json.dumps(function_call_arguments)
                converted_message = f'\n[using addon: {function_call_name} with arguments: {function_call_arguments_json}]'
                new_message = json.dumps({'content': converted_message})

                print(f'function {function_call_name} call arguments: {function_call_arguments}')
                #process_response(function_call_arguments, message)
                send(new_message) 
                socketio.sleep(0.1)
                function = function_dict[function_call_name]
                function_response = function(**function_call_arguments)

                
                process_functions(previous_responses, function_call_name, function_response, message, function_dict, function_metadata, message_history)
                break
        else:
            send(chunk['choices'][0]['delta'])
            socketio.sleep(0.1)


if __name__ == '__main__':
    socketio.run(app, debug=False, port=5001)
