"""FastBox delivery-day simulator.

Assumption: the problem statement defines assignment using each agent's
starting location, but does not define a route when an agent has multiple
packages. Each delivery is therefore treated as an independent direct trip:
agent start -> package warehouse -> package destination. This keeps package
assignment and distance calculation deterministic without inventing capacity,
return-to-base, or package-order rules.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path
from typing import Any, Iterable


Point = tuple[float, float]


class DataValidationError(ValueError):
    """Raised when delivery input data is not in an accepted format."""


def _as_point(value: Any, label: str) -> Point:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise DataValidationError(f"{label} must be a two-value coordinate.")
    if not all(isinstance(coordinate, (int, float)) for coordinate in value):
        raise DataValidationError(f"{label} coordinates must be numbers.")
    return float(value[0]), float(value[1])


def _normalize_locations(raw: Any, kind: str) -> dict[str, Point]:
    """Accept document mappings and the list-of-objects base-case variant."""
    if isinstance(raw, dict):
        entries = raw.items()
    elif isinstance(raw, list):
        entries = []
        for item in raw:
            if not isinstance(item, dict) or "id" not in item or "location" not in item:
                raise DataValidationError(
                    f"Each {kind} list item must contain id and location."
                )
            entries.append((item["id"], item["location"]))
    else:
        raise DataValidationError(f"{kind} must be an object or a list.")

    locations: dict[str, Point] = {}
    for identifier, location in entries:
        if not isinstance(identifier, str) or not identifier:
            raise DataValidationError(f"Each {kind} id must be a non-empty string.")
        if identifier in locations:
            raise DataValidationError(f"Duplicate {kind} id: {identifier}.")
        locations[identifier] = _as_point(location, f"{kind} {identifier}")
    if not locations:
        raise DataValidationError(f"At least one {kind} is required.")
    return locations


def _normalize_packages(raw: Any, warehouses: dict[str, Point]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise DataValidationError("packages must be a list.")

    packages: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise DataValidationError("Each package must be an object.")
        package_id = item.get("id")
        warehouse_id = item.get("warehouse", item.get("warehouse_id"))
        if not isinstance(package_id, str) or not package_id:
            raise DataValidationError("Each package id must be a non-empty string.")
        if package_id in seen_ids:
            raise DataValidationError(f"Duplicate package id: {package_id}.")
        if warehouse_id not in warehouses:
            raise DataValidationError(
                f"Package {package_id} references unknown warehouse: {warehouse_id}."
            )
        packages.append(
            {
                "id": package_id,
                "warehouse": warehouse_id,
                "destination": _as_point(
                    item.get("destination"), f"package {package_id} destination"
                ),
            }
        )
        seen_ids.add(package_id)
    return packages


def load_data(input_path: Path) -> tuple[dict[str, Point], dict[str, Point], list[dict[str, Any]]]:
    """Read JSON input and return normalized warehouse, agent, and package data."""
    raw_data = _read_json(input_path)
    warehouses = _normalize_locations(raw_data.get("warehouses"), "warehouses")
    agents = _normalize_locations(raw_data.get("agents"), "agents")
    packages = _normalize_packages(raw_data.get("packages"), warehouses)
    return warehouses, agents, packages


def _read_json(input_path: Path) -> dict[str, Any]:
    try:
        raw_data = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataValidationError(f"Input file not found: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"Invalid JSON in {input_path}: {exc.msg}") from exc

    if not isinstance(raw_data, dict):
        raise DataValidationError("Input data must be a JSON object.")
    return raw_data


def load_new_agents(input_path: Path, agents: dict[str, Point]) -> list[dict[str, Any]]:
    """Load optional agents that become eligible after completed deliveries."""
    raw_new_agents = _read_json(input_path).get("new_agents", [])
    if not isinstance(raw_new_agents, list):
        raise DataValidationError("new_agents must be a list.")

    new_agents: list[dict[str, Any]] = []
    known_ids = set(agents)
    for item in raw_new_agents:
        if not isinstance(item, dict):
            raise DataValidationError("Each new agent must be an object.")
        agent_id = item.get("id")
        joining_after = item.get("joins_after_deliveries")
        if not isinstance(agent_id, str) or not agent_id:
            raise DataValidationError("Each new agent id must be a non-empty string.")
        if agent_id in known_ids:
            raise DataValidationError(f"Duplicate agents id: {agent_id}.")
        if not isinstance(joining_after, int) or joining_after < 0:
            raise DataValidationError(
                f"new agent {agent_id} joins_after_deliveries must be a non-negative integer."
            )
        new_agents.append(
            {
                "id": agent_id,
                "location": _as_point(item.get("location"), f"new agent {agent_id}"),
                "joins_after_deliveries": joining_after,
            }
        )
        known_ids.add(agent_id)
    return sorted(new_agents, key=lambda item: (item["joins_after_deliveries"], item["id"]))


def distance(first: Point, second: Point) -> float:
    """Calculate the Euclidean distance between two coordinates."""
    return math.hypot(first[0] - second[0], first[1] - second[1])


def nearest_agent(
    warehouse_location: Point, agents: dict[str, Point]
) -> tuple[str, float]:
    """Return nearest agent; lexical id order resolves equal-distance ties."""
    return min(
        (
            (agent_id, distance(agent_location, warehouse_location))
            for agent_id, agent_location in agents.items()
        ),
        key=lambda result: (result[1], result[0]),
    )


def simulate_delivery(
    warehouses: dict[str, Point],
    agents: dict[str, Point],
    packages: Iterable[dict[str, Any]],
    *,
    new_agents: Iterable[dict[str, Any]] = (),
    random_delays: bool = False,
    delay_seed: int | None = None,
    max_delay_minutes: int = 30,
    route_lines: list[str] | None = None,
) -> dict[str, Any]:
    """Assign and deliver packages, returning the report required by the brief."""
    if max_delay_minutes < 0:
        raise DataValidationError("max_delay_minutes cannot be negative.")
    scheduled_agents = list(new_agents)
    available_agents = dict(agents)
    totals = {
        agent_id: {"packages_delivered": 0, "total_distance": 0.0}
        for agent_id in sorted([*agents, *(agent["id"] for agent in scheduled_agents)])
    }
    if random_delays:
        for total in totals.values():
            total["total_delay_minutes"] = 0
    delay_generator = random.Random(delay_seed)

    for completed_deliveries, package in enumerate(packages):
        for joining_agent in scheduled_agents:
            if (
                joining_agent["id"] not in available_agents
                and joining_agent["joins_after_deliveries"] <= completed_deliveries
            ):
                available_agents[joining_agent["id"]] = joining_agent["location"]
                if route_lines is not None:
                    route_lines.append(
                        f"[JOIN] {joining_agent['id']} becomes available at "
                        f"{_format_point(joining_agent['location'])} after "
                        f"{completed_deliveries} completed deliveries."
                    )
        warehouse_location = warehouses[package["warehouse"]]
        agent_id, pickup_distance = nearest_agent(warehouse_location, available_agents)
        delivery_distance = distance(warehouse_location, package["destination"])
        totals[agent_id]["packages_delivered"] += 1
        totals[agent_id]["total_distance"] += pickup_distance + delivery_distance
        delay_minutes = (
            delay_generator.randint(0, max_delay_minutes) if random_delays else None
        )
        if delay_minutes is not None:
            totals[agent_id]["total_delay_minutes"] += delay_minutes
        if route_lines is not None:
            delay_text = f" | delay: {delay_minutes} min" if delay_minutes is not None else ""
            route_lines.append(
                f"[{package['id']}] {agent_id} {_format_point(available_agents[agent_id])}"
                f" --pick up--> {package['warehouse']} {_format_point(warehouse_location)}"
                f" --deliver--> {_format_point(package['destination'])}"
                f" | distance: {pickup_distance + delivery_distance:.2f}{delay_text}"
            )

    report: dict[str, Any] = {}
    for agent_id, total in totals.items():
        delivered = total["packages_delivered"]
        total_distance = total["total_distance"]
        report[agent_id] = {
            "packages_delivered": delivered,
            "total_distance": round(total_distance, 2),
            "efficiency": round(total_distance / delivered, 2) if delivered else None,
        }
        if random_delays:
            report[agent_id]["total_delay_minutes"] = total["total_delay_minutes"]

    eligible_agents = [
        agent_id for agent_id, total in totals.items() if total["packages_delivered"] > 0
    ]
    report["best_agent"] = (
        min(
            eligible_agents,
            key=lambda agent_id: (
                totals[agent_id]["total_distance"]
                / totals[agent_id]["packages_delivered"],
                agent_id,
            ),
        )
        if eligible_agents
        else None
    )
    return report


def _format_point(point: Point) -> str:
    return f"({point[0]:g}, {point[1]:g})"


def export_top_performer(report: dict[str, Any], csv_path: Path) -> None:
    """Save best agent metrics in a compact CSV artifact."""
    best_agent = report["best_agent"]
    fields = ["agent_id", "packages_delivered", "total_distance", "efficiency"]
    if best_agent is not None and "total_delay_minutes" in report[best_agent]:
        fields.append("total_delay_minutes")
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        if best_agent is not None:
            writer.writerow({"agent_id": best_agent, **report[best_agent]})


def create_report(
    input_path: Path,
    output_path: Path,
    *,
    random_delays: bool = False,
    delay_seed: int | None = None,
    max_delay_minutes: int = 30,
    routes_output: Path | None = None,
    csv_output: Path | None = None,
) -> dict[str, Any]:
    """Run a simulation from input JSON and save its formatted JSON report."""
    warehouses, agents, packages = load_data(input_path)
    new_agents = load_new_agents(input_path, agents)
    route_lines: list[str] | None = [] if routes_output is not None else None
    report = simulate_delivery(
        warehouses,
        agents,
        packages,
        new_agents=new_agents,
        random_delays=random_delays,
        delay_seed=delay_seed,
        max_delay_minutes=max_delay_minutes,
        route_lines=route_lines,
    )
    output_path.write_text(json.dumps(report, indent=4) + "\n", encoding="utf-8")
    if routes_output is not None and route_lines is not None:
        routes_output.write_text(
            "FASTBOX ASCII ROUTE VISUALIZATION\n"
            "=================================\n"
            + "\n".join(route_lines)
            + "\n",
            encoding="utf-8",
        )
    if csv_output is not None:
        export_top_performer(report, csv_output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate FastBox package deliveries.")
    parser.add_argument(
        "input_file",
        nargs="?",
        default="data.json",
        type=Path,
        help="JSON input file (default: data.json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=Path("report.json"),
        type=Path,
        help="Path for the JSON report (default: report.json).",
    )
    parser.add_argument(
        "--random-delays",
        action="store_true",
        help="Simulate random delay minutes for delivered packages.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed used with --random-delays to make a simulation reproducible.",
    )
    parser.add_argument(
        "--max-delay-minutes",
        type=int,
        default=30,
        help="Largest possible per-package delay when delays are enabled (default: 30).",
    )
    parser.add_argument(
        "--ascii-routes",
        type=Path,
        help="Save a text visualization of each assigned delivery route.",
    )
    parser.add_argument(
        "--top-performer-csv",
        type=Path,
        help="Export the most efficient agent's metrics to a CSV file.",
    )
    args = parser.parse_args()

    try:
        create_report(
            args.input_file,
            args.output,
            random_delays=args.random_delays,
            delay_seed=args.seed,
            max_delay_minutes=args.max_delay_minutes,
            routes_output=args.ascii_routes,
            csv_output=args.top_performer_csv,
        )
    except DataValidationError as exc:
        parser.error(str(exc))
    print(f"Report saved to {args.output}")
    if args.ascii_routes:
        print(f"ASCII routes saved to {args.ascii_routes}")
    if args.top_performer_csv:
        print(f"Top performer saved to {args.top_performer_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
