# Sample Action Tracker Excerpt (Synthetic — Documentation Only)

> **Synthetic sample excerpt for documentation only.**
> Real `outputs/action_tracker.csv` files are not committed — they are generated
> per run from synthetic data. The rows below are a curated slice for
> illustration. **No real schools, teachers, or coordinators are referenced.**

The `action_tracker.csv` ships one row per top-risk school. Every action starts
at `status=proposed` and requires **human approval** before being communicated
externally. `evidence` is built from the school's per-component risk breakdown
so a reviewer can audit "why is this action here?" without re-running anything.

## Columns

| Column              | Purpose                                                |
| ------------------- | ------------------------------------------------------ |
| `action_id`         | Stable, sequential ID (`ACT_0001`, `ACT_0002`, …)      |
| `district`          | District the action targets                            |
| `block`             | Block (matches the risk ranking)                       |
| `school_id`         | Foreign key into `schools.csv`                         |
| `school_name`       | Display name for the memo                              |
| `risk_area`         | Driver category (FLN gap, low DIKSHA usage, etc.)      |
| `recommended_action`| Concrete next step, owner-agnostic phrasing            |
| `suggested_owner`   | Role (BRC, CRC, DEO, PMU Analyst, etc.) — never a name |
| `priority`          | P1/P2/P3, derived from the school's risk band          |
| `evidence`          | Component breakdown + raw KPIs that drove the score    |
| `policy_reference`  | Mandate the action links back to                       |
| `status`            | Always starts as `proposed`                            |

## Sample rows

```csv
action_id,district,block,school_id,school_name,risk_area,recommended_action,suggested_owner,priority,evidence,policy_reference,status
ACT_0001,District Alpha,District Alpha / Sundarpur,D01_B03_C0_S08,GPS Sundarpur No.9,Learning outcome gap (FLN),"Schedule diagnostic FLN assessment and targeted re-teaching; assign an academic mentor visit within two weeks.",Block Resource Coordinator + Academic Mentor,P1,"risk_score=79.4 (High); learning_outcome=86/100; digital_usage=98/100; fln_gain=-2.6; sessions_latest=0; weeks_reported=7/8; open_critical=1",NIPUN Bharat Mission / FLN Goals,proposed
ACT_0002,District Alpha,District Alpha / Kheda,D01_B01_C0_S00,GPS Kheda No.1,Learning outcome gap (FLN),"Schedule diagnostic FLN assessment and targeted re-teaching; assign an academic mentor visit within two weeks.",Block Resource Coordinator + Academic Mentor,P1,"risk_score=74.7 (High); learning_outcome=86/100; digital_usage=95/100; fln_gain=-3.6; sessions_latest=0; weeks_reported=6/8",NIPUN Bharat Mission / FLN Goals,proposed
ACT_0006,District Alpha,District Alpha / Madhopur,D01_B05_C1_S01,GPS Madhopur No.2,Low DIKSHA usage,"Conduct a 20-minute DIKSHA model lesson on-site; verify QR-textbook coverage and device/connectivity status; pair with a high-adoption peer school in the block.",Block Resource Coordinator + Cluster Resource Coordinator (CRC),P1,"risk_score=71.5 (High); digital_usage=100/100; learning_outcome=74/100; fln_gain=0.4; sessions_latest=0; weeks_reported=6/8; open_critical=1",Digital Learning Adoption Guideline,proposed
```

## What you should notice

- **Every recommended action is paired with evidence.** The evidence column
  cites the exact component scores (learning_outcome, digital_usage, …) that
  drove the action — not an LLM opinion.
- **Owners are roles, not individuals.** Government workflows rotate; mapping
  to a role keeps the tracker durable.
- **`status=proposed` is non-negotiable.** Nothing in the project automatically
  approves an action, sends a message, or escalates.
- **`policy_reference` lets a reviewer trace the action back to the mandate.**
  The references come from `data/policy_map.yaml`, the same source the KPI
  table uses for target-vs-actual framing.

> **End of excerpt.** The tracker typically contains 10 rows (`--top-n-actions 10`
> default). See [docs/CASE_STUDY.md](../CASE_STUDY.md) for how this artifact
> would be used inside an actual district review meeting.
