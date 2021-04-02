import xml.etree.ElementTree as ET
import requests
from dataclasses import dataclass
from typing import Callable, Iterable, List, TypeVar


class PlexError(Exception):
    pass


class PlexUnauthorizedError(PlexError):
    pass


_T = TypeVar('_T')
_R = TypeVar('_R')


def tmap(func: Callable[[_T], _R], seq: Iterable[_T]) -> List[_R]:
    return tuple(map(func, seq))


@dataclass(frozen=True)
class Location:
    key: int
    path: str

    @staticmethod
    def from_xml(tree: ET.Element):
        return Location(
            int(tree.get('id')),
            tree.get('path')
        )


@dataclass(frozen=True)
class Library:
    key: int
    title: str
    kind: str
    locations: List[Location]

    @staticmethod
    def from_xml(tree: ET.Element):
        return Library(
            int(tree.get('key')),
            tree.get('title'),
            tree.get('type'),
            tmap(Location.from_xml, tree)
        )


class PlexClient:
    def __init__(self, host: str = 'https://localhost:32400', authorizer: Callable[[], str] = None) -> None:
        self._base = host.strip('/')
        self._token = ''
        self._authorizer = authorizer

    def _get(self, url, xml=True, **kwargs):
        params = {
            **kwargs,
            'X-Plex-Token': self._token
        }

        req = requests.get(f'{self._base}/library/{url}', params=params, verify=False)

        if req.status_code == requests.codes['unauthorized']:
            if not self._authorizer:
                raise PlexUnauthorizedError
            else:
                self.set_token(self._authorizer())
                return self._get(url, **kwargs)

        if req.status_code != 200:
            raise PlexError(f'Unexpected status code {req.status_code}')

        if xml:
            return ET.fromstring(req.text)
        else:
            return req

    def set_token(self, token: str):
        self._token = token

    def get_libraries(self):
        xml = self._get('sections')
        return tmap(Library.from_xml, xml)

    def refresh_library(self, library: Library, path: str = None):
        self._get(f'sections/{library.key}/refresh', xml=False, path=path)
