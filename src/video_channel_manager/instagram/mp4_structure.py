from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator


class InstagramMp4StructureError(ValueError):
    """Local MP4 structure violates a provider requirement or cannot be proved safe."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__(f"Instagram MP4 structure is incompatible: {', '.join(reasons)}")


@dataclass(frozen=True, slots=True)
class Mp4Box:
    box_type: str
    offset: int
    size: int
    header_size: int

    @property
    def payload_offset(self) -> int:
        return self.offset + self.header_size

    @property
    def end_offset(self) -> int:
        return self.offset + self.size


@dataclass(frozen=True, slots=True)
class InstagramMp4StructureEvidence:
    file_size: int
    ftyp_offset: int
    moov_offset: int
    mdat_offset: int
    edit_list_paths: tuple[str, ...]

    @property
    def moov_before_mdat(self) -> bool:
        return self.moov_offset < self.mdat_offset


_BOX_HEADER_SIZE = 8
_EXTENDED_BOX_HEADER_SIZE = 16


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise InstagramMp4StructureError(("truncated_mp4_box_header",))
    return data


def _read_box(stream: BinaryIO, *, offset: int, parent_end: int) -> Mp4Box:
    if parent_end - offset < _BOX_HEADER_SIZE:
        raise InstagramMp4StructureError(("trailing_or_truncated_mp4_box_bytes",))

    stream.seek(offset)
    header = _read_exact(stream, _BOX_HEADER_SIZE)
    size32, raw_type = struct.unpack(">I4s", header)
    box_type = raw_type.decode("latin-1")
    header_size = _BOX_HEADER_SIZE

    if size32 == 1:
        extended = _read_exact(stream, 8)
        size = struct.unpack(">Q", extended)[0]
        header_size = _EXTENDED_BOX_HEADER_SIZE
    elif size32 == 0:
        size = parent_end - offset
    else:
        size = size32

    if size < header_size:
        raise InstagramMp4StructureError((f"invalid_mp4_box_size:{box_type}",))
    if offset + size > parent_end:
        raise InstagramMp4StructureError((f"mp4_box_exceeds_parent:{box_type}",))

    return Mp4Box(box_type=box_type, offset=offset, size=size, header_size=header_size)


def _iter_boxes(stream: BinaryIO, *, start: int, end: int) -> Iterator[Mp4Box]:
    offset = start
    while offset < end:
        box = _read_box(stream, offset=offset, parent_end=end)
        yield box
        if box.size <= 0:
            raise InstagramMp4StructureError((f"non_advancing_mp4_box:{box.box_type}",))
        offset = box.end_offset
    if offset != end:
        raise InstagramMp4StructureError(("mp4_child_boxes_do_not_fill_parent",))


def _find_edit_lists(stream: BinaryIO, moov: Mp4Box) -> tuple[str, ...]:
    paths: list[str] = []
    for moov_child in _iter_boxes(stream, start=moov.payload_offset, end=moov.end_offset):
        if moov_child.box_type != "trak":
            continue
        for trak_child in _iter_boxes(stream, start=moov_child.payload_offset, end=moov_child.end_offset):
            if trak_child.box_type != "edts":
                continue
            found_elst = False
            for edit_child in _iter_boxes(stream, start=trak_child.payload_offset, end=trak_child.end_offset):
                if edit_child.box_type == "elst":
                    found_elst = True
                    paths.append("moov/trak/edts/elst")
            if not found_elst:
                # An edit container without a readable edit-list child is still outside the reviewed contract.
                paths.append("moov/trak/edts")
    return tuple(paths)


def inspect_instagram_mp4_structure(path: Path) -> InstagramMp4StructureEvidence:
    """Parse only the MP4 box structure needed by the Instagram local-upload contract."""

    candidate = path.expanduser()
    try:
        file_size = candidate.stat().st_size
        if file_size <= 0:
            raise InstagramMp4StructureError(("empty_mp4",))
        with candidate.open("rb") as stream:
            root_boxes = tuple(_iter_boxes(stream, start=0, end=file_size))
            ftyp = next((box for box in root_boxes if box.box_type == "ftyp"), None)
            moov = next((box for box in root_boxes if box.box_type == "moov"), None)
            mdat = next((box for box in root_boxes if box.box_type == "mdat"), None)
            reasons: list[str] = []
            if ftyp is None:
                reasons.append("mp4_ftyp_missing")
            if moov is None:
                reasons.append("mp4_moov_missing")
            if mdat is None:
                reasons.append("mp4_mdat_missing")
            if reasons:
                raise InstagramMp4StructureError(tuple(reasons))

            assert ftyp is not None
            assert moov is not None
            assert mdat is not None
            edit_list_paths = _find_edit_lists(stream, moov)
    except InstagramMp4StructureError:
        raise
    except OSError as exc:
        raise InstagramMp4StructureError((f"mp4_structure_read_failed:{type(exc).__name__}",)) from exc

    reasons = []
    if moov.offset > mdat.offset:
        reasons.append("mp4_moov_not_before_mdat")
    if edit_list_paths:
        reasons.append("mp4_edit_list_present")
    if reasons:
        raise InstagramMp4StructureError(tuple(reasons))

    return InstagramMp4StructureEvidence(
        file_size=file_size,
        ftyp_offset=ftyp.offset,
        moov_offset=moov.offset,
        mdat_offset=mdat.offset,
        edit_list_paths=edit_list_paths,
    )


__all__ = [
    "InstagramMp4StructureError",
    "InstagramMp4StructureEvidence",
    "inspect_instagram_mp4_structure",
]
