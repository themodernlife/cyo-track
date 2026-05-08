import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import typer

from cyo_track.parser import parse_file

app = typer.Typer()


@app.command()
def main(
    files: list[Path] = typer.Argument(..., help="One or more HY-TEK result files to parse"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON to this file instead of stdout"),
    pretty: bool = typer.Option(True, help="Pretty-print JSON output"),
):
    """Parse HY-TEK Meet Manager result files and emit JSON."""
    all_results = []
    for path in files:
        if not path.exists():
            typer.echo(f"Error: {path} not found", err=True)
            raise typer.Exit(1)
        all_results.extend(parse_file(path))

    data = [asdict(r) for r in all_results]
    text = json.dumps(data, indent=2 if pretty else None)

    if output:
        output.write_text(text)
        typer.echo(f"Wrote {len(all_results)} results to {output}")
    else:
        typer.echo(text)


if __name__ == "__main__":
    app()
