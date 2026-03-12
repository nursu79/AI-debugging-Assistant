"""
sample_code.py — Example code with intentional errors for the AI Debugging Assistant to analyze.
"""

def buggy_addition():
    count = 5
    # Error: TypeError (int + str)
    result = count + " items"
    return result

def buggy_indexing():
    items = [1, 2, 3]
    # Error: IndexError (out of range)
    return items[10]

def buggy_dict():
    config = {"user": "admin"}
    # Error: KeyError (missing key)
    return config["database"]

def buggy_attribute():
    service = None
    # Error: AttributeError (None has no .get)
    return service.get(123)

if __name__ == "__main__":
    # Uncomment one to generate a real error for testing the assistant
    # buggy_addition()
    # buggy_indexing()
    # buggy_dict()
    # buggy_attribute()
    print("Uncomment a buggy function call to test.")
