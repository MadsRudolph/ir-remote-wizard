"""FastAPI application — IR Remote Wizard web UI with HA ingress support."""

from __future__ import annotations

import os
import uuid
import logging

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import Config
from .database import IRDatabase
from .discovery import DiscoveryEngine, WizardPhase
from .esphome_client import ESPHomeIRClient
from .yaml_generator import generate_yaml, save_yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IR Remote Wizard")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Global state (initialized on startup)
config: Config = None
db: IRDatabase = None
engine: DiscoveryEngine = None
ir_client: ESPHomeIRClient | None = None


@app.on_event("startup")
async def startup():
    global config, db, engine
    config = Config.load()
    db = IRDatabase(config.db_path)
    engine = DiscoveryEngine(db)
    logger.info("IR Remote Wizard started. DB: %s", config.db_path)

    stats = db.get_stats()
    logger.info("Database: %d devices, %d codes, %d types, %d brands",
                stats["devices"], stats["codes"], stats["device_types"], stats["brands"])


def _url(request: Request, path: str) -> str:
    """Build a URL respecting HA ingress path prefix."""
    ingress = os.environ.get("INGRESS_PATH", "")
    return f"{ingress}{path}"


def _render(request: Request, template: str, context: dict = None) -> HTMLResponse:
    """Render a template with common context."""
    ctx = {"request": request, "url": lambda p: _url(request, p)}
    if context:
        ctx.update(context)
    return templates.TemplateResponse(template, ctx)


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session_id = str(uuid.uuid4())
    session = engine.create_session(session_id)
    return _render(request, "connect.html", {
        "session_id": session_id,
        "config": config,
    })


@app.post("/connect", response_class=HTMLResponse)
async def connect(
    request: Request,
    session_id: str = Form(...),
    esp32_host: str = Form(...),
    esp32_port: int = Form(6053),
    api_key: str = Form(""),
):
    global ir_client

    ir_client = ESPHomeIRClient(
        host=esp32_host,
        port=esp32_port,
        noise_psk=api_key,
    )

    result = await ir_client.test_connection_and_self_check()

    if not result["success"]:
        return _render(request, "connect.html", {
            "session_id": session_id,
            "config": config,
            "error": f"Connection failed: {result['error']}",
        })

    # Connection successful — move to device type selection
    device_types = db.get_device_type_counts()
    return _render(request, "device_type.html", {
        "session_id": session_id,
        "device_types": device_types,
        "device_info": result,
        "self_check": result.get("self_check"),
    })


@app.post("/self-check", response_class=HTMLResponse)
async def self_check(
    request: Request,
    session_id: str = Form(...),
):
    """Manually re-run the IR self-check."""
    if not ir_client:
        return _render(request, "connect.html", {
            "session_id": session_id,
            "config": config,
            "error": "No ESP32 connection. Please connect first.",
        })

    try:
        await ir_client.connect()
        info = await ir_client._client.device_info()
        device_info = {
            "success": True,
            "name": info.name,
            "model": info.model,
            "esphome_version": info.esphome_version,
        }
        check_result = await ir_client.run_self_check()
        await ir_client.disconnect()
    except Exception as e:
        device_info = {"success": True, "name": "Unknown"}
        check_result = {"success": False, "error": str(e), "log_lines": []}

    device_types = db.get_device_type_counts()
    return _render(request, "device_type.html", {
        "session_id": session_id,
        "device_types": device_types,
        "device_info": device_info,
        "self_check": check_result,
    })


@app.post("/device-type", response_class=HTMLResponse)
async def select_device_type(
    request: Request,
    session_id: str = Form(...),
    device_type: str = Form(...),
):
    session = engine.set_device_type(session_id, device_type)
    brands = db.get_brands(device_type)
    return _render(request, "brand.html", {
        "session_id": session_id,
        "device_type": device_type,
        "brands": brands,
    })


@app.post("/brand", response_class=HTMLResponse)
async def select_brand(
    request: Request,
    session_id: str = Form(...),
    brand: str = Form(...),
):
    session = engine.set_brand(session_id, brand)

    if not session.power_candidates:
        return _render(request, "results.html", {
            "session_id": session_id,
            "session": session,
            "yaml_content": "",
            "error": "No IR codes found for this device type and brand.",
        })

    return _render(request, "discovery.html", {
        "session_id": session_id,
        "session": session,
        "candidate": session.current_candidate,
        "phase": "identify",
    })


@app.post("/send-test", response_class=HTMLResponse)
async def send_test(
    request: Request,
    session_id: str = Form(...),
):
    """Send the current candidate IR code to the ESP32 for testing."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    if session.phase == WizardPhase.IDENTIFY:
        candidate = session.current_candidate
        if candidate and ir_client:
            await ir_client.send_ir_code(
                candidate["protocol"],
                candidate.get("address"),
                candidate.get("command"),
                candidate.get("raw_data"),
            )
        return _render(request, "discovery.html", {
            "session_id": session_id,
            "session": session,
            "candidate": candidate,
            "phase": "identify",
            "sent": True,
        })

    elif session.phase == WizardPhase.MAP_BUTTONS:
        button = session.current_button
        if button and ir_client:
            await ir_client.send_ir_code(
                button["protocol"],
                button.get("address"),
                button.get("command"),
                button.get("raw_data"),
            )
        return _render(request, "discovery.html", {
            "session_id": session_id,
            "session": session,
            "candidate": button,
            "phase": "map_buttons",
            "sent": True,
        })

    return RedirectResponse(_url(request, "/"))


@app.post("/confirm", response_class=HTMLResponse)
async def confirm(
    request: Request,
    session_id: str = Form(...),
    worked: str = Form(...),
):
    """Handle user confirmation of whether a code worked."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    did_work = worked == "yes"

    if session.phase == WizardPhase.IDENTIFY:
        session = engine.confirm_power_code(session_id, did_work)

        if session.phase == WizardPhase.MAP_BUTTONS:
            return _render(request, "discovery.html", {
                "session_id": session_id,
                "session": session,
                "candidate": session.current_button,
                "phase": "map_buttons",
                "brand_found": session.matched_brand,
            })
        elif session.phase == WizardPhase.RESULTS:
            yaml_content = generate_yaml(session)
            return _render(request, "results.html", {
                "session_id": session_id,
                "session": session,
                "yaml_content": yaml_content,
            })
        else:
            return _render(request, "discovery.html", {
                "session_id": session_id,
                "session": session,
                "candidate": session.current_candidate,
                "phase": "identify",
            })

    elif session.phase == WizardPhase.MAP_BUTTONS:
        session = engine.confirm_button(session_id, did_work)

        if session.phase == WizardPhase.RESULTS:
            yaml_content = generate_yaml(session)
            return _render(request, "results.html", {
                "session_id": session_id,
                "session": session,
                "yaml_content": yaml_content,
            })
        else:
            return _render(request, "discovery.html", {
                "session_id": session_id,
                "session": session,
                "candidate": session.current_button,
                "phase": "map_buttons",
            })

    return RedirectResponse(_url(request, "/"))


@app.post("/skip-to-results", response_class=HTMLResponse)
async def skip_to_results(request: Request, session_id: str = Form(...)):
    session = engine.skip_to_results(session_id)
    yaml_content = generate_yaml(session)
    return _render(request, "results.html", {
        "session_id": session_id,
        "session": session,
        "yaml_content": yaml_content,
    })


@app.post("/save-yaml", response_class=HTMLResponse)
async def save_yaml_route(
    request: Request,
    session_id: str = Form(...),
    yaml_content: str = Form(...),
):
    """Save the generated YAML to the HA config directory."""
    output_path = os.path.join(config.ha_config_dir, "esphome", "ir-blaster.yaml")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    save_yaml(yaml_content, output_path)

    return _render(request, "results.html", {
        "session_id": session_id,
        "session": engine.get_session(session_id),
        "yaml_content": yaml_content,
        "saved": True,
        "save_path": output_path,
    })
