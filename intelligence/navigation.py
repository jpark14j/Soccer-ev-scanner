"""Navigation metadata only: rendering a route never initiates data collection."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Destination:
    name: str
    renderer: str


PAGES = (
    Destination('Home','home'),
    Destination('Best Picks & Parlays','picks'),
    Destination('Upcoming Games','games'),
    Destination('Performance Tracker','performance'),
    Destination('Settings','settings'),
)
TOOLS = (
    Destination('Connections & Data Settings','settings'),
    Destination('Detailed Picks & Parlays','detailed_picks'),
    Destination('Detailed Performance','detailed_performance'),
    Destination('Daily Research Audit','dashboard'),
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
