import subprocess

description = "This addon allows you to execute a python file or a piece of python code in a new terminal or subprocess and sends the output of the code back. This could be print, return or error messages, whatever the console output is."

parameters = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "The path to the python file to be executed",
        },
        "code": {
            "type": "string",
            "description": "The python code to be executed",
        }
    },
    "required": [],
}

def execute_python(**input):
    try:
        if 'file_path' in input:
            process = subprocess.Popen(['python', input['file_path']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        elif 'code' in input:
            process = subprocess.Popen(['python', '-c', input['code']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            return {'error': 'No valid input provided'}
        stdout, stderr = process.communicate()
        return {'output': stdout.decode('utf-8'), 'error': stderr.decode('utf-8')}
    except Exception as e:
        return {'error': str(e)}
