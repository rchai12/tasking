import typer

from docket import __version__

app = typer.Typer()


@app.callback()
def _callback() -> None:
    """Tasks, reminders and calendar sync."""


@app.command()
def version() -> None:
    print(f"docket {__version__}")
