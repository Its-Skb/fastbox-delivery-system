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

## Bonus features

All four optional tasks are implemented. The required default workflow remains
unchanged; bonus artifacts can be generated with:

```powershell
python delivery_system.py bonus_demo.json --output bonus_report.json `
  --random-delays --seed 42 --ascii-routes routes.txt `
  --top-performer-csv top_performer.csv
```

The repository includes the resulting `bonus_report.json`, `routes.txt`, and
`top_performer.csv` files so each optional feature can be reviewed immediately.

### Random delivery delays

`--random-delays` adds a simulated integer delay of 0 to 30 minutes for each
delivery and includes `total_delay_minutes` for each agent in the JSON report.
Use `--seed` for reproducible output, and optionally use
`--max-delay-minutes` to configure the maximum delay. Delays are tracked as
operational context and do not alter the distance-based efficiency requested
in the main assignment.

### ASCII route visualization

`--ascii-routes routes.txt` generates a readable text file showing each
package's path:

```text
[P1] A1 (5, 5) --pick up--> W1 (0, 0) --deliver--> (30, 40)
```

It also records when any scheduled new agent becomes available.

### Dynamic agent joining

An input file can include agents that become available during the simulated
day. Packages are processed in their listed order; an agent joining after
`N` completed deliveries is eligible beginning with package `N + 1`.

```json
{
    "new_agents": [
        {"id": "A4", "location": [48, 75], "joins_after_deliveries": 2}
    ]
}
```

Existing assignments are not revisited when an agent joins.

### Export top performer to CSV

`--top-performer-csv top_performer.csv` writes the most efficient agent and
their final metrics to a CSV file suitable for sharing or spreadsheet review.

## Additional bonus assumptions

1. Random delays are modeled in minutes and do not change route distance.
2. Packages are processed in JSON list order for the purpose of mid-day agent
   availability.
3. A joining agent becomes eligible only for undelivered packages after its
   scheduled join point; packages already delivered are never reassigned.
4. New agents with no assigned packages still appear in the final report with
   zero deliveries, consistent with initially available idle agents.
