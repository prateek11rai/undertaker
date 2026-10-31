"""Source excerpts around stack frames, only from files inside the given folder."""

from dataclasses import dataclass
from pathlib import Path, PurePath

from undertaker.temporal.evidence import Frame

AROUND = 15


@dataclass
class Excerpt:
    """Lines of source around one frame."""

    file: str
    line: int
    start: int
    lines: list[str]

    @property
    def text(self) -> str:
        """Numbered lines, the frame's line marked with '>'."""
        out = []
        for i, src in enumerate(self.lines, start=self.start):
            mark = ">" if i == self.line else " "
            out.append(f"{mark}{i:4d}  {src}")
        return "\n".join(out)


def resolve_inside(root: Path, frame_path: str) -> Path | None:
    """Find the file a frame points at, only if it is a real file inside root.

    Args:
        root: The source folder.
        frame_path: The path from the stack trace.

    Returns:
        The resolved file, or None if it is outside root, a symlink, or missing.
    """
    root = root.resolve()
    pp = PurePath(frame_path)
    if ".." in pp.parts:
        return None
    candidates: list[Path] = []
    if pp.is_absolute():
        candidates.append(Path(pp))
    else:
        candidates.append(root / pp)
    # Traces from another machine: match by trailing path parts inside root.
    for found in sorted(root.rglob(pp.name)):
        candidates.append(found)
    best, best_score = None, -1
    for c in candidates:
        if c.is_symlink() or not c.is_file():
            continue
        r = c.resolve()
        if not r.is_relative_to(root):
            continue
        score = 0
        for a, b in zip(reversed(r.parts), reversed(pp.parts), strict=False):
            if a != b:
                break
            score += 1
        if score > best_score:
            best, best_score = r, score
    return best


def excerpts(frames: list[Frame], root: Path | None, limit: int = 2) -> list[Excerpt]:
    """Read ~30 lines around each frame that resolves inside root."""
    if not root:
        return []
    out = []
    for f in frames[:limit]:
        p = resolve_inside(root, f.path)
        if not p:
            continue
        try:
            lines = p.read_text(errors="replace").splitlines()
        except OSError:
            continue
        start = max(1, f.line - AROUND)
        end = min(len(lines), f.line + AROUND)
        rel = str(p.relative_to(root.resolve()))
        out.append(Excerpt(rel, f.line, start, lines[start - 1 : end]))
    return out
