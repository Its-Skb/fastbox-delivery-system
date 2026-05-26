import json
import tempfile
import unittest
from pathlib import Path

from delivery_system import (
    DataValidationError,
    create_report,
    distance,
    load_data,
    simulate_delivery,
)


class DeliverySystemTests(unittest.TestCase):
    def test_distance_is_euclidean(self) -> None:
        self.assertEqual(distance((0.0, 0.0), (3.0, 4.0)), 5.0)

    def test_assignment_distance_efficiency_and_idle_agent(self) -> None:
        report = simulate_delivery(
            {"W1": (0.0, 0.0), "W2": (10.0, 0.0)},
            {"A1": (0.0, 0.0), "A2": (10.0, 0.0), "A3": (100.0, 100.0)},
            [
                {"id": "P1", "warehouse": "W1", "destination": (3.0, 4.0)},
                {"id": "P2", "warehouse": "W1", "destination": (0.0, 2.0)},
                {"id": "P3", "warehouse": "W2", "destination": (10.0, 8.0)},
            ],
        )

        self.assertEqual(
            report["A1"],
            {"packages_delivered": 2, "total_distance": 7.0, "efficiency": 3.5},
        )
        self.assertEqual(
            report["A2"],
            {"packages_delivered": 1, "total_distance": 8.0, "efficiency": 8.0},
        )
        self.assertEqual(
            report["A3"],
            {"packages_delivered": 0, "total_distance": 0.0, "efficiency": None},
        )
        self.assertEqual(report["best_agent"], "A1")

    def test_equal_distance_tie_is_resolved_by_agent_id(self) -> None:
        report = simulate_delivery(
            {"W1": (1.0, 0.0)},
            {"A2": (2.0, 0.0), "A1": (0.0, 0.0)},
            [{"id": "P1", "warehouse": "W1", "destination": (1.0, 0.0)}],
        )
        self.assertEqual(report["A1"]["packages_delivered"], 1)
        self.assertEqual(report["A2"]["packages_delivered"], 0)

    def test_loads_list_based_base_case_schema_and_writes_output(self) -> None:
        data = {
            "warehouses": [{"id": "W1", "location": [0, 0]}],
            "agents": [{"id": "A1", "location": [0, 0]}],
            "packages": [
                {"id": "P1", "warehouse_id": "W1", "destination": [3, 4]}
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            input_path = Path(folder) / "input.json"
            output_path = Path(folder) / "report.json"
            input_path.write_text(json.dumps(data), encoding="utf-8")

            warehouses, agents, packages = load_data(input_path)
            report = create_report(input_path, output_path)

            self.assertEqual(warehouses, {"W1": (0.0, 0.0)})
            self.assertEqual(agents, {"A1": (0.0, 0.0)})
            self.assertEqual(packages[0]["warehouse"], "W1")
            self.assertEqual(report["A1"]["total_distance"], 5.0)
            self.assertEqual(json.loads(output_path.read_text()), report)

    def test_unknown_warehouse_is_rejected(self) -> None:
        data = {
            "warehouses": {"W1": [0, 0]},
            "agents": {"A1": [0, 0]},
            "packages": [{"id": "P1", "warehouse": "missing", "destination": [1, 1]}],
        }
        with tempfile.TemporaryDirectory() as folder:
            input_path = Path(folder) / "invalid.json"
            input_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(DataValidationError):
                load_data(input_path)


if __name__ == "__main__":
    unittest.main()
