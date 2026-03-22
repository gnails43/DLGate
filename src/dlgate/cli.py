from __future__ import annotations

import asyncio
import logging
import sys

# Windows requires ProactorEventLoop for subprocess support (Playwright)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from dlgate.config import Config
from dlgate.models import ProcessStatus

console = Console()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


@click.group()
@click.option("--config", "config_path", default="config.yaml", help="Path to config file")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx: click.Context, config_path: str, verbose: bool) -> None:
    """DLGate - Automated download gate processor for music tracks."""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["verbose"] = verbose


ALL_SNS = {
    "soundcloud": ("https://soundcloud.com", "SoundCloud"),
    "spotify": ("https://open.spotify.com", "Spotify"),
    "instagram": ("https://www.instagram.com", "Instagram"),
    "tiktok": ("https://www.tiktok.com", "TikTok"),
    "youtube": ("https://www.youtube.com", "YouTube"),
}


@main.command()
@click.argument("services", nargs=-1)
@click.pass_context
def setup(ctx: click.Context, services: tuple[str, ...]) -> None:
    """Open browser for initial SNS login setup.

    Optionally specify which services to open (e.g. dlgate setup spotify tiktok).
    If none specified, opens all.
    """
    asyncio.run(_setup(ctx.obj["config_path"], services))


async def _setup(config_path: str, services: tuple[str, ...]) -> None:
    from dlgate.browser.session import BrowserSession

    config = Config.load(config_path)
    config.ensure_dirs()

    # Filter to requested services
    if services:
        urls = []
        for s in services:
            key = s.lower()
            if key in ALL_SNS:
                urls.append(ALL_SNS[key])
            else:
                console.print(f"[yellow]Unknown service: {s}[/yellow]")
                console.print(f"Available: {', '.join(ALL_SNS.keys())}")
                return
    else:
        urls = list(ALL_SNS.values())

    console.print("[bold]DLGate Setup[/bold]")
    console.print("A browser will open. Please log in to:")
    for _, name in urls:
        console.print(f"  - {name}")
    console.print()

    async with BrowserSession(config.browser) as session:
        page = session.page

        try:
            await page.goto(urls[0][0])
            console.print(f"  Opened {urls[0][1]}")
        except Exception:
            console.print(f"  [yellow]Warning: {urls[0][1]} failed to load, skipping[/yellow]")
        for url, name in urls[1:]:
            new_page = await session.context.new_page()
            try:
                await new_page.goto(url)
                console.print(f"  Opened {name}")
            except Exception:
                console.print(f"  [yellow]Warning: {name} failed to load, skipping[/yellow]")

        console.print()
        console.print("[bold green]Log in to each service, then press Enter to save sessions.[/bold green]")
        input()

    console.print("[bold green]Setup complete! Sessions saved.[/bold green]")


@main.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """Check login status for each SNS."""
    asyncio.run(_check(ctx.obj["config_path"]))


async def _check(config_path: str) -> None:
    from dlgate.browser.session import BrowserSession

    config = Config.load(config_path)
    config.ensure_dirs()

    # Check login by looking for auth cookies per domain
    cookie_checks = [
        ("SoundCloud", [".soundcloud.com"], ["sc_anonymous_id", "oauth_token"]),
        ("Spotify", [".spotify.com"], ["sp_dc", "sp_key"]),
        ("Instagram", [".instagram.com"], ["sessionid", "ds_user_id"]),
        ("TikTok", [".tiktok.com"], ["sessionid", "sid_tt", "sessionid_ss"]),
        ("YouTube", [".youtube.com", ".google.com"], ["SID", "SSID", "LOGIN_INFO"]),
    ]

    console.print("[bold]Checking login status...[/bold]")
    console.print()

    async with BrowserSession(config.browser) as session:
        cookies = await session.context.cookies()

        for name, domains, auth_cookie_names in cookie_checks:
            # Find cookies matching this service's domains
            service_cookies = [
                c for c in cookies
                if any(c["domain"].endswith(d.lstrip(".")) or c["domain"] == d for d in domains)
            ]
            # Check if any auth cookies exist
            found_auth = [
                c["name"] for c in service_cookies
                if c["name"] in auth_cookie_names
            ]

            if found_auth:
                console.print(f"  [bold green]OK[/bold green]  {name}")
            else:
                cookie_names = [c["name"] for c in service_cookies[:5]]
                if service_cookies:
                    console.print(f"  [bold red]NG[/bold red]  {name} (no auth cookie found)")
                else:
                    console.print(f"  [bold red]NG[/bold red]  {name} (no cookies)")

    console.print()
    console.print("Run [bold]dlgate setup <service>[/bold] to log in to specific services.")


@main.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.pass_context
def process(ctx: click.Context, json_file: str) -> None:
    """Process tracks from an exported JSON list."""
    asyncio.run(_process(ctx.obj["config_path"], json_file))


async def _process(config_path: str, json_file: str) -> None:
    from dlgate.browser.session import BrowserSession
    from dlgate.pipeline import load_track_list, process_tracks

    config = Config.load(config_path)
    config.ensure_dirs()

    tracks = load_track_list(json_file)
    if not tracks:
        console.print("[yellow]No tracks found in the list.[/yellow]")
        return

    console.print(f"[bold]Processing {len(tracks)} track(s)...[/bold]")
    console.print()

    async with BrowserSession(config.browser) as session:
        results = await process_tracks(session, tracks, config)

    # Print summary
    console.print()
    print_summary(results)


def print_summary(results: list) -> None:
    table = Table(title="DLGate Results")
    table.add_column("Track", style="cyan", max_width=40)
    table.add_column("Status", justify="center")
    table.add_column("Details", max_width=40)

    for r in results:
        track_name = r.track.title or r.track.url
        if r.track.artist:
            track_name = f"{r.track.artist} - {track_name}"

        if r.status == ProcessStatus.SUCCESS:
            status = "[bold green]SUCCESS[/bold green]"
            details = r.download_path or ""
        elif r.status == ProcessStatus.FAILED:
            status = "[bold red]FAILED[/bold red]"
            details = r.error_message or ""
        elif r.status == ProcessStatus.NO_GATE:
            status = "[yellow]NO GATE[/yellow]"
            details = "No download gate found"
        else:
            status = "[dim]SKIPPED[/dim]"
            details = r.error_message or ""

        table.add_row(track_name, status, details)

    success = sum(1 for r in results if r.status == ProcessStatus.SUCCESS)
    total = len(results)

    console.print(table)
    console.print(f"\n[bold]{success}/{total}[/bold] tracks downloaded successfully.")


if __name__ == "__main__":
    main()
