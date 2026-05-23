from __future__ import annotations

import json
import math
import os
import sys

import requests

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("USERNAME", "acetodani")

COLORS = ["#f0f0f0", "#F5CD2F", "#00852B", "#006CB7", "#E3000B"]
RADAR_COLOR = "#006CB7"
TEXT_COLOR = "#1a1a1a"

CANVAS_W = 1280
CANVAS_H = 830


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
    num_weeks = len(weeks)

    cell_size = 14
    gap = 2
    step = cell_size + gap

    iso_x_week = step * math.cos(math.radians(30))
    iso_y_week = step * math.sin(math.radians(30))
    iso_x_day = -step * math.cos(math.radians(30))
    iso_y_day = step * math.sin(math.radians(30))

    grid_width = num_weeks * iso_x_week + 7 * abs(iso_x_day)
    origin_x = 7 * abs(iso_x_day) + 40
    origin_y = 180

    elements = []

    for wi in range(num_weeks):
        for di in range(len(weeks[wi]["contributionDays"])):
            day = weeks[wi]["contributionDays"][di]
            count = day["contributionCount"]
            level = level_from_str(day["contributionLevel"])

            height = math.log10(count / 20 + 1) * 100 + 2 if count > 0 else 2

            x = origin_x + wi * iso_x_week + di * iso_x_day
            y = origin_y + wi * iso_y_week + di * iso_y_day

            color = COLORS[level]
            color_left = darken(color, 0.82)
            color_right = darken(color, 0.65)

            # Draw 3D block as three polygons (top, left, right)
            w = cell_size * math.cos(math.radians(30))
            h_iso = cell_size * math.sin(math.radians(30))

            # Top face (parallelogram)
            top_points = [
                (x, y - height),
                (x + w, y - h_iso - height),
                (x + 2 * w, y - height),
                (x + w, y + h_iso - height),
            ]
            top_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in top_points)

            # Left face
            left_points = [
                (x, y - height),
                (x + w, y + h_iso - height),
                (x + w, y + h_iso),
                (x, y),
            ]
            left_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in left_points)

            # Right face
            right_points = [
                (x + w, y + h_iso - height),
                (x + 2 * w, y - height),
                (x + 2 * w, y),
                (x + w, y + h_iso),
            ]
            right_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in right_points)

            anim_dur = "3s"
            g = ""
            g += f'<polygon points="{top_str}" fill="{color}" stroke="none">'
            g += f'<animate attributeName="opacity" values="0;1" dur="{anim_dur}" fill="freeze"/>'
            g += '</polygon>'
            g += f'<polygon points="{left_str}" fill="{color_left}" stroke="none">'
            g += f'<animate attributeName="opacity" values="0;1" dur="{anim_dur}" fill="freeze"/>'
            g += '</polygon>'
            g += f'<polygon points="{right_str}" fill="{color_right}" stroke="none">'
            g += f'<animate attributeName="opacity" values="0;1" dur="{anim_dur}" fill="freeze"/>'
            g += '</polygon>'

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

    # Grid pentagons
    for lv in range(1, levels + 1):
        points = " ".join(f"{pos(lv, i)[0]:.1f},{pos(lv, i)[1]:.1f}" for i in range(5))
        elements.append(
            f'<polygon points="{points}" fill="none" stroke="#999999" '
            f'stroke-width="0.8" stroke-dasharray="4,4"/>'
        )

    # Axis lines
    for i in range(5):
        x, y = pos(levels, i)
        elements.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="#999999" stroke-width="0.8"/>'
        )

    # Scale labels
    scale_labels = ["1", "10", "100", "1K", "10K"]
    for lv in range(1, levels + 1):
        lx, ly = pos(lv, 0)
        elements.append(
            f'<text x="{lx + 5:.1f}" y="{ly:.1f}" font-size="11" '
            f'fill="#666666" text-anchor="start" '
            f'font-family="sans-serif">{scale_labels[lv-1]}</text>'
        )

    # Data polygon
    data_points = []
    for i, (_, value) in enumerate(axes):
        level = min(levels, math.log10(max(1, value)) if value > 0 else 0)
        data_points.append(pos(level, i))

    points_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in data_points)
    elements.append(
        f'<polygon points="{points_str}" fill="{RADAR_COLOR}" fill-opacity="0.35" '
        f'stroke="{RADAR_COLOR}" stroke-width="2">'
        f'<animate attributeName="fill-opacity" values="0;0.35" dur="3s" fill="freeze"/>'
        f'</polygon>'
    )

    # Axis labels
    for i, (name, _) in enumerate(axes):
        x, y = pos(levels, i)
        dx = x - cx
        dy_val = y - cy
        length = math.sqrt(dx * dx + dy_val * dy_val)
        if length > 0:
            lx = x + (dx / length) * 25
            ly = y + (dy_val / length) * 25
        else:
            lx, ly = x, y - 25

        anchor = "middle"
        if lx < cx - 30:
            anchor = "end"
        elif lx > cx + 30:
            anchor = "start"

        elements.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="16" font-weight="bold" '
            f'fill="{TEXT_COLOR}" text-anchor="{anchor}" '
            f'dominant-baseline="middle" font-family="sans-serif">{name}</text>'
        )

    return "\n".join(elements)


def generate_svg(data: dict) -> str:
    user = data["user"]
    collection = user["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    first_date = weeks[0]["contributionDays"][0]["date"]
    last_week = weeks[-1]["contributionDays"]
    last_date = last_week[-1]["date"]

    blocks_svg = generate_3d_blocks(weeks)
    radar_svg = generate_radar(collection)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">
<style>
  text {{ font-family: "Ubuntu", "Helvetica", "Arial", sans-serif; }}
</style>
<g>
{blocks_svg}
</g>
<g>
{radar_svg}
</g>
<text x="{CANVAS_W - 20}" y="24" font-size="14" fill="#666666" text-anchor="end">{first_date} / {last_date}</text>
<text x="40" y="{CANVAS_H - 30}" font-size="28" font-weight="bold" fill="{TEXT_COLOR}">{total}<tspan dx="8" font-size="18" font-weight="normal">contributions</tspan></text>
</svg>'''

    return svg


def main():
    data = fetch_contributions()
    os.makedirs("profile-3d-contrib", exist_ok=True)
    svg = generate_svg(data)
    with open("profile-3d-contrib/profile-custom.svg", "w") as f:
        f.write(svg)
    print("Generated profile-3d-contrib/profile-custom.svg")


if __name__ == "__main__":
    main()
