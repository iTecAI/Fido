from .fs import TargetFileSystem
from .models import *

import os, json

def cfg():
    return json.loads(os.environ["CONFIG_RAW"])