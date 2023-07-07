import os
import subprocess
import sys
import time
import threading

description = "An addon that can restart the main.py python script"

parameters = {
    "type": "object",
    "properties": {
    },
}


def restart_script():
    try:
        # Create a thread that will run the restart_start function
        thread = threading.Thread(target=restart_start)
        # Start the thread
        thread.start()
        return "Restarting in 20 seconds..."
    
    except Exception as e:
        return str(e)

def restart_start():
    time.sleep(20)
    try:
        python = sys.executable
        os.execl(python, python, *sys.argv)
        
    except Exception as e:
        return str(e)
