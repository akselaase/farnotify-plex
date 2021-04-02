from collections import defaultdict
from farnotify.plex.client import Library, Location, PlexClient
from typing import Dict, List
from farnotify.inotify.recursive_notifier import INotify
from farnotify.plex.client import PlexClient
from inotify_simple import flags
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

RESCAN_EVENTS = flags.CREATE | flags.CLOSE_WRITE | flags.DELETE | flags.DELETE_SELF | flags.MODIFY | flags.MOVED_FROM | flags.MOVED_TO


def parse_path(path: str) -> PurePath:
    nt = PureWindowsPath(path)
    if nt.drive:
        return nt
    else:
        return PurePosixPath(path)


def get_locations(libraries: List[Library]):
    locs = defaultdict(lambda: [])  # type: Dict[Location, List[Library]]
    for lib in libraries:
        for loc in lib.locations:
            locs[loc].append(lib)
    return dict(locs)


def main(host: str, token: str):
    client = PlexClient(host)
    client.set_token(token)
    libraries = client.get_libraries()
    locations = get_locations(libraries)

    with INotify() as inotify:
        for location in locations:
            inotify.add_path(Path(location.path))

        for event in inotify:
            if not event.mask & RESCAN_EVENTS:
                continue

            matching_libs = set()
            for location, libs in locations.items():
                if event.path.is_relative_to(location.path):
                    matching_libs.update(libs)

            if not matching_libs:
                print(f'Nothing to do with {event}!')
                continue

            for lib in matching_libs:
                client.refresh_library(lib, event.path)
