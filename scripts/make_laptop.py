#!/usr/bin/env python3
"""Generate an animated SVG of a 3D laptop floating and rotating in the air.

GitHub READMEs can't run JavaScript, so all the 3D math happens here: the laptop is
modelled as boxes, rotated and projected for every frame, and written out as SMIL
<animate> tracks that play inside a plain <img>.

Usage:
    python3 scripts/make_laptop.py -o assets/laptop.svg   # animated
    python3 scripts/make_laptop.py --still 0 90           # static preview frames
"""
import argparse
import math

# ---------------------------------------------------------------- settings
W, H = 480, 360            # SVG canvas
FRAMES = 72                # frames per full turn (5 deg each)
DURATION = 8.0             # seconds per full turn
ELEVATION = 22             # camera looks down at this angle (deg)
CAM_DIST = 9.0             # perspective strength (bigger = flatter)
FOCAL = 520                # zoom
BOB = 0.14                 # float height
BOB_CYCLES = 2             # bobs per full turn
LID_OPEN = 105             # lid angle from closed (deg)
LIGHT = (-0.45, 0.75, 0.55)

BODY = (176, 184, 196)     # aluminium
BODY_DARK = (58, 63, 72)   # keyboard well / bezel
SCREEN = "#0d1117"
CODE = ["#ff7b72", "#79c0ff", "#d2a8ff", "#7ee787", "#ffa657", "#79c0ff", "#7ee787"]


# ---------------------------------------------------------------- vector helpers
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a):
    l = math.sqrt(dot(a, a)) or 1
    return mul(a, 1 / l)


LIGHT = norm(LIGHT)


# ---------------------------------------------------------------- model
class Face:
    """A flat quad. `kind`: 'shade' (lit by LIGHT), 'flat' (fixed colour)."""
    def __init__(self, pts, color, kind="shade", stroke=True, parent=None):
        self.pts, self.color, self.kind, self.stroke = pts, color, kind, stroke
        self.parent = parent   # decals show/hide exactly with the face they sit on


def box(origin, ex, ey, ez, color):
    """Box spanned by edge vectors ex, ey, ez from origin. Faces wound outward."""
    o = origin
    p = lambda i, j, k: add(add(add(o, mul(ex, i)), mul(ey, j)), mul(ez, k))
    quads = [
        (p(0, 0, 0), p(0, 1, 0), p(1, 1, 0), p(1, 0, 0)),  # -ez
        (p(0, 0, 1), p(1, 0, 1), p(1, 1, 1), p(0, 1, 1)),  # +ez
        (p(0, 0, 0), p(1, 0, 0), p(1, 0, 1), p(0, 0, 1)),  # -ey
        (p(0, 1, 0), p(0, 1, 1), p(1, 1, 1), p(1, 1, 0)),  # +ey
        (p(0, 0, 0), p(0, 0, 1), p(0, 1, 1), p(0, 1, 0)),  # -ex
        (p(1, 0, 0), p(1, 1, 0), p(1, 1, 1), p(1, 0, 1)),  # +ex
    ]
    # make sure each quad's normal points away from the box centre
    centre = add(o, mul(add(add(ex, ey), ez), 0.5))
    faces = []
    for q in quads:
        n = cross(sub(q[1], q[0]), sub(q[2], q[0]))
        if dot(n, sub(q[0], centre)) < 0:
            q = q[::-1]
        faces.append(Face(list(q), color))
    return faces


def facing(faces, normal):
    """The box face whose outward normal points along `normal`."""
    def n(f):
        return norm(cross(sub(f.pts[1], f.pts[0]), sub(f.pts[2], f.pts[0])))
    return max(faces, key=lambda f: dot(n(f), normal))


def rect_on(origin, u, v, u0, u1, v0, v1, lift, normal, color, kind="shade", stroke=False,
            parent=None):
    """Rectangle decal on a plane, lifted slightly along `normal`."""
    off = mul(normal, lift)
    pt = lambda a, b: add(add(add(origin, mul(u, a)), mul(v, b)), off)
    q = [pt(u0, v0), pt(u1, v0), pt(u1, v1), pt(u0, v1)]
    if dot(cross(u, v), normal) < 0:       # wind so the face points along `normal`
        q = q[::-1]
    return Face(q, color, kind, stroke, parent)


def build_model():
    faces = []
    bw, bd, bh = 3.2, 2.2, 0.13           # base width / depth / height
    x0, z0 = -bw / 2, -bd / 2

    # --- base
    base = box((x0, 0, z0), (bw, 0, 0), (0, bh, 0), (0, 0, bd), BODY)
    faces += base
    top = (0, 1, 0)
    deck = facing(base, top)
    o = (x0, bh, z0)                       # back-left corner of the top
    ux, vz = (1, 0, 0), (0, 0, 1)
    faces.append(rect_on(o, ux, vz, 0.22, bw - 0.22, 0.18, 1.12, 0.004, top, BODY_DARK, parent=deck))
    for r in range(5):                     # key rows
        v = 0.26 + r * 0.17
        faces.append(rect_on(o, ux, vz, 0.30, bw - 0.30, v, v + 0.10, 0.008, top,
                             (92, 99, 112), parent=deck))
    faces.append(rect_on(o, ux, vz, bw / 2 - 0.55, bw / 2 + 0.55, 1.30, 1.98, 0.004, top,
                         (160, 168, 181), parent=deck))  # trackpad

    # --- lid, hinged at the back edge of the base
    a = math.radians(LID_OPEN - 90)        # tilt back from vertical
    up = (0, math.cos(a), -math.sin(a))    # along the lid
    fwd = (0, math.sin(a), math.cos(a))    # screen normal
    th, lh = 0.08, 2.05
    hinge = (x0, bh, z0)
    back = add(hinge, mul(fwd, -th))
    lid = box(back, (bw, 0, 0), mul(up, lh), mul(fwd, th), BODY)
    faces += lid
    front, rear = facing(lid, fwd), facing(lid, mul(fwd, -1))
    faces.append(rect_on(hinge, ux, up, 0.06, bw - 0.06, 0.06, lh - 0.06, 0.004, fwd,
                         (24, 27, 34), parent=front))    # bezel
    faces.append(rect_on(hinge, ux, up, 0.14, bw - 0.14, 0.16, lh - 0.14, 0.008, fwd,
                         SCREEN, kind="flat", parent=front))
    # code lines on screen (top to bottom)
    lines = [(0.0, 0.9), (0.2, 1.6), (0.2, 1.3), (0.4, 1.9), (0.4, 1.1), (0.2, 0.7), (0.0, 0.5)]
    for i, (ind, ln) in enumerate(lines):
        v = lh - 0.42 - i * 0.22
        faces.append(rect_on(hinge, ux, up, 0.38 + ind, 0.38 + ind + ln, v, v + 0.09, 0.012,
                             fwd, CODE[i % len(CODE)], kind="flat", parent=front))
    # cursor
    faces.append(rect_on(hinge, ux, up, 1.0, 1.08, lh - 0.42 - 6 * 0.22, lh - 0.42 - 6 * 0.22 + 0.09,
                         0.012, fwd, "#e6edf3", kind="flat", parent=front))
    # small logo dot on the back of the lid
    back_n = mul(fwd, -1)
    faces.append(rect_on(back, ux, up, bw / 2 - 0.14, bw / 2 + 0.14, lh / 2 - 0.14, lh / 2 + 0.14,
                         0.004, back_n, (205, 211, 220), parent=rear))

    # centre the model vertically around the rotation pivot
    cy = 0.9
    for f in faces:
        f.pts = [(p[0], p[1] - cy, p[2] + 0.1) for p in f.pts]
    return faces


# ---------------------------------------------------------------- projection
def view(p, theta, bob):
    c, s = math.cos(theta), math.sin(theta)
    x, y, z = c * p[0] + s * p[2], p[1], -s * p[0] + c * p[2]       # rotate Y
    e = math.radians(ELEVATION)
    ce, se = math.cos(e), math.sin(e)
    y, z = ce * y - se * z, se * y + ce * z                         # look down from above
    return (x, y + bob, z)


def project(p):
    k = FOCAL / (CAM_DIST - p[2])
    return (W / 2 + p[0] * k, H * 0.46 - p[1] * k)


def shade(rgb, n):
    i = 0.38 + 0.62 * max(0.0, dot(n, LIGHT))
    spec = max(0.0, dot(n, norm(add(LIGHT, (0, 0, 1))))) ** 24 * 0.35
    c = [min(255, int(ch * i + 255 * spec)) for ch in rgb]
    return "#%02x%02x%02x" % tuple(c)


def facing_cam(f, t):
    """>0 when face (or its parent) faces the camera at loop time t in [0, 1]."""
    g = f.parent or f
    vp = [view(p, 2 * math.pi * t, bob_at(t)) for p in g.pts[:3]]
    n = cross(sub(vp[1], vp[0]), sub(vp[2], vp[0]))
    return dot(n, sub((0, 0, CAM_DIST), vp[0]))


def crossings(f, n=FRAMES):
    """Loop times where the face turns edge-on (visibility flips), found by bisection."""
    out = []
    for i in range(n):
        a, b = i / n, (i + 1) / n
        fa, fb = facing_cam(f, a), facing_cam(f, b)
        if (fa > 0) != (fb > 0):
            for _ in range(40):
                m = (a + b) / 2
                if (facing_cam(f, m) > 0) == (fa > 0):
                    a = m
                else:
                    b = m
            out.append((a + b) / 2)
    return out


def face_at(f, t):
    vp = [view(p, 2 * math.pi * t, bob_at(t)) for p in f.pts]
    n = norm(cross(sub(vp[1], vp[0]), sub(vp[2], vp[0])))
    pts = " ".join("%.1f,%.1f" % project(p) for p in vp)
    return pts, (f.color if f.kind == "flat" else shade(f.color, n))


def frame(faces, theta, bob):
    """Per face: (points string, fill, visible)."""
    out = []
    cam = (0, 0, CAM_DIST)
    for f in faces:
        vp = [view(p, theta, bob) for p in f.pts]
        n = norm(cross(sub(vp[1], vp[0]), sub(vp[2], vp[0])))
        centre = mul(add(add(vp[0], vp[1]), add(vp[2], vp[3])), 0.25)
        visible = facing_cam(f, (theta / (2 * math.pi)) % 1) > 0
        pts = " ".join("%.1f,%.1f" % project(p) for p in vp)
        if f.kind == "flat":
            fill = f.color
        else:
            fill = shade(f.color, n)
        out.append((pts, fill, visible))
    return out


# ---------------------------------------------------------------- SVG output
HEAD = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs>
  <radialGradient id="sh"><stop offset="0" stop-color="#000" stop-opacity=".35"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
  <radialGradient id="glow"><stop offset="0" stop-color="#58a6ff" stop-opacity=".22"/><stop offset="1" stop-color="#58a6ff" stop-opacity="0"/></radialGradient>
</defs>
<style>
  .e{{stroke:#0b0e13;stroke-opacity:.18;stroke-width:.6;stroke-linejoin:round}}
  #glow{{opacity:0}}
  @media (prefers-color-scheme: dark){{ #shadow{{opacity:.55}} #glow{{opacity:1}} }}
</style>
'''


def bob_at(t):
    return BOB * math.sin(2 * math.pi * BOB_CYCLES * t)


def animated_svg(faces):
    kt = ";".join("%.4g" % (i / FRAMES) for i in range(FRAMES + 1))
    dur = f'dur="{DURATION}s" repeatCount="indefinite" keyTimes="{kt}"'
    parts = [HEAD]

    # floating shadow + soft glow
    rx = ";".join("%.1f" % (150 - 40 * (bob_at(i / FRAMES) / BOB)) for i in range(FRAMES + 1))
    op = ";".join("%.2f" % (0.85 - 0.3 * (bob_at(i / FRAMES) / BOB)) for i in range(FRAMES + 1))
    parts.append(f'<ellipse id="glow" cx="{W/2}" cy="{H-38}" rx="200" ry="150" fill="url(#glow)"/>')
    parts.append(f'<g id="shadow"><ellipse cx="{W/2}" cy="{H-38}" rx="150" ry="16" fill="url(#sh)">'
                 f'<animate attributeName="rx" values="{rx}" {dur}/>'
                 f'<animate attributeName="opacity" values="{op}" {dur}/></ellipse></g>')

    loop = f'dur="{DURATION}s" repeatCount="indefinite"'
    fmt = lambda ts: ";".join("%.5f" % t for t in ts)
    for f in faces:
        cross_t = crossings(f)
        if not cross_t and facing_cam(f, 0) <= 0:
            continue                                   # never visible
        # shape/colour keyframes: regular steps plus the exact edge-on moments
        ts = sorted(set([i / FRAMES for i in range(FRAMES + 1)] + cross_t))
        states = [face_at(f, t) for t in ts]
        pts = [st[0] for st in states]
        fills = [st[1] for st in states]
        # visibility switches exactly when the face is edge-on
        seg = [0.0] + cross_t
        ends = cross_t + [1.0]
        vis = ["1" if facing_cam(f, (a + b) / 2) > 0 else "0" for a, b in zip(seg, ends)]
        cls = ' class="e"' if f.stroke else ""
        attrs = f'points="{pts[0]}" fill="{fills[0]}" opacity="{vis[0]}"'
        anim = f'<animate attributeName="points" values="{";".join(pts)}" keyTimes="{fmt(ts)}" {loop}/>'
        if len(set(fills)) > 1:
            anim += f'<animate attributeName="fill" values="{";".join(fills)}" keyTimes="{fmt(ts)}" {loop}/>'
        if len(set(vis)) > 1:
            anim += (f'<animate attributeName="opacity" values="{";".join(vis)}" '
                     f'keyTimes="{fmt(seg)}" calcMode="discrete" {loop}/>')
        parts.append(f'<polygon{cls} {attrs}>{anim}</polygon>')
    parts.append("</svg>\n")
    return "\n".join(parts)


def still_svg(faces, deg):
    t = (deg % 360) / 360
    fr = frame(faces, math.radians(deg), bob_at(t))
    parts = [HEAD,
             f'<ellipse id="glow" cx="{W/2}" cy="{H-38}" rx="200" ry="150" fill="url(#glow)"/>',
             f'<g id="shadow"><ellipse cx="{W/2}" cy="{H-38}" rx="{150 - 40 * bob_at(t) / BOB:.1f}" ry="16" fill="url(#sh)"/></g>']
    for f, (pts, fill, vis) in zip(faces, fr):
        if vis:
            cls = ' class="e"' if f.stroke else ""
            parts.append(f'<polygon{cls} points="{pts}" fill="{fill}"/>')
    parts.append("</svg>\n")
    return "\n".join(parts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="laptop.svg")
    ap.add_argument("--still", type=float, nargs="*", help="write static frames at these angles")
    a = ap.parse_args()
    model = build_model()
    if a.still is not None:
        for d in a.still:
            name = f"still_{int(d):03d}.svg"
            open(name, "w").write(still_svg(model, d))
            print("wrote", name)
    else:
        svg = animated_svg(model)
        open(a.out, "w").write(svg)
        print(f"wrote {a.out} ({len(svg) / 1024:.0f} KB)")
