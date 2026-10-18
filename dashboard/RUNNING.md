# Run the integrated OLAP dashboard

The seven approved statements are selected directly from the existing root
`olap_queries_optimized.sql`, without changing analytical SQL. No dependencies
were added. The importer, schema, ETL, indexes, and analytical SQL are unchanged.

## Windows CMD

```cmd
cd /d C:\Users\Gab\Documents\GitHub\STADVDB-MCO1-NYC-Taxi
python -m pip install -r requirements.txt
python -m streamlit run dashboard/app.py --server.port 8501
```

Open http://127.0.0.1:8501. If that port is occupied, leave its service alone and
use `--server.port 8502`, then open http://127.0.0.1:8502. Verification found an
existing Windows system listener on 8501; the dashboard launched on 8502.

## Private database configuration

The app reads root `.env` and environment variables. Existing `DB_*` settings are
reused; `DASHBOARD_DB_*` overrides allow an independent reporting login. `DB_TABLE`
is unused. No raw source tables are reporting inputs. Environment variables take
precedence over the file. This app does not read `st.secrets`.

Have your administrator provide a dedicated account with direct SELECT grants
on all six warehouse tables, without write, administrative, role, or grant
privileges. The app inspects its own `SHOW GRANTS` locally and refuses privileges
it cannot verify, including role grants. It refuses root for live reports.
No users or grants are created automatically. All reads use read-only transactions.

Set these privately, using the supplied login:

```dotenv
DASHBOARD_DB_USER=your_read_only_login
DASHBOARD_DB_PASSWORD=your_private_password
DASHBOARD_DB_NAME=source_db
DASHBOARD_CONNECT_TIMEOUT_SECONDS=5
DASHBOARD_READ_TIMEOUT_SECONDS=7200
DASHBOARD_WRITE_TIMEOUT_SECONDS=30
```

Each timeout accepts 1–86400 seconds. The two-hour socket read timeout accommodates
the longest recorded ~49-minute report; it is not a guaranteed server execution
deadline or cancellation mechanism. Existing MySQL execution limits still apply.
After a timeout/disconnection, inspect active queries before retrying. Restart
Streamlit after editing configuration. Credentials, tokens, and driver exceptions
are never shown in the app. `.env` and `.streamlit/secrets.toml` are Git-ignored.

## Execution, caching, and browsing

- **Saved exports** is the default and never connects to MySQL. Copy completed
  TSV/SUCCESS-log pairs into `dashboard/exports/`, following its README. The app
  labels these saved results. A completion log alone is not a usable export.
- **Warehouse reports** performs lightweight availability checks, then waits for
  **Load warehouse report**. Startup, navigation, charts, and display filters do
  not execute expensive analytical queries.
- **Load warehouse report** can reuse the exact SQL/parameter/account result for
  **24 hours**. **Refresh from MySQL** clears only that matching cache entry and
  requests a new execution. Both require a click. The current seven statements
  have no bind parameters.
- Retrieval timestamps and fresh/cache-hit status are visible. Ordinary rerenders
  retain session results. The shared cache lives in this app process; restarting
  clears it. Existing session results remain visible until explicitly replaced.
- Only **one expensive report** executes at a time in this process. Other uncached
  requests receive a clear busy message. A spinner shows elapsed waiting time;
  benchmark durations are context, not progress estimates. Closing/changing the
  page does not reliably cancel the MySQL operation. Keep the laptop awake.
- **Explore these results** selects already-returned groups. These display filters
  are not SQL parameters and never combine averages. Different population filters,
  date ranges, or aggregation levels require student-authored SQL and bindings.
- Charts exclude rollups. The displayed-group CSV matches the displayed table;
  the complete SQL output and its download separately retain original rollups.
  SQL NULL is exported as `\N`; literal `N/A` labels remain strings.
- Outputs above 10,000 aggregate rows are rejected rather than truncated. Errors
  and empty results never fall back to synthetic values. **Sample preview** is a
  separately labeled development mode.

The benchmark runtimes in `reports.json` were supplied by the team. The registry
maps Q1A–Q3B to statements 1–7 and records population, grain, and a source
fingerprint. Revised SQL requires team review and an updated fingerprint. No
predicates, LIMITs, parameter logic, or optimizations are injected by the app.

## ngrok presentation

Start Streamlit first. In a second CMD window:

```cmd
ngrok version
ngrok config check
ngrok http 8501
```

The CLI is installed locally. If account setup is incomplete, follow the
[official ngrok setup](https://ngrok.com/docs/start) and privately run
`ngrok config add-authtoken YOUR_TOKEN` once. Never paste the token into this repo.
Local `ngrok config check` passed; an actual tunnel/device check is still needed.
If Streamlit uses 8502, use `ngrok http 8502` instead.

Share only the forwarding HTTPS URL. Another device does not need MySQL or Python.
The local database port is not exposed. CORS and XSRF protections remain enabled.
Visitors can use the dashboard's Run/Refresh controls, so use ngrok access controls
for your intended audience. Keep MySQL, Streamlit, ngrok, and the laptop awake;
stop ngrok after the presentation. No tunnel is opened automatically.

See [VERIFICATION.md](VERIFICATION.md) for tested behavior and remaining checks.
