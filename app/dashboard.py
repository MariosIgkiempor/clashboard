import re
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

DB = Path(__file__).resolve().parent.parent / "data" / "clashboard.duckdb"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# Gold tables are at (grain x machine). Every query below says `main.<table>`; q() rewrites that to a
# per-session temp view `v_<table>` that is already filtered to the machines picked in the sidebar.
PLAIN = ["bash_command_log", "bash_daily", "cache_efficiency", "cache_savings", "mcp_stats", "message_context",
         "project_summary", "session_summary", "session_timeline", "session_tools", "tool_stats", "tool_transitions"]


def _lit(values) -> str:
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in values)


# Gold tables that carry project_name, so the sidebar project filter can apply to them.
BY_PROJECT = {"bash_command_log", "project_summary", "session_summary", "session_timeline"}


def project_group(name: str) -> str:
    """Collapse worktree dirs into their parent repo. Names are encoded dirs, e.g.
    `Programming-personal-shhh--claude-worktrees-foo-1a2b` or `-t3-worktrees-shhh-t3-bd428e77`."""
    if "--claude-worktrees-" in name:
        return name.split("--claude-worktrees-")[0]
    m = re.match(r"-t3-worktrees-(.+)-t3-[0-9a-f]+$", name)
    return m.group(1) if m else name


def view_sql(machines, projects=()) -> list[str]:
    m = _lit(machines)
    pf = f" AND project_name IN ({_lit(projects)})" if projects else ""
    views = [f"CREATE TEMP VIEW v_{t} AS SELECT * FROM main.{t} WHERE machine IN ({m})"
             + (pf if t in BY_PROJECT else "") for t in PLAIN]
    views += [
        f"""CREATE TEMP VIEW v_daily_usage AS SELECT day, model, sum(msgs) AS msgs, sum(input_tokens) AS input_tokens,
              sum(output_tokens) AS output_tokens, sum(cache_read_tokens) AS cache_read_tokens,
              sum(cache_write_tokens) AS cache_write_tokens
            FROM main.daily_usage WHERE machine IN ({m}) GROUP BY day, model""",
        f"""CREATE TEMP VIEW v_cost AS SELECT day, model, sum(cost_usd) AS cost_usd
            FROM main.cost WHERE machine IN ({m}) GROUP BY day, model""",
        f"""CREATE TEMP VIEW v_cost_breakdown AS SELECT day, model, sum(input_cost) AS input_cost, sum(output_cost) AS output_cost,
              sum(cache_read_cost) AS cache_read_cost, sum(cache_write_cost) AS cache_write_cost, sum(total_cost) AS total_cost
            FROM main.cost_breakdown WHERE machine IN ({m}) GROUP BY day, model""",
        f"""CREATE TEMP VIEW v_daily_agent_split AS SELECT day, agent_type, sum(messages) AS messages,
              sum(output_tokens) AS output_tokens, sum(cost_usd) AS cost_usd
            FROM main.daily_agent_split WHERE machine IN ({m}) GROUP BY day, agent_type""",
        f"""CREATE TEMP VIEW v_activity_heatmap AS SELECT weekday_num, weekday, hour, sum(messages) AS messages,
              sum(output_tokens) AS output_tokens
            FROM main.activity_heatmap WHERE machine IN ({m}) GROUP BY weekday_num, weekday, hour""",
        f"""CREATE TEMP VIEW v_tool_latency AS SELECT tool_name, count(*) AS calls,
              quantile_cont(latency_ms, 0.5) / 1000.0 AS p50_seconds, quantile_cont(latency_ms, 0.95) / 1000.0 AS p95_seconds,
              max(latency_ms) / 1000.0 AS max_seconds
            FROM main.tool_latency WHERE machine IN ({m}) GROUP BY tool_name HAVING count(*) >= 20""",
        f"""CREATE TEMP VIEW v_bash_command_stats AS SELECT command_family, command_head, command_subcommand,
              count(*) AS calls, count(*) FILTER (WHERE is_error) AS errors,
              100.0 * count(*) FILTER (WHERE is_error) / count(*) AS error_pct,
              count(DISTINCT session_id) AS sessions, count(DISTINCT project_name) AS projects,
              min(day) AS first_day, max(day) AS last_day, sum(output_bytes) AS output_bytes,
              avg(output_bytes) AS avg_output_bytes,
              quantile_cont(latency_ms, 0.5) / 1000.0 AS p50_seconds, quantile_cont(latency_ms, 0.95) / 1000.0 AS p95_seconds,
              avg(uses_pipe::int) AS pipe_share, avg(command_length) AS avg_command_length,
              count(*) FILTER (WHERE run_in_background) AS background_calls
            FROM main.bash_command_log WHERE machine IN ({m}){pf} GROUP BY 1, 2, 3""",
        f"""CREATE TEMP VIEW v_daily_trends AS
            WITH daily AS (
              SELECT day, sum(cost_usd) AS cost_usd, sum(messages) AS messages, sum(output_tokens) AS output_tokens,
                     sum(sessions) AS sessions, sum(projects) AS projects
              FROM main.daily_trends WHERE machine IN ({m}) GROUP BY day),
            spine AS (SELECT unnest(generate_series(min(day), max(day), INTERVAL 1 DAY))::DATE AS day FROM daily),
            filled AS (
              SELECT spine.day, coalesce(d.cost_usd, 0) AS cost_usd, coalesce(d.messages, 0) AS messages,
                     coalesce(d.output_tokens, 0) AS output_tokens, coalesce(d.sessions, 0) AS sessions,
                     coalesce(d.projects, 0) AS projects
              FROM spine LEFT JOIN daily d USING (day))
            SELECT *, avg(cost_usd) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS cost_7d_avg,
                   sum(cost_usd) OVER (ORDER BY day ROWS UNBOUNDED PRECEDING) AS cumulative_cost,
                   cost_usd - lag(cost_usd) OVER (ORDER BY day) AS cost_change_vs_prev_day
            FROM filled""",
    ]
    return views


@st.cache_data(ttl=60)
def _run(sql: str, machines: tuple, projects: tuple) -> pd.DataFrame:
    # Open per query and close right away, so dbt can still write the file.
    con = duckdb.connect(str(DB), read_only=True)
    try:
        for v in view_sql(machines, projects):
            con.execute(v)
        df = con.sql(re.sub(r"\bmain\.(\w+)", r"v_\1", sql)).df()
    finally:
        con.close()
    for col in ("day", "week"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


def q(sql: str) -> pd.DataFrame:
    return _run(sql, tuple(MACHINES), tuple(PROJECT_NAMES))


def show(chart: alt.Chart) -> None:
    st.altair_chart(chart, width="stretch")


def money(x: float) -> str:
    return f"${x:,.2f}"


st.set_page_config(page_title="Clashboard", layout="wide")
_con = duckdb.connect(str(DB), read_only=True)
ALL_MACHINES = [r[0] for r in _con.execute("select distinct machine from main.session_summary order by 1").fetchall()]
_con.close()
MACHINES = st.sidebar.multiselect("Machines", ALL_MACHINES, default=ALL_MACHINES)
if not MACHINES:
    st.warning("Pick at least one machine in the sidebar.")
    st.stop()

_con = duckdb.connect(str(DB), read_only=True)
_proj = _con.execute("select project_name, count(*) from main.session_summary where machine in ("
                     + _lit(MACHINES) + ") group by 1").fetchall()
_con.close()
_mains = {n for n, _ in _proj if project_group(n) == n and not n.startswith("-")}
_groups: dict[str, list[str]] = {}
_counts: dict[str, int] = {}
for _name, _n in _proj:
    _g = project_group(_name)
    if _g not in _mains:  # t3 worktrees carry only the repo name; attach to the full main-repo name
        _g = next((mn for mn in _mains if mn.endswith("-" + _g)), _g)
    _groups.setdefault(_g, []).append(_name)
    _counts[_g] = _counts.get(_g, 0) + _n
PROJECT_PICK = st.sidebar.multiselect(
    "Projects (worktrees grouped)", sorted(_groups, key=lambda g: -_counts[g]),
    format_func=lambda g: f"{g} ({_counts[g]} sessions, {len(_groups[g])} dirs)",
    help="Empty = all projects. Filters the Projects, Sessions and Bash tabs; "
         "daily cost/usage tables have no project column and stay unfiltered.")
PROJECT_NAMES = [n for g in PROJECT_PICK for n in _groups[g]]
st.title("Claude usage")
st.caption("Cost is API-equivalent value computed from the prices seed, not a bill.")

def sql_str(value: str) -> str:
    """Quote a string for SQL (values come from our own gold tables, but may contain quotes)."""
    return "'" + str(value).replace("'", "''") + "'"


tabs = st.tabs(["Overview", "Cost", "Cache", "Tools", "Bash", "MCP", "Activity", "Projects", "Sessions"])
(overview_tab, cost_tab, cache_tab, tools_tab, bash_tab, mcp_tab,
 activity_tab, projects_tab, sessions_tab) = tabs

# ================================================================ Overview
with overview_tab:
    daily = q("select * from main.daily_trends order by day")
    savings = q("select sum(actual_cost) as actual, sum(cost_without_cache) as without_cache from main.cache_savings").iloc[0]
    agents = q("select agent_type, sum(cost_usd) as cost from main.daily_agent_split group by 1")
    sessions_total = int(q("select count(*) as n from main.session_summary").iloc[0]["n"])
    active_days = int((daily["cost_usd"] > 0).sum())
    total_cost = float(daily["cost_usd"].sum())
    sub_cost = float(agents.loc[agents["agent_type"] == "subagent", "cost"].sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Estimated cost", money(total_cost))
    c2.metric("Saved by caching", money(savings["without_cache"] - savings["actual"]),
              f"{1 - savings['actual'] / savings['without_cache']:.0%} cheaper", delta_color="off")
    c3.metric("Sessions", f"{sessions_total:,}")
    c4.metric("Avg per active day", money(total_cost / max(active_days, 1)))
    c5.metric("Subagent share of cost", f"{sub_cost / total_cost:.0%}")

    st.subheader("Daily cost with 7-day average")
    base = alt.Chart(daily).encode(x=alt.X("day:T", title=None))
    bars = base.mark_bar(opacity=0.45).encode(
        y=alt.Y("cost_usd:Q", title="USD"), tooltip=["day:T", alt.Tooltip("cost_usd:Q", format="$.2f")])
    line = base.mark_line(strokeWidth=3, color="#e45756").encode(
        y="cost_7d_avg:Q", tooltip=["day:T", alt.Tooltip("cost_7d_avg:Q", title="7d avg", format="$.2f")])
    show(bars + line)

    left, right = st.columns(2)
    with left:
        st.subheader("Cumulative spend")
        show(alt.Chart(daily).mark_area(opacity=0.6, line=True).encode(
            x=alt.X("day:T", title=None), y=alt.Y("cumulative_cost:Q", title="USD"),
            tooltip=["day:T", alt.Tooltip("cumulative_cost:Q", format="$,.0f")]))
    with right:
        st.subheader("Sessions per day")
        show(alt.Chart(daily).mark_bar().encode(
            x=alt.X("day:T", title=None), y=alt.Y("sessions:Q", title="sessions"),
            tooltip=["day:T", "sessions:Q", "projects:Q"]))

    st.subheader("Calendar: cost per day")
    cal = daily.copy()
    cal["week_start"] = (cal["day"] - pd.to_timedelta(cal["day"].dt.day_of_week, unit="D")).dt.strftime("%d %b")
    cal["weekday"] = cal["day"].dt.day_name()
    week_order = list(dict.fromkeys(cal.sort_values("day")["week_start"]))
    show(alt.Chart(cal).mark_rect(stroke="white", strokeWidth=1).encode(
        x=alt.X("week_start:O", sort=week_order, title="week starting"),
        y=alt.Y("weekday:O", sort=WEEKDAYS, title=None),
        color=alt.Color("cost_usd:Q", scale=alt.Scale(type="sqrt", scheme="oranges"), title="USD"),
        tooltip=["day:T", alt.Tooltip("cost_usd:Q", format="$.2f"), "sessions:Q"]).properties(height=220))

# ================================================================ Cost
with cost_tab:
    spend = q("select day, model, cost_usd from main.cost order by day")

    left, right = st.columns(2)
    with left:
        st.subheader("Cost per day, by model")
        show(alt.Chart(spend).mark_bar().encode(
            x=alt.X("day:T", title=None), y=alt.Y("cost_usd:Q", title="USD"), color="model:N",
            tooltip=["day:T", "model:N", alt.Tooltip("cost_usd:Q", format="$.2f")]))
    with right:
        st.subheader("Model mix over time (share of cost)")
        show(alt.Chart(spend).mark_area().encode(
            x=alt.X("day:T", title=None), y=alt.Y("cost_usd:Q", stack="normalize", title="share"),
            color="model:N", tooltip=["day:T", "model:N", alt.Tooltip("cost_usd:Q", format="$.2f")]))

    by_type = q("""
        select day, type, sum(cost) as cost from (
            select day, input_cost, output_cost, cache_read_cost, cache_write_cost from main.cost_breakdown
        ) unpivot (cost for type in (input_cost, output_cost, cache_read_cost, cache_write_cost))
        group by all order by day""")
    by_type["type"] = by_type["type"].str.replace("_cost", "").str.replace("_", " ")
    left, right = st.columns([1, 2])
    with left:
        st.subheader("Where the money goes")
        totals = by_type.groupby("type", as_index=False)["cost"].sum()
        show(alt.Chart(totals).mark_arc(innerRadius=70).encode(
            theta="cost:Q", color=alt.Color("type:N", title=None),
            tooltip=["type:N", alt.Tooltip("cost:Q", format="$,.0f")]))
    with right:
        st.subheader("Cost by token type, per day")
        show(alt.Chart(by_type).mark_bar().encode(
            x=alt.X("day:T", title=None), y=alt.Y("cost:Q", title="USD"), color=alt.Color("type:N", title=None),
            tooltip=["day:T", "type:N", alt.Tooltip("cost:Q", format="$.2f")]))

    st.subheader("Main conversation vs subagents")
    split = q("select day, agent_type, cost_usd, messages from main.daily_agent_split order by day")
    show(alt.Chart(split).mark_area(opacity=0.8).encode(
        x=alt.X("day:T", title=None), y=alt.Y("cost_usd:Q", title="USD", stack=True),
        color=alt.Color("agent_type:N", title=None),
        tooltip=["day:T", "agent_type:N", alt.Tooltip("cost_usd:Q", format="$.2f"), "messages:Q"]))

    st.subheader("Totals by model")
    st.dataframe(q("""
        select c.model, round(sum(c.cost_usd), 2) as cost_usd, sum(u.msgs) as messages,
               sum(u.output_tokens) as output_tokens, sum(u.cache_read_tokens) as cache_read_tokens
        from main.cost c join main.daily_usage u using (day, model) group by 1 order by cost_usd desc"""),
        width="stretch")

# ================================================================ Cache
with cache_tab:
    sv = q("select day, sum(actual_cost) as actual, sum(cost_without_cache) as without_cache, "
           "sum(savings_usd) as saved from main.cache_savings group by day order by day")
    tot_actual, tot_without = sv["actual"].sum(), sv["without_cache"].sum()
    m1, m2, m3 = st.columns(3)
    m1.metric("Actual cost", money(tot_actual))
    m2.metric("Without caching", money(tot_without))
    m3.metric("Saved", money(tot_without - tot_actual), f"{1 - tot_actual / tot_without:.0%}", delta_color="off")

    st.subheader("Actual cost vs the same tokens without caching")
    melted = sv.melt("day", ["actual", "without_cache"], var_name="series", value_name="usd")
    show(alt.Chart(melted).mark_line(point=True).encode(
        x=alt.X("day:T", title=None), y=alt.Y("usd:Q", title="USD (log)", scale=alt.Scale(type="symlog")),
        color=alt.Color("series:N", title=None), tooltip=["day:T", "series:N", alt.Tooltip("usd:Q", format="$,.2f")]))

    st.subheader("Cache hit ratio per day")
    st.caption("cache reads / (cache reads + cache writes + uncached input)")
    ratio = q("""
        select day, sum(cache_read_tokens)::double
                 / nullif(sum(cache_read_tokens) + sum(cache_write_tokens) + sum(uncached_input_tokens), 0) as cache_hit_ratio
        from main.cache_efficiency group by day order by day""")
    show(alt.Chart(ratio).mark_line(point=True).encode(
        x=alt.X("day:T", title=None), y=alt.Y("cache_hit_ratio:Q", scale=alt.Scale(domain=[0.5, 1]), title="hit ratio"),
        tooltip=["day:T", alt.Tooltip("cache_hit_ratio:Q", format=".1%")]))

    st.subheader("By project (lowest ratio first, real volume only)")
    st.dataframe(q("""
        select project_name, round(cost_usd, 2) as cost_usd, round(cost_without_cache - cost_usd, 2) as saved_usd,
               cache_hit_ratio from main.project_summary where cost_usd > 5 order by cache_hit_ratio"""),
        width="stretch")

# ================================================================ Tools
with tools_tab:
    tools = q("""
        select tool_name, sum(calls) as calls, sum(errors) as errors,
               round(100.0 * sum(errors) / sum(calls), 1) as error_pct,
               sum(output_bytes) as output_bytes, round(sum(output_bytes) / sum(calls)) as avg_output_bytes
        from main.tool_stats group by tool_name""")
    left, right = st.columns(2)
    with left:
        st.subheader("Most-called tools")
        top = tools.sort_values("calls", ascending=False).head(15)
        show(alt.Chart(top).mark_bar().encode(
            y=alt.Y("tool_name:N", sort="-x", title=None), x=alt.X("calls:Q", scale=alt.Scale(type="symlog")),
            tooltip=["tool_name:N", "calls:Q", "errors:Q"]))
    with right:
        st.subheader("Biggest context hogs (total output bytes)")
        hogs = tools.sort_values("output_bytes", ascending=False).head(15)
        show(alt.Chart(hogs).mark_bar(color="#f58518").encode(
            y=alt.Y("tool_name:N", sort="-x", title=None), x=alt.X("output_bytes:Q", title="bytes"),
            tooltip=["tool_name:N", alt.Tooltip("output_bytes:Q", format=",.0f"), "avg_output_bytes:Q"]))

    left, right = st.columns([1, 2])
    with left:
        st.subheader("Built-in vs MCP vs subagent")
        cats = q("""
            select case when starts_with(tool_name, 'mcp__') then 'MCP'
                        when tool_name in ('Agent', 'Task') then 'Subagent'
                        else 'Built-in' end as category, sum(calls) as calls
            from main.tool_stats group by 1""")
        show(alt.Chart(cats).mark_arc(innerRadius=60).encode(
            theta="calls:Q", color=alt.Color("category:N", title=None), tooltip=["category:N", "calls:Q"]))
    with right:
        st.subheader("Weekly error rate, busiest tools")
        err = q("""
            with top as (select tool_name from main.tool_stats group by 1 order by sum(calls) desc limit 6)
            select date_trunc('week', day) as week, tool_name,
                   100.0 * sum(errors) / sum(calls) as error_pct, sum(calls) as calls
            from main.tool_stats where tool_name in (select tool_name from top)
            group by 1, 2 having sum(calls) >= 20 order by 1""")
        show(alt.Chart(err).mark_line(point=True).encode(
            x=alt.X("week:T", title=None), y=alt.Y("error_pct:Q", title="% of calls failing"),
            color=alt.Color("tool_name:N", title=None),
            tooltip=["week:T", "tool_name:N", alt.Tooltip("error_pct:Q", format=".1f"), "calls:Q"]))

    st.subheader("How long tools take (p50 tick, p95 bar)")
    st.caption("Latency is call-to-result, so it includes time spent waiting for you to approve the call.")
    lat = q("select tool_name, calls, p50_seconds, p95_seconds from main.tool_latency order by p95_seconds desc limit 20")
    lat_base = alt.Chart(lat).encode(y=alt.Y("tool_name:N", sort="-x", title=None))
    show(lat_base.mark_bar(opacity=0.5).encode(
        x=alt.X("p95_seconds:Q", scale=alt.Scale(type="symlog"), title="seconds"),
        tooltip=["tool_name:N", "calls:Q", alt.Tooltip("p50_seconds:Q", format=".1f"),
                 alt.Tooltip("p95_seconds:Q", format=".1f")])
         + lat_base.mark_tick(color="#e45756", thickness=3, size=16).encode(x="p50_seconds:Q"))

    st.subheader("What tool follows what? (chance the next call is the column tool)")
    trans = q("""
        with top as (
            select from_tool as t from main.tool_transitions group by 1 order by sum(n) desc limit 12)
        select from_tool, to_tool, n, n::double / sum(n) over (partition by from_tool) as p
        from main.tool_transitions
        where from_tool in (select t from top) and to_tool in (select t from top)""")
    order = list(q("select from_tool from main.tool_transitions group by 1 order by sum(n) desc limit 12")["from_tool"])
    show(alt.Chart(trans).mark_rect().encode(
        x=alt.X("to_tool:N", sort=order, title="next tool"), y=alt.Y("from_tool:N", sort=order, title="this tool"),
        color=alt.Color("p:Q", scale=alt.Scale(scheme="blues"), title="probability"),
        tooltip=["from_tool:N", "to_tool:N", "n:Q", alt.Tooltip("p:Q", format=".0%")]).properties(height=380))

    st.subheader("Error rate (tools with 50+ calls)")
    st.dataframe(tools[tools["calls"] >= 50].sort_values("error_pct", ascending=False), width="stretch")

# ================================================================ Bash
with bash_tab:
    import plotly.express as px

    stats = q("select * from main.bash_command_stats")
    total_calls = int(stats["calls"].sum())
    total_errors = int(stats["errors"].sum())
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Commands run", f"{total_calls:,}")
    k2.metric("Distinct programs", f"{stats['command_head'].nunique():,}")
    k3.metric("Failure rate", f"{total_errors / total_calls:.1%}")
    k4.metric("Use a pipe", f"{(stats['pipe_share'] * stats['calls']).sum() / total_calls:.0%}")
    k5.metric("Run in background", f"{int(stats['background_calls'].sum()):,}")
    st.caption("Command text is redacted for secrets and truncated to 300 characters. Redaction is best-effort.")

    # ---------------------------------------------------------- click-through hierarchy
    st.subheader("Explore: family > program > subcommand (click a slice to zoom)")
    view = st.radio("Layout", ["Sunburst", "Treemap"], horizontal=True, label_visibility="collapsed")
    tree = stats[stats["calls"] >= 10].copy()
    # Plotly needs every row to be a leaf: programs with real subcommands get "(plain)" for the bare call,
    # programs without any stop at the program level.
    has_subs = set(tree.loc[tree["command_subcommand"] != "(none)", "command_head"])
    tree["command_subcommand"] = [
        sub if sub != "(none)" else ("(plain)" if head in has_subs else None)
        for head, sub in zip(tree["command_head"], tree["command_subcommand"])
    ]
    path = ["command_family", "command_head", "command_subcommand"]
    plot = px.sunburst if view == "Sunburst" else px.treemap
    fig = plot(tree, path=path, values="calls", color="error_pct", color_continuous_scale="RdYlGn_r",
               range_color=[0, 20], hover_data={"calls": ":,", "error_pct": ":.1f"})
    fig.update_layout(height=640, margin=dict(t=10, l=0, r=0, b=0), coloraxis_colorbar=dict(title="% failing"))
    st.plotly_chart(fig, width="stretch")
    st.caption("Slice size = number of calls. Colour = failure rate (green low, red 20%+). Programs/subcommands with fewer than 10 calls are hidden.")

    # ---------------------------------------------------------- overview charts
    left, right = st.columns(2)
    with left:
        st.subheader("Most-run programs")
        heads = stats.groupby(["command_head", "command_family"], as_index=False)[["calls", "errors"]].sum()
        show(alt.Chart(heads.nlargest(20, "calls")).mark_bar().encode(
            y=alt.Y("command_head:N", sort="-x", title=None), x=alt.X("calls:Q", scale=alt.Scale(type="symlog")),
            color=alt.Color("command_family:N", title=None),
            tooltip=["command_head:N", "command_family:N", "calls:Q", "errors:Q"]).properties(height=460))
    with right:
        st.subheader("Programs that fail most (100+ calls)")
        failing = heads[heads["calls"] >= 100].assign(error_pct=lambda d: 100 * d["errors"] / d["calls"])
        show(alt.Chart(failing.nlargest(20, "error_pct")).mark_bar(color="#e45756").encode(
            y=alt.Y("command_head:N", sort="-x", title=None), x=alt.X("error_pct:Q", title="% failing"),
            tooltip=["command_head:N", "calls:Q", alt.Tooltip("error_pct:Q", format=".1f")]).properties(height=460))

    st.subheader("Command families over time")
    fam_daily = q("select day, command_family, sum(calls) as calls from main.bash_daily group by all order by day")
    show(alt.Chart(fam_daily).mark_area().encode(
        x=alt.X("day:T", title=None), y=alt.Y("calls:Q", stack=True), color=alt.Color("command_family:N", title=None),
        tooltip=["day:T", "command_family:N", "calls:Q"]))

    left, right = st.columns(2)
    with left:
        st.subheader("Biggest context hogs (avg output bytes, 50+ calls)")
        hog = stats[stats["calls"] >= 50].nlargest(15, "avg_output_bytes").assign(
            label=lambda d: d["command_head"] + " " + d["command_subcommand"].replace("(none)", "").str.strip())
        show(alt.Chart(hog).mark_bar(color="#f58518").encode(
            y=alt.Y("label:N", sort="-x", title=None), x=alt.X("avg_output_bytes:Q", title="avg bytes returned"),
            tooltip=["label:N", "calls:Q", alt.Tooltip("avg_output_bytes:Q", format=",.0f")]))
    with right:
        st.subheader("How chained are your commands?")
        shape = q("select least(n_segments, 8) as segments, count(*) as commands from main.bash_command_log group by 1 order by 1")
        show(alt.Chart(shape).mark_bar().encode(
            x=alt.X("segments:O", title="statements per command (8 = 8 or more)"), y="commands:Q",
            tooltip=["segments:O", "commands:Q"]))

    # ---------------------------------------------------------- cascading drill-down
    st.subheader("Drill into one command")
    fam_totals = stats.groupby("command_family")["calls"].sum().sort_values(ascending=False)
    d1, d2, d3 = st.columns(3)
    family = d1.selectbox("Family", ["(all)"] + list(fam_totals.index))
    in_family = stats if family == "(all)" else stats[stats["command_family"] == family]
    head_totals = in_family.groupby("command_head")["calls"].sum().sort_values(ascending=False)
    program = d2.selectbox("Program", ["(all)"] + list(head_totals.index))
    in_head = in_family if program == "(all)" else in_family[in_family["command_head"] == program]
    sub_totals = in_head.groupby("command_subcommand")["calls"].sum().sort_values(ascending=False)
    subcommand = d3.selectbox("Subcommand", ["(all)"] + list(sub_totals.index), disabled=program == "(all)")

    conds = ["true"]
    if family != "(all)":
        conds.append(f"command_family = {sql_str(family)}")
    if program != "(all)":
        conds.append(f"command_head = {sql_str(program)}")
    if subcommand != "(all)" and program != "(all)":
        conds.append(f"command_subcommand = {sql_str(subcommand)}")
    where = " and ".join(conds)

    summary = q(f"""
        select count(*) as calls, count(*) filter (where is_error) as errors,
               count(distinct session_id) as sessions, count(distinct project_name) as projects,
               quantile_cont(latency_ms, 0.5) / 1000.0 as p50, quantile_cont(latency_ms, 0.95) / 1000.0 as p95,
               avg(output_bytes) as avg_out
        from main.bash_command_log where {where}""").iloc[0]
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Calls", f"{int(summary['calls']):,}")
    s2.metric("Failure rate", f"{summary['errors'] / max(summary['calls'], 1):.1%}")
    s3.metric("Sessions", f"{int(summary['sessions']):,}")
    s4.metric("Median / p95 latency", f"{(summary['p50'] or 0):.1f}s / {(summary['p95'] or 0):.1f}s")
    s5.metric("Avg output", f"{(summary['avg_out'] or 0):,.0f} B")

    left, right = st.columns(2)
    with left:
        st.markdown("**Calls and failures per day**")
        trend = q(f"""select day, count(*) as calls, count(*) filter (where is_error) as failures
                      from main.bash_command_log where {where} group by day order by day""")
        base = alt.Chart(trend).encode(x=alt.X("day:T", title=None))
        show(base.mark_bar(opacity=0.6).encode(y="calls:Q", tooltip=["day:T", "calls:Q", "failures:Q"])
             + base.mark_line(color="#e45756", point=True).encode(y="failures:Q"))
    with right:
        level = "command_family" if family == "(all)" else "command_head" if program == "(all)" else "command_subcommand"
        st.markdown(f"**Breakdown by {level.replace('command_', '')}**")
        breakdown = q(f"""select {level} as name, count(*) as calls, count(*) filter (where is_error) as failures
                          from main.bash_command_log where {where} group by 1 order by 2 desc limit 15""")
        show(alt.Chart(breakdown).mark_bar().encode(
            y=alt.Y("name:N", sort="-x", title=None), x="calls:Q", tooltip=["name:N", "calls:Q", "failures:Q"]))

    st.markdown("**Where it runs (top projects)**")
    by_project = q(f"""select project_name, count(*) as calls from main.bash_command_log where {where}
                       group by 1 order by 2 desc limit 10""")
    show(alt.Chart(by_project).mark_bar().encode(
        y=alt.Y("project_name:N", sort="-x", title=None), x="calls:Q", tooltip=["project_name:N", "calls:Q"]).properties(height=260))

    st.markdown("**Individual commands (newest first, max 300)**")
    f1, f2 = st.columns([1, 3])
    errors_only = f1.checkbox("Failures only")
    needle = f2.text_input("Contains text (in the redacted preview or description)")
    log_conds = [where]
    if errors_only:
        log_conds.append("is_error")
    if needle:
        log_conds.append(f"(command_preview ilike {sql_str('%' + needle + '%')} or description ilike {sql_str('%' + needle + '%')})")
    log = q(f"""
        select ts, project_name, command_head, command_subcommand, description, command_preview,
               is_error as failed, round(latency_ms / 1000.0, 1) as seconds, output_bytes
        from main.bash_command_log where {' and '.join(log_conds)} order by ts desc limit 300""")
    st.dataframe(log, width="stretch", hide_index=True)

# ================================================================ MCP
with mcp_tab:
    servers = q("""
        select mcp_server, sum(calls) as calls, sum(errors) as errors,
               round(100.0 * sum(errors) / sum(calls), 1) as error_pct, sum(output_bytes) as output_bytes
        from main.mcp_stats group by mcp_server order by calls desc""")
    left, right = st.columns(2)
    with left:
        st.subheader("MCP servers by calls")
        show(alt.Chart(servers.head(15)).mark_bar().encode(
            y=alt.Y("mcp_server:N", sort="-x", title=None), x="calls:Q",
            tooltip=["mcp_server:N", "calls:Q", "errors:Q", "error_pct:Q"]))
    with right:
        st.subheader("Server error rate (10+ calls)")
        show(alt.Chart(servers[servers["calls"] >= 10]).mark_bar(color="#e45756").encode(
            y=alt.Y("mcp_server:N", sort="-x", title=None), x=alt.X("error_pct:Q", title="% failing"),
            tooltip=["mcp_server:N", "calls:Q", "error_pct:Q"]))

    st.subheader("MCP calls over time")
    keep = list(servers.head(6)["mcp_server"])
    daily_mcp = q("select day, mcp_server, sum(calls) as calls from main.mcp_stats group by all order by day")
    daily_mcp["server"] = daily_mcp["mcp_server"].where(daily_mcp["mcp_server"].isin(keep), "other")
    show(alt.Chart(daily_mcp.groupby(["day", "server"], as_index=False)["calls"].sum()).mark_area().encode(
        x=alt.X("day:T", title=None), y=alt.Y("calls:Q", stack=True), color=alt.Color("server:N", title=None),
        tooltip=["day:T", "server:N", "calls:Q"]))

    st.subheader("MCP tools")
    st.dataframe(q("""
        select mcp_server, mcp_tool, sum(calls) as calls, sum(errors) as errors, sum(output_bytes) as output_bytes
        from main.mcp_stats group by all order by calls desc limit 50"""), width="stretch")

# ================================================================ Activity
with activity_tab:
    heat = q("select * from main.activity_heatmap")
    st.subheader("When you work: messages by weekday and hour")
    st.caption("Main-conversation messages only, in Europe/London time (change with the dbt var display_timezone).")
    show(alt.Chart(heat).mark_rect().encode(
        x=alt.X("hour:O", title="hour of day"), y=alt.Y("weekday:O", sort=WEEKDAYS, title=None),
        color=alt.Color("messages:Q", scale=alt.Scale(scheme="viridis"), title="messages"),
        tooltip=["weekday:N", "hour:O", "messages:Q", "output_tokens:Q"]).properties(height=280))
    left, right = st.columns(2)
    with left:
        st.subheader("By hour")
        show(alt.Chart(heat.groupby("hour", as_index=False)["messages"].sum()).mark_bar().encode(
            x=alt.X("hour:O", title="hour"), y="messages:Q", tooltip=["hour:O", "messages:Q"]))
    with right:
        st.subheader("By weekday")
        show(alt.Chart(heat.groupby("weekday", as_index=False)["messages"].sum()).mark_bar().encode(
            x=alt.X("weekday:N", sort=WEEKDAYS, title=None), y="messages:Q", tooltip=["weekday:N", "messages:Q"]))

# ================================================================ Projects
with projects_tab:
    proj = q("select * from main.project_summary order by cost_usd desc")
    st.subheader("Most expensive projects")
    show(alt.Chart(proj.head(15)).mark_bar().encode(
        y=alt.Y("project_name:N", sort="-x", title=None), x=alt.X("cost_usd:Q", title="USD"),
        color=alt.Color("subagent_share:Q", scale=alt.Scale(scheme="purples"), title="subagent share"),
        tooltip=["project_name:N", "machine:N", alt.Tooltip("cost_usd:Q", format="$,.0f"), "sessions:Q", "messages:Q",
                 alt.Tooltip("subagent_share:Q", format=".0%")]))

    st.subheader("Sessions vs cost per project (bubble = messages, colour = cache hit ratio)")
    show(alt.Chart(proj).mark_circle(opacity=0.75).encode(
        x=alt.X("sessions:Q", scale=alt.Scale(type="symlog")), y=alt.Y("cost_usd:Q", scale=alt.Scale(type="symlog"), title="USD"),
        size=alt.Size("messages:Q", legend=None),
        color=alt.Color("cache_hit_ratio:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[0.8, 1]), title="cache hit"),
        tooltip=["project_name:N", "machine:N", alt.Tooltip("cost_usd:Q", format="$,.0f"), "sessions:Q", "messages:Q",
                 alt.Tooltip("cache_hit_ratio:Q", format=".1%")]).properties(height=380))
    st.dataframe(proj[["project_name", "machine", "first_day", "last_day", "sessions", "messages", "tool_calls", "tool_errors",
                       "cost_usd", "cache_hit_ratio", "subagent_share"]], width="stretch")

# ================================================================ Sessions
with sessions_tab:
    all_sessions = q("select * from main.session_summary")
    st.subheader("Every session: duration vs cost")
    show(alt.Chart(all_sessions[all_sessions["duration_min"] > 0]).mark_circle(opacity=0.6).encode(
        x=alt.X("duration_min:Q", scale=alt.Scale(type="symlog"), title="duration (minutes)"),
        y=alt.Y("cost_usd:Q", scale=alt.Scale(type="symlog"), title="USD"),
        size=alt.Size("tool_calls:Q", legend=None), color=alt.Color("project_name:N", legend=None),
        tooltip=["project_name:N", "machine:N", alt.Tooltip("cost_usd:Q", format="$,.2f"), "duration_min:Q", "messages:Q", "tool_calls:Q"]
    ).properties(height=320))
    st.subheader("How session costs are distributed")
    show(alt.Chart(all_sessions[all_sessions["cost_usd"] > 0]).mark_bar().encode(
        x=alt.X("cost_usd:Q", bin=alt.Bin(maxbins=30), scale=alt.Scale(type="log"), title="session cost (USD, log bins)"),
        y=alt.Y("count()", title="sessions")))

    st.subheader("Session drill-down")
    top100 = all_sessions.sort_values("cost_usd", ascending=False, na_position="last").head(100)
    labels = {r.session_id: f"${r.cost_usd or 0:,.2f} | {str(r.started_at)[:16]} | {r.machine} | {r.project_name[-40:]}"
              for r in top100.itertuples()}
    chosen = st.selectbox("Session (top 100 by cost)", list(labels), format_func=labels.get)
    row = top100[top100["session_id"] == chosen].iloc[0]
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Cost", money(row["cost_usd"] or 0))
    m2.metric("Duration", f"{int(row['duration_min'])} min")
    m3.metric("Messages", f"{int(row['messages']):,}")
    m4.metric("Subagent messages", f"{int(row['subagent_messages']):,}")
    m5.metric("Tool calls", f"{int(row['tool_calls']):,}")

    st.subheader("Context size over the session")
    st.caption("Tokens sent per API call (input + cache read + cache write). Drops mean compaction or a fresh subagent.")
    ctx = q(f"""
        select ts, message_index, context_tokens, output_tokens,
               case when is_sidechain then 'subagent' else 'main' end as agent_type
        from main.message_context where session_id = '{chosen}' order by ts""")
    show(alt.Chart(ctx).mark_line(point=alt.OverlayMarkDef(size=12)).encode(
        x=alt.X("ts:T", title=None), y=alt.Y("context_tokens:Q", title="context tokens"),
        color=alt.Color("agent_type:N", title=None),
        tooltip=["ts:T", "agent_type:N", "message_index:Q", "context_tokens:Q", "output_tokens:Q"]))

    st.subheader("Tools used in this session")
    st.dataframe(q(f"""
        select tool_name, calls, errors, output_bytes from main.session_tools
        where session_id = '{chosen}' order by calls desc"""), width="stretch")

    st.subheader("Timeline")
    ev = q(f"""
        select seq, message_id, event_id, ts, end_ts, event_type, label, is_sidechain, is_error, context_tokens, output_tokens,
               cost_usd, output_bytes, detail
        from main.session_timeline where session_id = '{chosen}' order by seq""")
    if ev.empty:
        st.info("No events for this session.")
    else:
        ev["ts"] = pd.to_datetime(ev["ts"])
        ev["end_ts"] = pd.to_datetime(ev["end_ts"]).fillna(ev["ts"])
        ev["agent"] = ev["is_sidechain"].map({True: "subagent", False: "main"})
        kinds = st.multiselect("Show", ["message", "tool"], default=["message", "tool"], key="tl_kinds")
        only_err = st.checkbox("Errors only (tool calls)", key="tl_err")
        view = ev[ev["event_type"].isin(kinds)]
        if only_err:
            view = view[view["is_error"] == True]  # noqa: E712
        MAX = 1500
        if len(view) > MAX:
            st.caption(f"{len(view):,} events; charting the first {MAX:,}. Use the filters to narrow.")
        view = view.head(MAX)
        lane = alt.Y("label:N", title=None, sort=alt.EncodingSortField("seq", op="min"))
        base = alt.Chart(view).encode(
            y=lane, color=alt.Color("event_type:N", title=None),
            tooltip=["seq:Q", "ts:T", "event_type:N", "label:N", "agent:N", "is_error:N", "detail:N",
                     alt.Tooltip("cost_usd:Q", format="$,.4f"), "context_tokens:Q", "output_tokens:Q"])
        err = alt.condition("datum.is_error == true", alt.value("red"), alt.value(None))
        bars = base.mark_bar(cornerRadius=1, opacity=0.6).encode(x=alt.X("ts:T", title=None), x2="end_ts:T")
        ticks = base.mark_tick(thickness=2, size=14).encode(x="ts:T", stroke=err)  # visible even at 0 duration
        show((bars + ticks).properties(height=max(200, 18 * view["label"].nunique())).interactive(bind_y=False))
        t0 = ev["ts"].min()

        st.markdown("##### Conversation feed")
        st.caption("Metadata only: no prompt or response text is stored. Each bubble is one API call; its tool calls sit inside.")
        msgs = ev[ev["event_type"] == "message"].sort_values("seq")
        tools_by_msg = {k: g for k, g in ev[ev["event_type"] == "tool"].groupby("message_id")}
        if only_err:
            bad = set(ev[(ev["event_type"] == "tool") & (ev["is_error"] == True)]["message_id"])  # noqa: E712
            msgs = msgs[msgs["message_id"].isin(bad)]
        PAGE = 25
        pages = max(1, -(-len(msgs) // PAGE))
        c1, c2 = st.columns([1, 5])
        page = c1.number_input(f"Page (of {pages})", 1, pages, 1, key="tl_page")
        c2.caption(f"{len(msgs):,} API calls, {PAGE} per page")
        for m in msgs.iloc[(page - 1) * PAGE: page * PAGE].itertuples():
            side = bool(m.is_sidechain)
            _, col = st.columns([1, 14]) if side else (None, st.container())
            with col:
                with st.chat_message("assistant", avatar="🧩" if side else None):
                    st.markdown(f"**{'Subagent' if side else 'Assistant'}** · `{m.label}` · "
                                f"t+{(m.ts - t0).total_seconds():,.0f}s · seq {m.seq}")
                    st.caption(f"context {int(m.context_tokens or 0):,} tok · out {int(m.output_tokens or 0):,} tok · "
                               f"{money(m.cost_usd or 0)}")
                    tl = tools_by_msg.get(m.message_id)
                    if tl is None:
                        continue
                    for t in tl.sort_values("seq").itertuples():
                        err = t.is_error is True
                        dur = (t.end_ts - t.ts).total_seconds()
                        head = f"{'❌' if err else '🔧'} {t.label} · {dur:,.1f}s · {int(t.output_bytes or 0):,} B out"
                        with st.expander(head):
                            if t.detail:
                                st.code(t.detail, language="bash")
                            else:
                                st.caption("No stored input (only Bash commands are kept).")
                            st.caption(f"tool_use_id {t.event_id} · seq {t.seq}")

        with st.expander("Raw events table"):
            table = view.assign(offset=(view["ts"] - t0).dt.total_seconds().round(1),
                                duration_s=(view["end_ts"] - view["ts"]).dt.total_seconds().round(2))
            st.dataframe(table[["seq", "offset", "event_type", "label", "agent", "duration_s", "is_error", "detail",
                                "context_tokens", "output_tokens", "cost_usd", "output_bytes"]],
                         width="stretch", hide_index=True,
                         column_config={"offset": st.column_config.NumberColumn("t+ (s)"),
                                        "cost_usd": st.column_config.NumberColumn("cost", format="$%.4f")})
