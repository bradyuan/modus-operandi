"""GPT Actions adapter: exposes ``mo.api`` as a plain HTTPS API with an OpenAPI schema.

A Custom GPT imports ``/openapi.json`` as its Actions and authenticates with a bearer
token (the same secret as the MCP adapter's link). Each tool becomes ``POST /<tool name>``
with the tool's signature as the request body. No MO logic lives here.
"""

import argparse
import inspect
import typing
import warnings

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import create_model

from mo import api
from mo.server import _secret

_bearer = HTTPBearer()
MAX_DESCRIPTION = 300  # GPT Actions limit; the full guidance goes in the GPT's Instructions (api.host_guide)


def _short(doc: str) -> str:
    text = " ".join(inspect.cleandoc(doc).split())
    return text if len(text) <= MAX_DESCRIPTION else text[: MAX_DESCRIPTION - 1].rsplit(" ", 1)[0] + "…"


def _authorized(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    if credentials.credentials != _secret():
        raise HTTPException(status_code=401, detail="Invalid token")


def _endpoint(fn, body_model):
    def call(body) -> dict[str, typing.Any]:
        try:
            return fn(**body.model_dump(exclude_unset=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    call.__annotations__["body"] = body_model  # FastAPI reads this to parse the JSON body
    return call


def create_app(public_url: str | None = None) -> FastAPI:
    app = FastAPI(
        title="Modus Operandi",
        description=api.INSTRUCTIONS,
        version="0.1.0",
        servers=[{"url": public_url}] if public_url else None,
        dependencies=[Depends(_authorized)],
    )
    for fn in api.TOOLS:
        hints = typing.get_type_hints(fn)
        fields = {
            name: (hints[name], ... if param.default is inspect.Parameter.empty else param.default)
            for name, param in inspect.signature(fn).parameters.items()
        }
        with warnings.catch_warnings():  # a field named "register" shadows a BaseModel method; harmless
            warnings.simplefilter("ignore", UserWarning)
            body_model = create_model(f"{fn.__name__}_request", **fields)
        app.post(
            f"/{fn.__name__}",
            operation_id=fn.__name__,
            summary=api.TITLES[fn.__name__],
            description=_short(fn.__doc__),
        )(_endpoint(fn, body_model))
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MO's GPT Actions API.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--public-host", help="tunnel hostname, e.g. abc.trycloudflare.com")
    parser.add_argument("--print-instructions", action="store_true", help="print text for the GPT's Instructions")
    args = parser.parse_args()
    if args.print_instructions:
        print(api.host_guide())
        return
    public_url = f"https://{args.public_host.removeprefix('https://').rstrip('/')}" if args.public_host else None
    if public_url:
        print(f"\nOpenAPI schema for your GPT's Actions: {public_url}/openapi.json\n"
              f"Authentication: API key, Bearer, with the key in ~/.mo/secret (keep it private).\n", flush=True)
    uvicorn.run(create_app(public_url), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
