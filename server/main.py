import dotenv, os, json, base64

dotenv.load_dotenv()

if "CONFIG_FILE" in os.environ.keys():
    with open(os.getenv("CONFIG_FILE"), "r") as f:
        CONFIG = json.load(f)
elif "CONFIG_STRING" in os.environ.keys():
    CONFIG = json.loads(
        base64.urlsafe_b64decode(os.getenv("CONFIG_STRING").encode("utf-8")).decode(
            "utf-8"
        )
    )
else:
    raise RuntimeError(
        "Environment variable CONFIG_FILE or CONFIG_STRING are both not present."
    )

os.environ["RAW_CONFIG"] = json.dumps(CONFIG)

from util import TargetFileSystem, Resource
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi_restful.tasks import repeat_every
from starlette.status import *
from routes import routers

import logging

FS = TargetFileSystem(**CONFIG["target"])
log = logging.getLogger("uvicorn.error")

if not CONFIG["authenticated"]:
    log.warning("API is not currently authenticated.")

app = FastAPI()

@app.on_event("startup")
@repeat_every(seconds=300)
def run_repeat_tasks():
    FS.clear_old_download_trackers()


@app.middleware("http")
async def authenticate(request: Request, call_next):
    if CONFIG["authenticated"] and not request.url.path.strip("/").startswith("redoc"):
        # Check if header exists
        if not "Authorization" in request.headers.keys():
            log.warning(f"Got no-auth request from {request.client.host}")
            return JSONResponse(
                content={
                    "result": "failure",
                    "message": "Authorization header not included",
                },
                status_code=HTTP_401_UNAUTHORIZED,
            )

        # Check if API key is valid
        if not request.headers["Authorization"] in CONFIG["api_keys"].keys():
            log.warning(
                f"Got bad-auth request from {request.client.host} with key {request.headers['Authorization']}"
            )
            return JSONResponse(
                content={"result": "failure", "message": "Incorrect API key"},
                status_code=HTTP_401_UNAUTHORIZED,
            )

        key = CONFIG["api_keys"][request.headers["Authorization"]]

        # Check if client can access path
        if not any([request.url.path.startswith(p) for p in key["scope"]]):
            log.warning(
                f"Got bad-scope request from {request.client.host} with key {key['name']} to path {request.url.path}"
            )
            return JSONResponse(
                content={
                    "result": "failure",
                    "message": "Do not have scope to access path",
                },
                status_code=HTTP_403_FORBIDDEN,
            )

        log.debug(
            f"Got request to {request.url.path} from {key['name']} @ {request.client.host}"
        )
    else:
        log.debug(f"Got request to {request.url.path} from {request.client.host}")
    response = await call_next(request)
    return response


@app.get("/")
async def root():
    return {
        "target": {
            "system": CONFIG["target"]["module"] + "." + CONFIG["target"]["subclass"],
            "root": CONFIG["target"]["root_path"],
        },
        "modules": [
            {"slug": i["slug"], "displayName": i["display"]}
            for i in CONFIG["modules"].values()
            if i["active"]
        ],
        "keys": len(CONFIG["api_keys"].keys()),
    }

for r in routers:
    app.include_router(r)