"""Discovery wizard engine — manages the multi-phase code identification flow."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from .database import IRDatabase
from .protocol_map import BUTTON_CATEGORIES

SESSION_TTL = 2 * 60 * 60  # 2 hours


class WizardPhase(str, Enum):
    CONNECT = "connect"
    DEVICE_TYPE = "device_type"
    BRAND = "brand"
    IDENTIFY = "identify"
    NARROWING = "narrowing"
    MAP_BUTTONS = "map_buttons"
    RESULTS = "results"


@dataclass
class ConfirmedButton:
    """A button whose IR code has been confirmed working by the user."""
    name: str
    protocol: str
    address: str | None
    command: str | None
    raw_data: str | None


@dataclass
class WizardSession:
    """Tracks the state of one discovery session."""
    phase: WizardPhase = WizardPhase.CONNECT
    device_type: str = ""
    brand: str | None = None
    device_name: str = ""
    edit_device_id: str = ""
    created_at: float = field(default_factory=time.time)

    # Phase 1 (Identify) state
    power_candidates: list[dict] = field(default_factory=list)
    current_candidate_idx: int = 0
    matched_device_ids: list[int] = field(default_factory=list)
    matched_brand: str = ""

    # Narrowing state (binary search after bulk blast)
    narrowing_pool: list[int] = field(default_factory=list)
    narrowing_tested: list[int] = field(default_factory=list)
    narrowing_round: int = 0

    # Phase 2 (Map buttons) state
    button_candidates: list[dict] = field(default_factory=list)
    current_button_idx: int = 0
    confirmed_buttons: list[ConfirmedButton] = field(default_factory=list)

    @property
    def current_candidate(self) -> dict | None:
        if 0 <= self.current_candidate_idx < len(self.power_candidates):
            return self.power_candidates[self.current_candidate_idx]
        return None

    @property
    def current_button(self) -> dict | None:
        if 0 <= self.current_button_idx < len(self.button_candidates):
            return self.button_candidates[self.current_button_idx]
        return None

    @property
    def identify_progress(self) -> tuple[int, int]:
        return (self.current_candidate_idx + 1, len(self.power_candidates))

    @property
    def button_progress(self) -> tuple[int, int]:
        return (self.current_button_idx + 1, len(self.button_candidates))

    @property
    def narrowing_total_rounds(self) -> int:
        """Estimate total rounds needed (log2 of initial candidate count)."""
        import math
        n = len(self.power_candidates)
        return max(1, math.ceil(math.log2(n))) if n > 1 else 1


class DiscoveryEngine:
    """Manages the discovery wizard flow."""

    def __init__(self, db: IRDatabase):
        self.db = db
        self.sessions: dict[str, WizardSession] = {}

    def create_session(self, session_id: str) -> WizardSession:
        self._evict_stale()
        session = WizardSession()
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> WizardSession | None:
        session = self.sessions.get(session_id)
        if session and time.time() - session.created_at > SESSION_TTL:
            del self.sessions[session_id]
            return None
        return session

    def _evict_stale(self) -> None:
        now = time.time()
        stale = [sid for sid, s in self.sessions.items() if now - s.created_at > SESSION_TTL]
        for sid in stale:
            del self.sessions[sid]

    def set_device_type(self, session_id: str, device_type: str) -> WizardSession:
        session = self.sessions[session_id]
        session.device_type = device_type
        session.phase = WizardPhase.BRAND
        return session

    def set_brand(self, session_id: str, brand: str | None) -> WizardSession:
        session = self.sessions[session_id]
        session.brand = brand if brand != "_unknown" else None
        session.phase = WizardPhase.IDENTIFY
        self._load_power_candidates(session)
        return session

    def _load_power_candidates(self, session: WizardSession) -> None:
        """Load unique power code candidates for the session."""
        candidates = self.db.get_power_codes_grouped(
            session.device_type, session.brand
        )
        session.power_candidates = candidates
        session.current_candidate_idx = 0

    def confirm_power_code(self, session_id: str, worked: bool) -> WizardSession:
        """Handle user's yes/no response to a power code test."""
        session = self.sessions[session_id]

        if worked:
            candidate = session.current_candidate
            session.matched_device_ids = candidate["device_ids"]
            session.matched_brand = candidate["brands"][0] if candidate["brands"] else ""

            # Add the power button to confirmed list
            session.confirmed_buttons.append(ConfirmedButton(
                name="Power",
                protocol=candidate["protocol"],
                address=candidate["address"],
                command=candidate["command"],
                raw_data=candidate["raw_data"],
            ))

            # Move to button mapping phase
            session.phase = WizardPhase.MAP_BUTTONS
            self._load_button_candidates(session)
        else:
            session.current_candidate_idx += 1
            if session.current_candidate_idx >= len(session.power_candidates):
                # Exhausted all candidates — go to results with nothing
                session.phase = WizardPhase.RESULTS

        return session

    def confirm_bulk_blast(self, session_id: str, worked: bool) -> WizardSession:
        """Handle user confirmation after bulk-blasting all power candidates."""
        session = self.sessions[session_id]

        if worked:
            if len(session.power_candidates) > 1:
                # Multiple candidates — start binary search narrowing
                return self.start_narrowing(session_id)
            else:
                # Single candidate — resolve immediately
                self._resolve_candidate(session, session.power_candidates[0])
        else:
            session.phase = WizardPhase.RESULTS

        return session

    def _resolve_candidate(self, session: WizardSession, candidate: dict) -> None:
        """Resolve to a single candidate: set matched IDs and move to button mapping."""
        session.matched_device_ids = candidate["device_ids"]
        session.matched_brand = candidate["brands"][0] if candidate["brands"] else ""

        session.confirmed_buttons.append(ConfirmedButton(
            name="Power",
            protocol=candidate["protocol"],
            address=candidate["address"],
            command=candidate["command"],
            raw_data=candidate["raw_data"],
        ))

        session.phase = WizardPhase.MAP_BUTTONS
        self._load_button_candidates(session)

    def _resolve_candidates_imprecise(self, session: WizardSession) -> None:
        """Fallback: resolve with ALL candidates (imprecise, same as old behavior)."""
        all_device_ids = []
        all_brands = set()
        for candidate in session.power_candidates:
            all_device_ids.extend(candidate["device_ids"])
            all_brands.update(candidate["brands"])

        session.matched_device_ids = list(set(all_device_ids))
        session.matched_brand = sorted(all_brands)[0] if all_brands else ""

        first = session.power_candidates[0]
        session.confirmed_buttons.append(ConfirmedButton(
            name="Power",
            protocol=first["protocol"],
            address=first["address"],
            command=first["command"],
            raw_data=first["raw_data"],
        ))

        session.phase = WizardPhase.MAP_BUTTONS
        self._load_button_candidates(session)

    def start_narrowing(self, session_id: str) -> WizardSession:
        """Begin binary search narrowing over power candidates."""
        session = self.sessions[session_id]
        session.narrowing_pool = list(range(len(session.power_candidates)))
        session.narrowing_round = 1
        session.phase = WizardPhase.NARROWING

        # First test: blast the first half
        mid = len(session.narrowing_pool) // 2
        session.narrowing_tested = session.narrowing_pool[:mid]
        return session

    def narrow_confirm(self, session_id: str, worked: bool) -> WizardSession:
        """Handle yes/no response during narrowing. Returns updated session."""
        session = self.sessions[session_id]

        if worked:
            # The working code is in the tested half
            session.narrowing_pool = list(session.narrowing_tested)
        else:
            # The working code is in the untested half
            tested_set = set(session.narrowing_tested)
            session.narrowing_pool = [i for i in session.narrowing_pool if i not in tested_set]

        if len(session.narrowing_pool) == 0:
            # Edge case: user said no to everything — fall back to imprecise
            self._resolve_candidates_imprecise(session)
            return session

        if len(session.narrowing_pool) == 1:
            # Found it!
            candidate = session.power_candidates[session.narrowing_pool[0]]
            self._resolve_candidate(session, candidate)
            return session

        # Still narrowing — prepare next round
        session.narrowing_round += 1
        mid = len(session.narrowing_pool) // 2
        session.narrowing_tested = session.narrowing_pool[:mid]
        return session

    def _load_button_candidates(self, session: WizardSession) -> None:
        """Load all button candidates for matched devices."""
        buttons = self.db.get_unique_buttons_for_devices(session.matched_device_ids)

        # Filter out Power (already confirmed) and sort by category
        ordered = []
        seen = {"Power", "Power_on"}
        for category_name, button_names in BUTTON_CATEGORIES.items():
            for target_name in button_names:
                target_lower = target_name.lower()
                for btn in buttons:
                    if btn["button_name"].lower() == target_lower and btn["button_name"] not in seen:
                        btn["category"] = category_name
                        ordered.append(btn)
                        seen.add(btn["button_name"])

        # Add any remaining buttons not in known categories
        for btn in buttons:
            if btn["button_name"] not in seen and btn["button_name"].lower() != "power":
                btn["category"] = "Other"
                ordered.append(btn)
                seen.add(btn["button_name"])

        session.button_candidates = ordered
        session.current_button_idx = 0

    def confirm_button(self, session_id: str, worked: bool) -> WizardSession:
        """Handle user's yes/no response to a button code test."""
        session = self.sessions[session_id]
        button = session.current_button

        if worked and button:
            session.confirmed_buttons.append(ConfirmedButton(
                name=button["button_name"],
                protocol=button["protocol"],
                address=button["address"],
                command=button["command"],
                raw_data=button["raw_data"],
            ))

        session.current_button_idx += 1
        if session.current_button_idx >= len(session.button_candidates):
            session.phase = WizardPhase.RESULTS

        return session

    def skip_to_results(self, session_id: str) -> WizardSession:
        """Skip remaining buttons and go to results."""
        session = self.sessions[session_id]
        session.phase = WizardPhase.RESULTS
        return session
