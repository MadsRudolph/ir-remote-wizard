"""FastAPI application — IR Remote Wizard web UI with HA ingress support."""

from __future__ import annotations

import asyncio
import os
import uuid
import logging

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import Config
from .database import IRDatabase
from .device_store import DeviceStore, DeviceProfile, SavedButton, make_device_id
from .discovery import ConfirmedButton, DiscoveryEngine, WizardPhase, WizardSession
from .esphome_client import ESPHomeIRClient
from .ha_script_generator import generate_ha_scripts, generate_ha_dashboard_card, save_ha_scripts
from .protocol_map import convert_code
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
device_store: DeviceStore = None
ir_client: ESPHomeIRClient | None = None


@app.on_event("startup")
async def startup():
    global config, db, engine, device_store
    config = Config.load()
    db = IRDatabase(config.db_path)
    engine = DiscoveryEngine(db)
    device_store = DeviceStore(config.ha_config_dir)
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


def _results_context(session: WizardSession, session_id: str, **extra) -> dict:
    """Build the standard context dict for the results page."""
    ctx = {
        "session_id": session_id,
        "session": session,
        "ha_scripts": generate_ha_scripts(session),
        "ha_dashboard": generate_ha_dashboard_card(session),
        "yaml_content": generate_yaml(session),
    }
    ctx.update(extra)
    return ctx


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    devices = device_store.list_devices()
    return _render(request, "home.html", {"devices": devices})


@app.get("/new", response_class=HTMLResponse)
async def new_device(request: Request):
    session_id = str(uuid.uuid4())
    engine.create_session(session_id)
    return _render(request, "connect.html", {
        "session_id": session_id,
        "config": config,
    })


@app.post("/delete/{device_id}", response_class=HTMLResponse)
async def delete_device(request: Request, device_id: str):
    device_store.delete_device(device_id)
    devices = device_store.list_devices()
    return _render(request, "home.html", {"devices": devices})


@app.get("/edit/{device_id}", response_class=HTMLResponse)
async def edit_device(request: Request, device_id: str):
    profile = device_store.get_device(device_id)
    if not profile:
        return RedirectResponse(_url(request, "/"))

    session_id = str(uuid.uuid4())
    session = engine.create_session(session_id)

    # Restore state from saved profile
    session.device_type = profile.device_type
    session.brand = profile.brand
    session.device_name = profile.device_name
    session.matched_brand = profile.matched_brand
    session.matched_device_ids = list(profile.matched_device_ids)
    session.edit_device_id = device_id
    session.confirmed_buttons = [
        ConfirmedButton(
            name=b.name,
            protocol=b.protocol,
            address=b.address,
            command=b.command,
            raw_data=b.raw_data,
        )
        for b in profile.buttons
    ]
    session.phase = WizardPhase.MAP_BUTTONS

    return _render(request, "connect.html", {
        "session_id": session_id,
        "config": config,
        "editing": profile,
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

    # Connection successful
    session = engine.get_session(session_id)
    if session:
        session.device_name = result.get("name", "ir-blaster")

    # Edit flow: skip device type/brand selection, go straight to button picker
    if session and session.phase == WizardPhase.MAP_BUTTONS and session.matched_device_ids:
        engine._load_button_candidates(session)
        return _render(request, "button_picker.html",
                       _button_picker_context(session, session_id))

    # Normal flow: move to device type selection
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
        return _render(request, "button_picker.html",
                       _button_picker_context(session, session_id))

    return RedirectResponse(_url(request, "/"))


@app.post("/bulk-blast", response_class=HTMLResponse)
async def bulk_blast(
    request: Request,
    session_id: str = Form(...),
):
    """Send all candidate power codes sequentially for quick discovery."""
    session = engine.get_session(session_id)
    if not session or not ir_client:
        return HTMLResponse("Session or client not found", status_code=404)

    try:
        await ir_client.connect()
        candidates = session.power_candidates
        for i, candidate in enumerate(candidates):
            # Update UI would be nice, but for now we just blast them
            # Higher level discovery logic might be needed for real async feedback
            await ir_client.send_ir_code(
                candidate["protocol"],
                candidate.get("address"),
                candidate.get("command"),
                candidate.get("raw_data"),
            )
            await asyncio.sleep(0.8) # Wait for device to react/processing
        await ir_client.disconnect()
        return HTMLResponse("Pulse sequence complete.")
    except Exception as e:
        logger.error("Bulk blast failed: %s", e)
        return HTMLResponse(f"Blast failed: {str(e)}", status_code=500)


@app.post("/bulk-confirm", response_class=HTMLResponse)
async def bulk_confirm(
    request: Request,
    session_id: str = Form(...),
    worked: str = Form(...),
):
    """Handle user confirmation after bulk blast."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    did_work = worked == "yes"
    session = engine.confirm_bulk_blast(session_id, did_work)

    if session.phase == WizardPhase.NARROWING:
        # Blast the first test subset and show narrowing UI
        await _blast_candidates(session, session.narrowing_tested)
        return _render(request, "narrow.html", {
            "session_id": session_id,
            "session": session,
        })
    elif session.phase == WizardPhase.MAP_BUTTONS:
        return _render(request, "button_picker.html",
                       _button_picker_context(session, session_id))
    elif session.phase == WizardPhase.RESULTS:
        return _render(request, "results.html",
                       _results_context(session, session_id))

    return RedirectResponse(_url(request, "/"))


@app.post("/narrow-confirm", response_class=HTMLResponse)
async def narrow_confirm(
    request: Request,
    session_id: str = Form(...),
    worked: str = Form(...),
):
    """Handle yes/no during binary search narrowing."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    did_work = worked == "yes"
    session = engine.narrow_confirm(session_id, did_work)

    if session.phase == WizardPhase.NARROWING:
        # Still narrowing — blast the next test subset
        await _blast_candidates(session, session.narrowing_tested)
        return _render(request, "narrow.html", {
            "session_id": session_id,
            "session": session,
        })
    elif session.phase == WizardPhase.MAP_BUTTONS:
        return _render(request, "button_picker.html",
                       _button_picker_context(session, session_id))
    elif session.phase == WizardPhase.RESULTS:
        return _render(request, "results.html",
                       _results_context(session, session_id))

    return RedirectResponse(_url(request, "/"))


async def _blast_candidates(session: WizardSession, indices: list[int]) -> None:
    """Send a subset of power candidates via IR."""
    if not ir_client:
        return
    try:
        await ir_client.connect()
        for idx in indices:
            candidate = session.power_candidates[idx]
            await ir_client.send_ir_code(
                candidate["protocol"],
                candidate.get("address"),
                candidate.get("command"),
                candidate.get("raw_data"),
            )
            await asyncio.sleep(0.8)
        await ir_client.disconnect()
    except Exception as e:
        logger.error("Narrowing blast failed: %s", e)


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
            return _render(request, "button_picker.html",
                           _button_picker_context(session, session_id))
        elif session.phase == WizardPhase.RESULTS:
            return _render(request, "results.html",
                           _results_context(session, session_id))
        else:
            return _render(request, "discovery.html", {
                "session_id": session_id,
                "session": session,
                "candidate": session.current_candidate,
                "phase": "identify",
            })

    return RedirectResponse(_url(request, "/"))


@app.post("/skip-to-results", response_class=HTMLResponse)
async def skip_to_results(request: Request, session_id: str = Form(...)):
    session = engine.skip_to_results(session_id)
    return _render(request, "results.html",
                   _results_context(session, session_id))


def _button_picker_context(
    session: WizardSession, session_id: str, **extra
) -> dict:
    """Build template context for the button picker page."""
    saved_names = {b.name for b in session.confirmed_buttons}

    # Tag each candidate with its index for form submission
    for i, btn in enumerate(session.button_candidates):
        btn["_idx"] = i

    # Group by category, preserving order
    from collections import OrderedDict
    groups: OrderedDict[str, list] = OrderedDict()
    for btn in session.button_candidates:
        cat = btn.get("category", "Other")
        groups.setdefault(cat, []).append(btn)

    ctx = {
        "session_id": session_id,
        "session": session,
        "grouped_buttons": list(groups.items()),
        "saved_names": saved_names,
        "brand_found": session.matched_brand or None,
    }
    ctx.update(extra)
    return ctx


@app.post("/pick-button/test", response_class=HTMLResponse)
async def pick_button_test(
    request: Request,
    session_id: str = Form(...),
    button_idx: int = Form(...),
):
    """Send a specific button's IR code for testing."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    if 0 <= button_idx < len(session.button_candidates):
        button = session.button_candidates[button_idx]
        if ir_client:
            await ir_client.send_ir_code(
                button["protocol"],
                button.get("address"),
                button.get("command"),
                button.get("raw_data"),
            )
        return _render(request, "button_picker.html",
                       _button_picker_context(session, session_id,
                                              testing=button, testing_idx=button_idx))

    return _render(request, "button_picker.html",
                   _button_picker_context(session, session_id))


@app.post("/pick-button/save", response_class=HTMLResponse)
async def pick_button_save(
    request: Request,
    session_id: str = Form(...),
    button_idx: int = Form(...),
):
    """Save a tested button to the confirmed list."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    if 0 <= button_idx < len(session.button_candidates):
        button = session.button_candidates[button_idx]
        # Avoid duplicates
        existing_names = {b.name for b in session.confirmed_buttons}
        if button["button_name"] not in existing_names:
            session.confirmed_buttons.append(ConfirmedButton(
                name=button["button_name"],
                protocol=button["protocol"],
                address=button["address"],
                command=button["command"],
                raw_data=button["raw_data"],
            ))

    return _render(request, "button_picker.html",
                   _button_picker_context(session, session_id,
                                          just_saved=button["button_name"]))


@app.post("/pick-button/delete", response_class=HTMLResponse)
async def pick_button_delete(
    request: Request,
    session_id: str = Form(...),
    button_index: int = Form(...),
):
    """Remove a saved button by index."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    if 0 <= button_index < len(session.confirmed_buttons):
        removed = session.confirmed_buttons.pop(button_index)
        return _render(request, "button_picker.html",
                       _button_picker_context(session, session_id,
                                              just_removed=removed.name))

    return _render(request, "button_picker.html",
                   _button_picker_context(session, session_id))


@app.post("/save-yaml", response_class=HTMLResponse)
async def save_yaml_route(
    request: Request,
    session_id: str = Form(...),
):
    """Save the generated HA scripts to scripts.yaml."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    scripts_yaml = generate_ha_scripts(session)
    logger.info("save-yaml: session %s has %d buttons, scripts length=%d",
                session_id, len(session.confirmed_buttons), len(scripts_yaml))

    result = save_ha_scripts(scripts_yaml, config.ha_config_dir)
    logger.info("save-yaml: result=%s", result)

    # Persist device profile
    if session.confirmed_buttons:
        brand = session.matched_brand or session.brand or "custom"
        device_id = session.edit_device_id or make_device_id(brand, session.device_type)
        profile = DeviceProfile(
            device_id=device_id,
            device_type=session.device_type or "Device",
            brand=brand,
            device_name=session.device_name,
            matched_brand=session.matched_brand,
            matched_device_ids=list(session.matched_device_ids),
            buttons=[
                SavedButton(
                    name=b.name,
                    protocol=b.protocol,
                    address=b.address,
                    command=b.command,
                    raw_data=b.raw_data,
                )
                for b in session.confirmed_buttons
            ],
        )
        device_store.save_device(profile)

    return _render(request, "results.html",
                   _results_context(session, session_id,
                                    saved=True,
                                    save_path=result["path"],
                                    merged=result["merged"]))


# --- Learn Mode routes ---

@app.post("/learn", response_class=HTMLResponse)
async def learn_mode(request: Request, session_id: str = Form(...)):
    """Enter learn mode — bypass database, capture codes from physical remote."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    session.device_type = session.device_type or "Device"

    return _render(request, "learn.html", {
        "session_id": session_id,
        "session": session,
    })


@app.post("/learn/listen", response_class=HTMLResponse)
async def learn_listen(request: Request, session_id: str = Form(...)):
    """Listen for an IR code from the user's remote."""
    session = engine.get_session(session_id)
    if not session or not ir_client:
        return RedirectResponse(_url(request, "/"))

    try:
        await ir_client.connect()
        result = await ir_client.listen_for_ir(timeout=5.0)
        await ir_client.disconnect()
    except Exception as e:
        result = {"success": False, "error": str(e)}

    return _render(request, "learn.html", {
        "session_id": session_id,
        "session": session,
        "capture": result,
    })


@app.post("/learn/test", response_class=HTMLResponse)
async def learn_test(
    request: Request,
    session_id: str = Form(...),
    protocol: str = Form(...),
    address: str = Form(""),
    command: str = Form(""),
    raw_data: str = Form(""),
    pronto: str = Form(""),
    display: str = Form(""),
):
    """Send a captured code back through the ESP32 to test it."""
    session = engine.get_session(session_id)
    if not session or not ir_client:
        return RedirectResponse(_url(request, "/"))

    # Build the capture dict to pass back to template
    capture = {
        "success": True,
        "protocol": protocol,
        "address": address or None,
        "command": command or None,
        "raw_data": raw_data or None,
        "pronto": pronto or None,
        "display": display,
    }

    try:
        await ir_client.connect()
        # Try the best protocol first; fall back to Pronto
        cmd = convert_code(protocol, address or None, command or None, raw_data or None)
        if not cmd and pronto:
            cmd = convert_code("Pronto", raw_data=pronto)
        if cmd:
            await ir_client.send_command(cmd)
        await ir_client.disconnect()
    except Exception as e:
        logger.error("Learn test send failed: %s", e)

    return _render(request, "learn.html", {
        "session_id": session_id,
        "session": session,
        "capture": capture,
        "tested": True,
    })


@app.post("/learn/save", response_class=HTMLResponse)
async def learn_save(
    request: Request,
    session_id: str = Form(...),
    button_name: str = Form(...),
    protocol: str = Form(...),
    address: str = Form(""),
    command: str = Form(""),
    raw_data: str = Form(""),
    pronto: str = Form(""),
):
    """Save a learned button with the user-provided name."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    # Determine what to store: use Pronto if that's the protocol or as fallback
    save_protocol = protocol
    save_address = address or None
    save_command = command or None
    save_raw = raw_data or None

    # If the decoded protocol doesn't map to an ESPHome service, fall back to Pronto
    cmd = convert_code(save_protocol, save_address, save_command, save_raw)
    if not cmd and pronto:
        save_protocol = "Pronto"
        save_address = None
        save_command = None
        save_raw = pronto

    session.confirmed_buttons.append(ConfirmedButton(
        name=button_name.strip(),
        protocol=save_protocol,
        address=save_address,
        command=save_command,
        raw_data=save_raw,
    ))

    return _render(request, "learn.html", {
        "session_id": session_id,
        "session": session,
        "saved_name": button_name.strip(),
    })


@app.post("/learn/delete", response_class=HTMLResponse)
async def learn_delete(
    request: Request,
    session_id: str = Form(...),
    button_index: int = Form(...),
):
    """Remove a saved button by index."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    if 0 <= button_index < len(session.confirmed_buttons):
        session.confirmed_buttons.pop(button_index)

    return _render(request, "learn.html", {
        "session_id": session_id,
        "session": session,
    })


@app.post("/learn/back-to-picker", response_class=HTMLResponse)
async def learn_back_to_picker(request: Request, session_id: str = Form(...)):
    """Return from learn mode to the button picker."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    engine._load_button_candidates(session)
    return _render(request, "button_picker.html",
                   _button_picker_context(session, session_id))


@app.post("/learn/done", response_class=HTMLResponse)
async def learn_done(request: Request, session_id: str = Form(...)):
    """Finish learn mode and go to results."""
    session = engine.get_session(session_id)
    if not session:
        return RedirectResponse(_url(request, "/"))

    session.phase = WizardPhase.RESULTS
    return _render(request, "results.html",
                   _results_context(session, session_id))
