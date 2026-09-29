"""Small version-pinned pypdf adapter retaining parsed revision links.

pypdf merges trailer dictionaries and deliberately omits /Prev from cross-reference
streams. Observe parsed dictionaries during reading, rather than matching objects
with regular expressions. Compatibility is covered by an incremental-update test.
"""

from typing import Any

from pypdf import PdfReader


class ProvenancePdfReader(PdfReader):
    def __init__(self, *args: Any, **kwargs: Any):
        self.previous_xrefs: list[int] = []
        super().__init__(*args, **kwargs)

    def _read_xref(self, stream):
        previous = super()._read_xref(stream)
        if previous is not None:
            self.previous_xrefs.append(int(previous))
        return previous

    def _process_xref_stream(self, xrefstream):
        if "/Prev" in xrefstream:
            self.previous_xrefs.append(int(xrefstream["/Prev"]))
        return super()._process_xref_stream(xrefstream)
