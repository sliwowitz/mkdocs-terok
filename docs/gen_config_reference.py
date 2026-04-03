# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Generate config reference demo using a space-weather-station Pydantic model."""

import mkdocs_gen_files
from pydantic import BaseModel, Field

from mkdocs_terok.config_reference import (
    render_json_schema,
    render_model_tables,
    render_yaml_example,
)

# ---------------------------------------------------------------------------
# Space weather monitoring station — example model
# ---------------------------------------------------------------------------


class SolarSensors(BaseModel):
    """Solar activity monitoring sensor array."""

    flux_threshold: float = Field(default=120.0, description="Solar flux alert threshold (SFU)")
    particle_detectors: int = Field(default=8, description="Active particle detector count")
    auto_alert: bool = Field(default=True, description="Emit alerts on threshold breach")


class StationConfig(BaseModel):
    """Configuration for a space weather monitoring station."""

    station_id: str = Field(default="SWS-07", description="Unique station identifier")
    region: str | None = Field(default=None, description="Assigned monitoring region")
    polling_interval: float = Field(default=5.0, description="Sensor polling interval (seconds)")
    active: bool = Field(default=True, description="Station operational status")
    watch_bands: list[str] = Field(
        default_factory=lambda: ["X-ray", "EUV"],
        description="Electromagnetic bands under observation",
    )
    solar_sensors: SolarSensors = Field(default_factory=SolarSensors)


# ---------------------------------------------------------------------------
# Field documentation keyed by dotpath
# ---------------------------------------------------------------------------

FIELD_DOCS: dict[str, str] = {
    "station_id": "Broadcast identifier used in telemetry headers.",
    "region": "Heliospheric sector this station is responsible for.",
    "polling_interval": "How often sensors sample, in seconds.",
    "active": "Set to false to put the station in standby mode.",
    "watch_bands": "Spectral bands the station actively monitors.",
    "solar_sensors": "Configuration for the onboard solar sensor array.",
    "solar_sensors.flux_threshold": "Alert fires when solar flux exceeds this value in SFU.",
    "solar_sensors.particle_detectors": "Number of detector modules installed.",
    "solar_sensors.auto_alert": "When enabled, threshold breaches trigger automatic alerts.",
}

# ---------------------------------------------------------------------------
# Render all three formats
# ---------------------------------------------------------------------------

lines: list[str] = [
    "# Config Reference Demo\n",
    "This page demonstrates `mkdocs-terok`'s config-reference generators",
    "using a space-weather-station Pydantic model — **`StationConfig`**.\n",
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
