"""Mounts: sheets inside sheets (record ``docs/plans/2026-10-11-sheet-mounts-layers.md``).

A parent mounts child sheets with dated ``mount``/``unmount`` effects. Parent
expressions read children one way down: ``mount.KIND.ID.key`` (one child) and
``mounts.KIND`` (the live children of a kind, in mount order, for projections:
``sum(mounts.ship[*].bunker)``). A child resolves at the parent's date and never
reads its parent. Each read yields a *namespace*: a plain dict of the child's
values and derived keys (dotted keys nested), ``list`` (its list view), ``id``,
``name``; its own ``mount``/``mounts`` resolve lazily.
"""
import os

from .expr import ExprError, SheetError


class Mount:
    __slots__ = ("kind", "id", "ref", "refs", "gm_created", "retired")

    def __init__(self, kind, mid, ref, refs, gm_created):
        self.kind = kind
        self.id = mid
        self.ref = ref
        self.refs = refs
        self.gm_created = gm_created
        self.retired = False


def live_mounts(state, kind):
    return [m for m in (state.mounts.get(kind) or {}).values() if not m.retired]


def nest(flat):
    """``{"a.b": 1, "c": 2}`` → ``{"a": {"b": 1}, "c": 2}`` (whole keys win)."""
    out = {}
    for k, v in flat.items():
        segs = k.split(".")
        cur = out
        for s in segs[:-1]:
            nxt = cur.get(s)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[s] = nxt
            cur = nxt
        if segs[-1] not in cur or not isinstance(v, dict):
            cur[segs[-1]] = v
    return out


class Namespace(dict):
    """A child's values; ``mount``/``mounts`` are fetched on first read."""

    def __init__(self, data, lazy):
        super().__init__(data)
        self._lazy = lazy

    def get(self, key, default=None):
        if key in ("mount", "mounts") and not dict.__contains__(self, key) and self._lazy:
            dict.__setitem__(self, key, self._lazy(key))
        return dict.get(self, key, default)


class MountContext:
    """Resolves children for one fold: shared cache, cycle stack, fixed date.

    ``provider`` (optional) maps ``(mount) -> namespace`` and is how a tick
    serves children from its in-memory simulation instead of from disk.
    """

    def __init__(self, sheet, at, stack=None, cache=None, provider=None):
        self.sheet = sheet
        self.at = at
        self.stack = (stack or []) + [sheet.path]
        self.cache = cache if cache is not None else {}
        self.provider = provider

    def path_of(self, mount):
        p = os.path.normpath(os.path.join(self.sheet.dir, mount.ref))
        if os.path.isdir(p):
            p = os.path.join(p, "sheet.json")
        return os.path.abspath(p)

    def child(self, mount):
        if self.provider is not None:
            ns = self.provider(mount)
            if ns is not None:
                return ns
        path = self.path_of(mount)
        if path in self.stack:
            raise ExprError("mount cycle: %s" % " -> ".join(
                os.path.basename(os.path.dirname(p)) for p in self.stack + [path]))
        key = (path, self.at)
        if key in self.cache:
            return self.cache[key]
        from .fold import NullSink, run_fold
        from .loader import load_sheet
        try:
            sheet = load_sheet(path)
        except SheetError as exc:
            raise ExprError("mount %s.%s: %s" % (mount.kind, mount.id, exc))
        res = run_fold(sheet, at=self.at, sink=NullSink(),
                       mount_ctx=MountContext(sheet, self.at, self.stack, self.cache))
        ns = namespace(res, mount.id)
        self.cache[key] = ns
        return ns


def namespace(res, mid):
    """A fold result as a read-only namespace for its parent."""
    env = res.aenv
    flat = dict(res.astate.values)
    for k in res.model.derived:
        flat[k] = env.derived(k)
    data = nest(flat)
    data["list"] = env.list_view()
    data["id"] = mid
    data["name"] = res.sheet.name

    def lazy(which):
        st = res.astate
        if which == "mounts":
            return {k: [env.mount_ns(m) for m in live_mounts(st, k)] for k in st.mounts}
        return {k: {m.id: env.mount_ns(m) for m in live_mounts(st, k)} for k in st.mounts}
    return Namespace(data, lazy)
