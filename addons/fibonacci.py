description = "Calculate the nth Fibonacci number"

parameters = {
    "type": "object",
    "properties": {
        "n": {
            "type": "integer",
            "description": "The position of the Fibonacci number in the sequence"
        }
    },
    "required": ["n"]
}

def fibonacci(n):
    if n <= 0:
        return "Invalid input. Please enter a positive integer."
    elif n == 1:
        return 0
    elif n == 2:
        return 1
    else:
        a, b = 0, 1
        for _ in range(n - 2):
            a, b = b, a + b
        return b