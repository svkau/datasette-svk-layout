"""
Local dev plugin - injects a mock actor from actor.json.
Do NOT use in production. Load with: datasette -p dev_mock_actor.py ...
"""
import json
from pathlib import Path
from datasette import hookimpl


@hookimpl
def actor_from_request(datasette, request):
    actor_file = Path(__file__).parent.parent / "actor.json"
    if actor_file.exists():
        return json.loads(actor_file.read_text())["actor"]
