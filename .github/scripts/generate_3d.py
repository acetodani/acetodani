from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone

import requests

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("USERNAME", "acetodani")

COLORS = ["#f0f0f0", "#F5CD2F", "#00852B", "#006CB7", "#E3000B"]
RADAR_COLOR = "#006CB7"
TEXT_COLOR = "#1a1a1a"

CANVAS_W = 1280
CANVAS_H = 520


def graphql(query: str) -> dict:
    r = requests.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {TOKEN}"},
        json={"query": query},
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        print(json.dumps(data["errors"], indent=2), file=sys.stderr)
        sys.exit(1)
    return data["data"]


def fetch_contributions() -> dict:
    query = """
    {
      user(login: "%s") {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                contributionLevel
                date
              }
            }
          }
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalRepositoryContributions
        }
      }
    }
    """ % USERNAME
    return graphql(query)


def level_from_str(s: str) -> int:
    mapping = {
        "NONE": 0,
        "FIRST_QUARTILE": 1,
        "SECOND_QUARTILE": 2,
        "THIRD_QUARTILE": 3,
        "FOURTH_QUARTILE": 4,
    }
    return mapping.get(s, 0)


def darken(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def generate_3d_blocks(weeks: list) -> str:
    dx = CANVAS_W / 64
    dy = dx * math.tan(math.radians(30))
    dxx = dx * 0.9
    dyy = dy * 0.9

    skew_angle = math.degrees(math.atan2(dxx / 2, dyy))
    scale_y = math.cos(math.atan2(dxx / 2, dyy))

    elements = []
    base_x = 120
    base_y = CANVAS_H - 80

    for wi, week in enumerate(weeks):
        for di, day in enumerate(week["contributionDays"]):
            count = day["contributionCount"]
            level = level_from_str(day["contributionLevel"])

            height = math.log10(count / 20 + 1) * 144 + 3 if count > 0 else 3

            x = base_x + wi * dxx - di * dxx
            y = base_y + wi * dyy / 2 + di * dyy / 2

            color = COLORS[level]
            color_left = darken(color, 0.85)
            color_right = darken(color, 0.7)

            top_transform = f"skewY(-30) skewX({skew_angle:.2f}) scale(1 {scale_y:.4f})"
            left_transform = f"skewY(30) scale(1 {1:.4f})"
            right_transform = f"translate({dxx:.2f} {dyy/2:.2f}) skewY(-30) scale(1 {1:.4f})"

            g = f'<g transform="translate({x:.2f} {y - height:.2f})">'

            # Top face
            g += f'<rect stroke="none" x="0" y="0" width="{dxx:.2f}" height="{dxx:.2f}" '
            g += f'transform="{top_transform}" fill="{color}">'
            g += f'<animate attributeName="height" from="{dxx:.2f}" to="{dxx:.2f}" dur="3s"/>'
            g += '</rect>'

            # Left face
            g += f'<rect stroke="none" x="0" y="0" width="{dxx:.2f}" height="{height:.2f}" '
            g += f'transform="{left_transform}" fill="{color_left}">'
            g += f'<animate attributeName="height" from="3" to="{height:.2f}" dur="3s"/>'
            g += '</rect>'

            # Right face
            g += f'<rect stroke="none" x="0" y="0" width="{dxx:.2f}" height="{height:.2f}" '
            g += f'transform="{right_transform}" fill="{color_right}">'
            g += f'<animate attributeName="height" from="3" to="{height:.2f}" dur="3s"/>'
            g += '</rect>'

            g += '</g>'
            elements.append(g)

    return "\n".join(elements)


def generate_radar(totals: dict) -> str:
    cx, cy = 1020, 250
    radius = 150
    levels = 5
    axes = [
        ("Commit", totals["totalCommitContributions"]),
        ("Issue", totals["totalIssueContributions"]),
        ("PullReq", totals["totalPullRequestContributions"]),
        ("Review", totals["totalPullRequestReviewContributions"]),
        ("Repo", totals["totalRepositoryContributions"]),
    ]

    def pos(level: float, axis_idx: int) -> tuple[float, float]:
        angle = (axis_idx / 5) * 2 * math.pi - math.pi / 2
        r = radius * (level / levels)
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    elements = []

    # Grid lines (pentagons at each level)
    for lv in range(1, levels + 1):
        points = " ".join(f"{pos(lv, i)[0]:.1f},{pos(lv, i)[1]:.1f}" for i in range(5))
        elements.append(
            f'<polygon points="{points}" fill="none" stroke="#cccccc" '
            f'stroke-width="1" stroke-dasharray="4,4"/>'
        )

    # Axis lines
    for i in range(5):
        x, y = pos(levels, i)
        elements.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="#cccccc" stroke-width="1"/>'
        )

    # Scale labels
    scale_labels = ["1", "10", "100", "1K", "10K"]
    for lv in range(1, levels + 1):
        lx, ly = pos(lv, 0)
        elements.append(
            f'<text x="{lx:.1f}" y="{ly - 5:.1f}" font-size="11" '
            f'fill="#999999" text-anchor="middle" '
            f'font-family="sans-serif">{scale_labels[lv-1]}</text>'
        )

    # Data polygon
    data_points = []
    for i, (_, value) in enumerate(axes):
        level = min(levels, math.log10(max(1, value)))
        data_points.append(pos(level, i))

    points_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in data_points)
    elements.append(
        f'<polygon points="{points_str}" fill="{RADAR_COLOR}" fill-opacity="0.4" '
        f'stroke="{RADAR_COLOR}" stroke-width="2">'
        f'<animate attributeName="fill-opacity" values="0;0.4" dur="3s" repeatCount="1"/>'
        f'</polygon>'
    )

    # Axis labels
    label_offset = 25
    for i, (name, _) in enumerate(axes):
        x, y = pos(levels, i)
        dx = x - cx
        dy_val = y - cy
        length = math.sqrt(dx * dx + dy_val * dy_val)
        if length > 0:
            lx = x + (dx / length) * label_offset
            ly = y + (dy_val / length) * label_offset
        else:
            lx, ly = x, y - label_offset

        anchor = "middle"
        if lx < cx - 20:
            anchor = "end"
        elif lx > cx + 20:
            anchor = "start"

        elements.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="16" font-weight="bold" '
            f'fill="{TEXT_COLOR}" text-anchor="{anchor}" '
            f'font-family="sans-serif">{name}</text>'
        )

    return "\n".join(elements)


def generate_svg(data: dict) -> str:
    user = data["user"]
    collection = user["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    # Date range
    first_date = weeks[0]["contributionDays"][0]["date"]
    last_week = weeks[-1]["contributionDays"]
    last_date = last_week[-1]["date"]

    blocks_svg = generate_3d_blocks(weeks)
    radar_svg = generate_radar(collection)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">
<style>
  text {{ font-family: "Ubuntu", "Helvetica", "Arial", sans-serif; }}
</style>
{blocks_svg}
{radar_svg}
<text x="{CANVAS_W - 20}" y="20" font-size="14" fill="#999999" text-anchor="end">{first_date} / {last_date}</text>
<text x="40" y="{CANVAS_H - 20}" font-size="28" font-weight="bold" fill="{TEXT_COLOR}">{total}</text>
<text x="40" y="{CANVAS_H - 20}" dx="5" font-size="28" fill="{TEXT_COLOR}"> </text>
<text x="{40 + len(str(total)) * 18}" y="{CANVAS_H - 20}" font-size="18" fill="{TEXT_COLOR}">contributions</text>
</svg>"""

    return svg


def main():
    data = fetch_contributions()

    os.makedirs("profile-3d-contrib", exist_ok=True)
    svg = generate_svg(data)

    with open("profile-3d-contrib/profile-custom.svg", "w") as f:
        f.write(svg)

    print(f"Generated profile-3d-contrib/profile-custom.svg")


if __name__ == "__main__":
    main()
