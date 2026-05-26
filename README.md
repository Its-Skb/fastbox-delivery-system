# FastBox Delivery System

This submission simulates one day of package delivery operations and writes a
JSON report containing each agent's delivery count, total distance traveled,
distance-per-delivery efficiency, and the most efficient agent.

## Running the program

Only Python's standard library is required. Run the simulator with an input
file and optional report destination:

```powershell
python delivery_system.py data.json
python delivery_system.py data.json --output report.json
```

The input may use either format found in the provided assignment files:

- Object mappings such as `"agents": {"A1": [5, 5]}` and package key
  `"warehouse"`.
- Lists such as `"agents": [{"id": "A1", "location": [5, 5]}]` and package
  key `"warehouse_id"` (the supplied `base_case.json` format).

## Assumptions and decisions

The assignment leaves route order and several edge cases unspecified. The
following deterministic rules are used:

1. A package is assigned to the agent whose **starting location** is nearest
   to its warehouse, using Euclidean distance as requested.
2. Each package is delivered as a direct independent trip:
   `agent starting location -> warehouse -> package destination`. The brief
   does not provide vehicle capacity, package batching, return trips, or a
   multi-stop route ordering rule, so no such behavior is assumed.
3. If agents are equally near a warehouse, the alphabetically smaller agent
   id is selected (for example, `A1` before `A2`).
4. Efficiency means average distance per delivered package. Smaller values
   are better; agents delivering no packages have `null` efficiency and
   cannot be `best_agent`.
5. Values written to the report are rounded to two decimal places for the
   readable decimal report format shown in the assignment.
6. Invalid references, duplicate ids, malformed coordinates, empty warehouse
   or agent sets, and malformed JSON cause a clear input error instead of
   silently producing an incorrect report.

## Testing

Run the included unit tests:

```powershell
python -m unittest discover -s tests -v
```

Example run against one supplied test file:

```powershell
python delivery_system.py "test_case_1.json" --output report.json
```
