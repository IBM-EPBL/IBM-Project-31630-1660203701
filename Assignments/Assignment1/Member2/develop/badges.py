

from pathlib import Path

class Badges:
    def __init__(self):
        self._data = {}

    def add(self, name, filename, content):
        self._data[name] = (filename, content)

    def write(self, name):
        path = Path('./_doc/_static')
        path.mkdir(parents=True, exist_ok=True)
        path /= self._data[name][0]
        if path.exists():
            print(f'path {path} already exists')
            return
        path.write_text(self._data[name][1])


badges = Badges()

badges.add('mit', 'license.svg', """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
width="82" height="20"><linearGradient id="b" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop
offset="1" stop-opacity=".1"/></linearGradient><clipPath id="a"><rect width="82" height="20" rx="3"
fill="#fff"/></clipPath><g clip-path="url(#a)"><path fill="#555" d="M0 0h51v20H0z"/><path fill="#007ec6" d="M51
0h31v20H51z"/><path fill="url(#b)" d="M0 0h82v20H0z"/></g><g fill="#fff" text-anchor="middle" font-family="DejaVu
Sans,Verdana,Geneva,sans-serif" font-size="110"><text x="265" y="150" fill="#010101" fill-opacity=".3"
transform="scale(.1)" textLength="410">License</text><text x="265" y="140" transform="scale(.1)"
textLength="410">License</text><text x="655" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)"
textLength="210">MIT</text><text x="655" y="140" transform="scale(.1)" textLength="210">MIT</text></g>
</svg>""".replace('\n', ' '))  # NOQA

badges.add('oitnb', 'oitnb.svg', """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
width="110" height="20"><linearGradient id="b" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop
offset="1" stop-opacity=".1"/></linearGradient><clipPath id="a"><rect width="110" height="20" rx="3"
fill="#fff"/></clipPath><g clip-path="url(#a)"><path fill="#555" d="M0 0h69v20H0z"/><path fill="#fe7d37" d="M69
0h41v20H69z"/><path fill="url(#b)" d="M0 0h110v20H0z"/></g><g fill="#fff" text-anchor="middle" font-family="DejaVu
Sans,Verdana,Geneva,sans-serif" font-size="110"> <text x="355" y="150" fill="#010101" fill-opacity=".3"
transform="scale(.1)" textLength="590">code style </text><text x="355" y="140" transform="scale(.1)"
textLength="590">code style </text><text x="885" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)"
textLength="310">oitnb</text><text x="885" y="140" transform="scale(.1)" textLength="310">oitnb</text></g> </svg>""".replace('\n', ' '))  # NOQA

badges.add('version', 'pypi.svg', """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
width="75" height="20"><linearGradient id="b" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop
offset="1" stop-opacity=".1"/></linearGradient><clipPath id="a"><rect width="75" height="20" rx="3"
fill="#fff"/></clipPath><g clip-path="url(#a)"><path fill="#555" d="M0 0h33v20H0z"/><path fill="#007ec6" d="M33
0h59v20H33z"/><path fill="url(#b)" d="M0 0h92v20H0z"/></g><g fill="#fff" text-anchor="middle" font-family="DejaVu
Sans,Verdana,Geneva,sans-serif" font-size="110"><text x="175" y="150" fill="#010101" fill-opacity=".3"
transform="scale(.1)" textLength="230">pypi</text><text x="175" y="140" transform="scale(.1)"
textLength="230">pypi</text><text x="540" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)"
textLength="290">0.1.0</text><text x="540" y="140" transform="scale(.1)" textLength="290">0.1.0</text></g>
</svg>""".replace('\n', ' '))  # NOQA
