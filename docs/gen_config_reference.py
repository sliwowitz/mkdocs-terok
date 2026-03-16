# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: Apache-2.0

"""Generate config reference demo using a Star Trek-themed Pydantic model."""

import mkdocs_gen_files
from pydantic import BaseModel, Field

from mkdocs_terok.config_reference import (
    render_json_schema,
    render_model_tables,
    render_yaml_example,
)

# ---------------------------------------------------------------------------
# Terok Nor / DS9 station configuration model
# ---------------------------------------------------------------------------


class DefenseGrid(BaseModel):
    """Weapons and shield configuration for the station's defense perimeter."""

    shield_frequency: float = Field(default=257.4, description="Primary shield harmonic (GHz)")
    phaser_banks: int = Field(default=48, description="Number of active phaser bank emitters")
    torpedo_launchers: int = Field(default=5000, description="Photon torpedo inventory count")
    auto_targeting: bool = Field(default=True, description="Enable autonomous threat response")


class DockingPylons(BaseModel):
    """Configuration for the upper and lower docking pylons."""

    upper_pylons: int = Field(default=3, description="Number of upper docking pylons")
    lower_pylons: int = Field(default=3, description="Number of lower docking pylons")
    max_vessel_length: float = Field(default=700.0, description="Maximum vessel length (meters)")
    tractor_beam: bool = Field(default=True, description="Enable tractor beam assist on approach")
    cleared_vessels: list[str] = Field(
        default_factory=lambda: ["runabout", "freighter"],
        description="Vessel classes cleared for autonomous docking",
    )


class StationConfig(BaseModel):
    """Primary configuration for Terok Nor (Deep Space Nine) station operations."""

    station_name: str = Field(default="Deep Space Nine", description="Station designation")
    commanding_officer: str = Field(default="Sisko", description="Current CO surname")
    crew_complement: int = Field(default=300, description="Standard crew complement")
    stardate_offset: float = Field(default=0.0, description="Stardate calibration offset")
    self_destruct_enabled: bool = Field(default=False, description="Auto-destruct system armed")
    motto: str | None = Field(default=None, description="Station motto or operational slogan")
    standing_orders: list[str] = Field(
        default_factory=lambda: ["Maintain vigilance at the wormhole"],
        description="Active standing orders",
    )
    defense_grid: DefenseGrid = Field(default_factory=DefenseGrid)
    docking_pylons: DockingPylons = Field(default_factory=DockingPylons)


# ---------------------------------------------------------------------------
# Field documentation keyed by dotpath
# ---------------------------------------------------------------------------

FIELD_DOCS: dict[str, str] = {
    "station_name": "Official designation broadcast on all subspace channels.",
    "commanding_officer": "Surname of the officer holding command authority.",
    "crew_complement": "Number of personnel assigned to the station.",
    "stardate_offset": "Temporal calibration value for the Bajoran wormhole proximity effect.",
    "self_destruct_enabled": "When true, the auto-destruct sequence is armed and awaiting authorization codes.",
    "motto": "Optional station motto displayed on dedication plaques and comm headers.",
    "standing_orders": "Priority directives pushed to all department heads each duty cycle.",
    "defense_grid": "Weapons and shield subsystem configuration.",
    "defense_grid.shield_frequency": "Rotating shield harmonic — randomized during red alert.",
    "defense_grid.phaser_banks": "Total emitter count across all weapon sail towers.",
    "defense_grid.torpedo_launchers": "Current photon torpedo inventory.",
    "defense_grid.auto_targeting": "Allows the defense grid to engage hostiles without manual override.",
    "docking_pylons": "Docking infrastructure for visiting and resident vessels.",
    "docking_pylons.upper_pylons": "Upper pylon berths — typically reserved for Starfleet vessels.",
    "docking_pylons.lower_pylons": "Lower pylon berths — open to civilian and allied traffic.",
    "docking_pylons.max_vessel_length": "Hard limit enforced by structural integrity fields.",
    "docking_pylons.tractor_beam": "Automated tractor lock for final approach guidance.",
    "docking_pylons.cleared_vessels": "Vessel classes that may dock without explicit ops clearance.",
}

# ---------------------------------------------------------------------------
# Render all three formats
# ---------------------------------------------------------------------------

lines: list[str] = [
    "# Config Reference Demo\n",
    "This page demonstrates `mkdocs-terok`'s config-reference generators using a",
    "Star Trek-themed Pydantic model — **`StationConfig`** for Terok Nor / Deep Space Nine.\n",
    "## Field Reference Tables\n",
    render_model_tables(StationConfig, field_docs=FIELD_DOCS),
    "\n## Annotated YAML Example\n",
    "```yaml",
    render_yaml_example(StationConfig, field_docs=FIELD_DOCS),
    "```\n",
    "\n## JSON Schema\n",
    '??? info "Full JSON Schema"',
    "    ```json",
    *[
        f"    {line}"
        for line in render_json_schema(StationConfig, title="StationConfig").splitlines()
    ],
    "    ```\n",
]

with mkdocs_gen_files.open("config-reference.md", "w") as f:
    f.write("\n".join(lines))
