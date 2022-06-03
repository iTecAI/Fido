from requests import RequestException
from util import TargetFileSystem
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi_restful.tasks import repeat_every
import dotenv, os, json
import base64
from starlette.status import *
from modules import *

import logging

dotenv.load_dotenv()

if "CONFIG_FILE" in os.environ.keys():
    with open(os.getenv("CONFIG_FILE"), "r") as f:
        CONFIG = json.load(f)
elif "CONFIG_STRING" in os.environ.keys():
    CONFIG = json.loads(base64.urlsafe_b64decode(os.getenv("CONFIG_STRING").encode("utf-8")).decode("utf-8"))
else:
    raise RuntimeError("Environment variable CONFIG_FILE or CONFIG_STRING are both not present.")

FS = TargetFileSystem(**CONFIG["target"])
log = logging.getLogger("uvicorn.error")

if (not CONFIG["authenticated"]):
    log.warning("API is not currently authenticated.")

MODULES = {
    "podcasts": PodcastModule(CONFIG["modules"]["podcasts"]["options"]["key"])
}

app = FastAPI()

@app.middleware("http")
async def authenticate(request: Request, call_next):
    if (CONFIG["authenticated"]):
        # Check if header exists
        if not "Authorization" in request.headers.keys():
            log.warning(f"Got no-auth request from {request.client.host}")
            return JSONResponse(content={
                "result": "failure",
                "message": "Authorization header not included"
            }, status_code=HTTP_401_UNAUTHORIZED)

        # Check if API key is valid
        if not request.headers["Authorization"] in CONFIG["api_keys"].keys():
            log.warning(f"Got bad-auth request from {request.client.host} with key {request.headers['Authorization']}")
            return JSONResponse(content={
                "result": "failure",
                "message": "Incorrect API key"
            }, status_code=HTTP_401_UNAUTHORIZED)

        key = CONFIG["api_keys"][request.headers["Authorization"]]

        # Check if client can access path
        if not any([request.url.path.startswith(p) for p in key["scope"]]):
            log.warning(f"Got bad-scope request from {request.client.host} with key {key['name']} to path {request.url.path}")
            return JSONResponse(content={
                "result": "failure",
                "message": "Do not have scope to access path"
            }, status_code=HTTP_403_FORBIDDEN)
    
        log.debug(f"Got request to {request.url.path} from {key['name']} @ {request.client.host}")
    else:
        log.debug(f"Got request to {request.url.path} from {request.client.host}")
    response = await call_next(request)
    return response

@app.get("/")
async def root():
    return {
        "target": {
            "system": CONFIG["target"]["module"] + "." + CONFIG["target"]["subclass"],
            "root": CONFIG["target"]["root_path"]
        },
        "modules": [{
            "slug": i["slug"],
            "displayName": i["display"]
        } for i in CONFIG["modules"].values() if i["active"]],
        "keys": len(CONFIG["api_keys"].keys())
    }

@app.post("/methods")
async def run_method(request: Request):
    """
    [
        {
            "module": str,
            "method": str,
            "args": [],
            "kwargs": []
        }, ...
    ]
    """
    items = await request.json()
    result = []
    for method in items:
        if not method["module"] in MODULES.keys():
            result.append({
                "result": "failed",
                "message": f"Failed to run: module {method['module']} invalid."
            })
            continue

        if not method["method"] in MODULES[method["module"]].METHODS:
            result.append({
                "result": "failed",
                "message": f"Failed to run: module {method['module']} has no method {method['method']}."
            })
            continue

        try:
            result.append({
                "result": "success",
                "value": getattr(MODULES[method["module"]], method["method"])(*method["args"], **method["kwargs"])
            })
        except:
            result.append({
                "result": "failed",
                "message": f"Failed to run: module {method['module']} encountered an error running {method['method']}. See server logs."
            })
            log.exception(f"Encountered error running {method['module']}.{method['method']} with {method['args']} & {method['kwargs']}")
    
    return result
        
