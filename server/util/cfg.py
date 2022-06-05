import os, json

def cfg():
    return json.loads(os.environ["RAW_CONFIG"])