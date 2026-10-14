"""`cm` entry point. Later tasks attach sub-apps (pod, batch, lora, export)."""
from __future__ import annotations

import typer

app = typer.Typer(help="cm: ComfyUI generation on rented RunPod GPUs.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Root command group."""
