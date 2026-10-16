"""Navigation metadata only: rendering a route never initiates data collection."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Destination:
    name: str
    renderer: str


PAGES = (
    Destination('AI Dashboard','dashboard'),
    Destination('Best Picks & Parlays','picks'),
    Destination('Performance Tracker','performance'),
    Destination('Settings & Research Tools','tools'),
)
TOOLS = (
    Destination('Settings','settings'),
    Destination('Research Operations','operations'),
    Destination('Advanced Markets','markets'),
    Destination('NBA Analytics','sport'),
    Destination('Soccer Analytics','sport'),
    Destination('MLB Analytics','sport'),
    Destination('Live Markets','live'),
    Destination('AI Assistant','assistant'),
    Destination('Model & Data Diagnostics','diagnostics'),
)


def destination(name,registry=PAGES):
    return next(d for d in registry if d.name==name)
