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
import json
import math
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
    try:
        raw_data = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataValidationError(f"Input file not found: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"Invalid JSON in {input_path}: {exc.msg}") from exc

    if not isinstance(raw_data, dict):
        raise DataValidationError("Input data must be a JSON object.")
    warehouses = _normalize_locations(raw_data.get("warehouses"), "warehouses")
    agents = _normalize_locations(raw_data.get("agents"), "agents")
    packages = _normalize_packages(raw_data.get("packages"), warehouses)
    return warehouses, agents, packages


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
) -> dict[str, Any]:
    """Assign and deliver packages, returning the report required by the brief."""
    totals = {
        agent_id: {"packages_delivered": 0, "total_distance": 0.0}
        for agent_id in sorted(agents)
    }

    for package in packages:
        warehouse_location = warehouses[package["warehouse"]]
        agent_id, pickup_distance = nearest_agent(warehouse_location, agents)
        delivery_distance = distance(warehouse_location, package["destination"])
        totals[agent_id]["packages_delivered"] += 1
        totals[agent_id]["total_distance"] += pickup_distance + delivery_distance

    report: dict[str, Any] = {}
    for agent_id, total in totals.items():
        delivered = total["packages_delivered"]
        total_distance = total["total_distance"]
        report[agent_id] = {
            "packages_delivered": delivered,
            "total_distance": round(total_distance, 2),
            "efficiency": round(total_distance / delivered, 2) if delivered else None,
        }

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


def create_report(input_path: Path, output_path: Path) -> dict[str, Any]:
    """Run a simulation from input JSON and save its formatted JSON report."""
    warehouses, agents, packages = load_data(input_path)
    report = simulate_delivery(warehouses, agents, packages)
    output_path.write_text(json.dumps(report, indent=4) + "\n", encoding="utf-8")
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
    args = parser.parse_args()

    try:
        create_report(args.input_file, args.output)
    except DataValidationError as exc:
        parser.error(str(exc))
    print(f"Report saved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
