"""Streamlit entrypoint for `terrasync status`.

Tabs:
    - Visão geral: KPIs do pipeline.
    - Bronze health: linha por (source, layer) com freshness + counts.
    - Staging health: linha por modelo stg_*, geom quality + dbt status.
    - Run history: últimas execuções de `runs.jsonl`.
    - Queries: SQL operacional do dashboard, auditável e executável on-demand.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from terrasync.config import BRONZE_DIR, SOURCE_GROUPS, SOURCES, STAGING_DIR
from terrasync.dashboard import dbt_artifacts
from terrasync.dashboard.bronze import scan_bronze
from terrasync.dashboard.probe import ProbeResult, probe_all
from terrasync.dashboard.queries import (
    _connect,
    _SQL_DIR,
    actual_row_count,
    geom_health,
    validate_geometries,
)
from terrasync.dashboard.runs import read_runs, runs_mtime
from terrasync.dashboard.staging import scan_staging

_PROBE_EMOJI = {"up": "✓", "slow": "⚠", "down": "✗", "unknown": "?"}
_DBT_STATUS_EMOJI = {
    "success": "✓",
    "pass": "✓",
    "fail": "✗",
    "error": "✗",
    "skipped": "⊘",
    "warn": "⚠",
}

st.set_page_config(
    page_title="terrasync · status",
    page_icon="🛰️",
    layout="wide",
)

_STATUS_EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⚪"}


_ALL = "(todas)"


def _filter_entries() -> list[tuple[str, str]]:
    """Flat, deduplicated list of (key, label) for the sidebar.

    Each entry filters a unique set of bronze rows. A group whose single
    member has the same name (e.g. `ana`/`ana`) appears once as the group;
    sources that don't belong to any group appear once as standalone.
    """
    in_a_group: set[str] = set()
    for grp in SOURCE_GROUPS.values():
        in_a_group.update(grp.sources)

    entries: list[tuple[str, str]] = []
    for g in SOURCE_GROUPS.keys():
        n = len(SOURCE_GROUPS[g].sources)
        label = f"{g} ({n})" if n > 1 else g
        entries.append((g, label))
    for name in SOURCES.keys():
        if name not in in_a_group:
            entries.append((name, name))

    entries.sort(key=lambda kv: kv[1].lower())
    return entries


def _sidebar_filter() -> str | None:
    st.sidebar.markdown("### Filtros")
    entries = _filter_entries()
    keys = [_ALL, *[k for k, _ in entries]]
    labels = {_ALL: _ALL, **{k: lbl for k, lbl in entries}}
    choice = st.sidebar.selectbox(
        "Agência / source",
        keys,
        index=0,
        format_func=lambda k: labels[k],
    )
    return None if choice == _ALL else choice


def _filter_rows(rows: list[dict], selection: str | None) -> list[dict]:
    if selection is None:
        return rows
    if selection in SOURCE_GROUPS:
        group_sources = set(SOURCE_GROUPS[selection].sources)
        return [r for r in rows if r["source"] in group_sources]
    return [r for r in rows if r["source"] == selection]


def _tab_overview(bronze_rows: list[dict], runs_df: pd.DataFrame) -> None:
    st.subheader("Visão geral")
    n_sources = len({r["source"] for r in bronze_rows})
    n_layers = len(bronze_rows)
    total_features = sum(r["n_features"] for r in bronze_rows)
    total_size_mb = sum(r["file_size_mb"] for r in bronze_rows)

    ages = [r["age_days"] for r in bronze_rows if r["age_days"] is not None]
    median_age = round(sorted(ages)[len(ages) // 2], 1) if ages else None
    oldest = max(ages) if ages else None

    if not runs_df.empty:
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)
        recent = runs_df[runs_df["acquired_at"] >= cutoff]
        ok_pct = (
            round(100 * (recent["status"] == "ok").mean(), 1)
            if not recent.empty
            else None
        )
    else:
        ok_pct = None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sources com bronze", n_sources, help=f"de {len(SOURCES)} declaradas")
    c2.metric("Parquets bronze", n_layers)
    c3.metric("Features totais", f"{total_features:,}".replace(",", "."))
    c4.metric("Tamanho total", f"{total_size_mb:,.1f} MB")

    c5, c6, c7 = st.columns(3)
    c5.metric("Idade mediana (dias)", median_age if median_age is not None else "—")
    c6.metric("Mais antigo (dias)", round(oldest, 1) if oldest is not None else "—")
    c7.metric("Runs OK (24h)", f"{ok_pct}%" if ok_pct is not None else "—")


def _ensure_probe_results(selection: str | None) -> dict[str, ProbeResult]:
    """Lazy probe on first open; manual re-probe clears the cache."""
    state_key = "probe_results"
    if state_key not in st.session_state:
        st.session_state[state_key] = {}

    if selection is None:
        sources = list(SOURCES.values())
    elif selection in SOURCE_GROUPS:
        sources = [SOURCES[k] for k in SOURCE_GROUPS[selection].sources]
    else:
        sources = [SOURCES[selection]]

    cached: dict[str, ProbeResult] = st.session_state[state_key]
    missing = [s for s in sources if s.name not in cached]
    if missing:
        with st.spinner(f"Probing {len(missing)} endpoint(s)…"):
            new_results = probe_all(missing)
        cached.update(new_results)
        st.session_state[state_key] = cached
    return cached


def _tab_bronze(rows: list[dict], group: str | None) -> None:
    st.subheader("Bronze health")
    st.caption(
        "Semáforo de age respeita `cadence` declarada por source "
        "(daily/weekly/monthly/quarterly/yearly). ⚪ = sem cadence declarada. "
        "Coluna `up` mostra liveness dos endpoints (✓ up · ⚠ slow · ✗ down)."
    )

    cols = st.columns([1, 5])
    if cols[0].button("🔄 Re-probe endpoints"):
        st.session_state.pop("probe_results", None)

    probe_results = _ensure_probe_results(group)

    if not rows:
        st.info("Nenhum parquet bronze encontrado em `data/bronze/`.")
        return

    display: list[dict] = []
    for r in rows:
        actual = actual_row_count(r["path"], r["mtime"])
        divergence = actual != r["n_features"]
        pres = probe_results.get(r["source"])
        if pres is None:
            up = "—"
            latency = None
            checked_at = ""
        else:
            up = _PROBE_EMOJI.get(pres.status, "?")
            latency = pres.latency_ms
            checked_at = pres.checked_at
        display.append(
            {
                "": _STATUS_EMOJI.get(r["age_status"], "⚪"),
                "up": up,
                "source": r["source"],
                "layer": r["layer"],
                "cadence": r.get("cadence", "unknown"),
                "category": r["category"],
                "age (d)": round(r["age_days"], 1) if r["age_days"] is not None else None,
                "acquired_at": r["acquired_at"] or "",
                "n_features (footer)": r["n_features"],
                "actual_rows": actual,
                "Δ": "⚠️" if divergence else "",
                "size (MB)": r["file_size_mb"],
                "latency (ms)": latency,
                "checked_at": checked_at,
                "endpoint": r["endpoint"],
            }
        )

    df = pd.DataFrame(display)
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "endpoint": st.column_config.TextColumn(width="large"),
        },
    )

    n_divergent = sum(1 for d in display if d["Δ"])
    if n_divergent:
        st.warning(
            f"{n_divergent} parquet(s) com divergência footer/contagem real. "
            "Possível truncamento ou metadata desatualizada."
        )


def _format_deps(deps: list[str], limit: int = 3) -> str:
    if not deps:
        return ""
    if len(deps) <= limit:
        return ", ".join(deps)
    return f"{', '.join(deps[:limit])}, +{len(deps) - limit}"


def _tab_staging(staging_rows: list[dict], bronze_rows: list[dict]) -> None:
    st.subheader("Staging health")
    st.caption(
        "Uma linha por modelo `stg_*` em `apps/dbt/models/staging/`. "
        "Modelos não materializados aparecem em cinza. "
        "Coluna `dbt status` reflete o último `dbt build`; geometrias validadas sob demanda."
    )

    if not staging_rows:
        st.info("Nenhum modelo staging encontrado.")
        return

    models = dbt_artifacts.model_summary()
    if models:
        rr_ts = dbt_artifacts.run_results_generated_at()
        mf_ts = dbt_artifacts.manifest_generated_at()
        st.info(
            f"dbt manifest: `{mf_ts or '—'}` · última build: `{rr_ts or '—'}`"
        )
    else:
        st.warning(
            "Manifest dbt ausente em `apps/dbt/target/manifest.json`. "
            "Rode `cd apps/dbt && uv run dbt build` para popular status/tests."
        )

    bronze_by_source: dict[str, int] = {}
    for r in bronze_rows:
        bronze_by_source[r["source"]] = bronze_by_source.get(r["source"], 0) + r["n_features"]

    built = [r for r in staging_rows if r["built"]]
    not_built = [r for r in staging_rows if not r["built"]]

    def _dbt_cells(model: str) -> dict:
        info = models.get(model)
        if info is None:
            return {
                "dbt status": "—",
                "dbt duration (s)": None,
                "tests": "",
                "deps": "",
            }
        status = info.last_run_status
        status_cell = _DBT_STATUS_EMOJI.get(status, "—") if status else "—"
        duration = (
            round(info.last_run_duration_s, 2)
            if info.last_run_duration_s is not None
            else None
        )
        if info.test_count == 0:
            tests_cell = ""
        else:
            tests_cell = f"{info.tests_passed}/{info.test_count}"
            if info.tests_failed:
                tests_cell += f" ✗{info.tests_failed}"
        return {
            "dbt status": status_cell,
            "dbt duration (s)": duration,
            "tests": tests_cell,
            "deps": _format_deps(info.depends_on),
        }

    display: list[dict] = []
    for r in staging_rows:
        dbt_cells = _dbt_cells(r["model"])
        if r["built"]:
            stats = geom_health(r["path"], r["mtime"])
            rows = stats["rows"]
            bronze_rows_for_source = bronze_by_source.get(r["source"], 0)
            display.append(
                {
                    "": "🟢" if rows > 0 else "🟡",
                    "model": r["model"],
                    "source": r["source"] or "(n/a)",
                    "bronze_rows": bronze_rows_for_source or None,
                    "staging_rows": rows,
                    "n_null_geom": stats["n_null_geom"],
                    "n_empty_geom": stats["n_empty_geom"],
                    "size (MB)": r["file_size_mb"],
                    **dbt_cells,
                }
            )
        else:
            display.append(
                {
                    "": "⚪",
                    "model": r["model"],
                    "source": r["source"] or "(n/a)",
                    "bronze_rows": bronze_by_source.get(r["source"], 0) or None,
                    "staging_rows": None,
                    "n_null_geom": None,
                    "n_empty_geom": None,
                    "size (MB)": None,
                    **dbt_cells,
                }
            )

    df = pd.DataFrame(display)
    max_rows = max(
        (d["bronze_rows"] or 0 for d in display),
        default=0,
    ) or 1
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "bronze_rows": st.column_config.ProgressColumn(
                "bronze_rows",
                help="Total de features no bronze da source",
                format="%d",
                min_value=0,
                max_value=int(max_rows),
            ),
            "staging_rows": st.column_config.ProgressColumn(
                "staging_rows",
                format="%d",
                min_value=0,
                max_value=int(max_rows),
            ),
        },
    )

    st.caption(
        f"{len(built)} materializado(s) · {len(not_built)} pendente(s) · "
        f"{len(staging_rows)} modelo(s) declarado(s)."
    )

    if not built:
        return

    st.markdown("#### Validação on-demand (`ST_IsValid`)")
    st.caption(
        "Custosa: varre a tabela inteira. Cacheada por 1 hora ou até o parquet ser regravado."
    )
    model_options = [r["model"] for r in built]
    choice = st.selectbox("Modelo", model_options, key="stg_validate_choice")
    if st.button("Validar geometrias", key="stg_validate_btn"):
        target = next(r for r in built if r["model"] == choice)
        result = validate_geometries(target["path"], target["mtime"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Geoms checadas", f"{result['checked']:,}".replace(",", "."))
        c2.metric("Inválidas", f"{result['n_invalid']:,}".replace(",", "."))
        pct = (
            round(100 * result["n_invalid"] / result["checked"], 2)
            if result["checked"]
            else 0.0
        )
        c3.metric("% inválidas", f"{pct}%")
        if result["n_invalid"] == 0:
            st.success("Todas as geometrias são válidas.")
        else:
            st.warning(
                f"{result['n_invalid']} geometria(s) inválida(s) — revisar `clean_geometry` ou fonte."
            )


def _tab_runs(df: pd.DataFrame) -> None:
    st.subheader("Run history")
    if df.empty:
        st.info("Nenhuma execução registrada em `data/manifests/runs.jsonl`.")
        return

    cols = st.columns([1, 1, 1])
    status_filter = cols[0].multiselect(
        "Status", sorted(df["status"].unique()), default=list(df["status"].unique())
    )
    source_filter = cols[1].multiselect(
        "Source", sorted(df["source"].unique()), default=None
    )
    limit = cols[2].number_input("Linhas", min_value=10, max_value=2000, value=200, step=10)

    filtered = df[df["status"].isin(status_filter)]
    if source_filter:
        filtered = filtered[filtered["source"].isin(source_filter)]
    filtered = filtered.head(int(limit))

    st.dataframe(
        filtered,
        hide_index=True,
        use_container_width=True,
        column_config={
            "acquired_at": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss"),
            "endpoint": st.column_config.TextColumn(width="large"),
            "error": st.column_config.TextColumn(width="medium"),
        },
    )

    st.markdown("#### Métricas auxiliares")
    failed = df[df["status"] == "failed"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Execuções (total)", len(df))
    m2.metric("Falhas", len(failed))
    fail_rate = round(100 * len(failed) / max(len(df), 1), 1)
    m3.metric("Taxa de falha", f"{fail_rate}%")

    if not failed.empty:
        st.markdown("##### Falhas por source")
        st.dataframe(
            failed.groupby("source").size().rename("falhas").reset_index(),
            hide_index=True,
            use_container_width=False,
        )

    st.markdown("##### Duração média por source")
    durations = (
        df[df["status"] == "ok"]
        .groupby("source")["duration_s"]
        .mean()
        .round(2)
        .rename("duration_s_avg")
        .reset_index()
        .sort_values("duration_s_avg", ascending=False)
    )
    st.dataframe(durations, hide_index=True, use_container_width=False)


def _list_known_parquets() -> list[str]:
    """All parquets currently on disk under data/staging and data/bronze."""
    paths: list[Path] = []
    if STAGING_DIR.exists():
        paths.extend(sorted(STAGING_DIR.glob("*.parquet")))
    if BRONZE_DIR.exists():
        paths.extend(sorted(BRONZE_DIR.glob("*/*.parquet")))
    return [str(p) for p in paths]


def _list_sql_files() -> list[Path]:
    if not _SQL_DIR.exists():
        return []
    return sorted(p for p in _SQL_DIR.glob("*.sql") if not p.name.startswith("_"))


def _tab_queries() -> None:
    st.subheader("Queries")
    st.caption(
        "SQL operacional do dashboard. Edite o arquivo `.sql` e dê refresh para "
        "ver mudanças. Parâmetros posicionais (`?`) são preenchidos pelos campos abaixo."
    )

    sql_files = _list_sql_files()
    if not sql_files:
        st.info(f"Nenhum `.sql` em `{_SQL_DIR}`.")
        return

    names = [p.stem for p in sql_files]
    choice = st.selectbox("Query", names, key="queries_choice")
    target = next(p for p in sql_files if p.stem == choice)
    sql_text = target.read_text(encoding="utf-8")

    st.code(sql_text, language="sql")
    st.caption(f"Arquivo: `{target.relative_to(target.parents[3])}`")

    n_params = sql_text.count("?")
    parquets = _list_known_parquets()

    params: list[str] = []
    if n_params > 0 and not parquets:
        st.warning("Nenhum parquet encontrado em `data/staging/` ou `data/bronze/`.")
        return

    for i in range(n_params):
        params.append(
            st.selectbox(
                f"Parâmetro {i + 1} (path do parquet)",
                parquets,
                key=f"queries_param_{choice}_{i}",
            )
        )

    if st.button("Run", key=f"queries_run_{choice}"):
        con = _connect()
        try:
            df = con.execute(sql_text, params).fetchdf()
            st.dataframe(df, hide_index=True, use_container_width=True)
        except Exception as exc:
            st.error(f"Erro ao executar: {exc}")
        finally:
            con.close()


def main() -> None:
    st.title("terrasync · status")
    st.caption(Path.cwd().as_posix())

    selection = _sidebar_filter()
    bronze_rows = _filter_rows(scan_bronze(), selection)
    staging_rows = scan_staging()
    runs_df = read_runs(runs_mtime())

    tab_overview, tab_bronze, tab_staging, tab_runs, tab_queries = st.tabs(
        ["Visão geral", "Bronze health", "Staging health", "Run history", "Queries"]
    )
    with tab_overview:
        _tab_overview(bronze_rows, runs_df)
    with tab_bronze:
        _tab_bronze(bronze_rows, selection)
    with tab_staging:
        _tab_staging(staging_rows, bronze_rows)
    with tab_runs:
        _tab_runs(runs_df)
    with tab_queries:
        _tab_queries()


main()
