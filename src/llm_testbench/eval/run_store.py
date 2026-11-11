"""Run history in Postgres (phase 2.7): every run of the harness, queryable in SQL.

The archive in ``data/results/runs/`` keeps the latest full run of each arm, versioned with
the code. This table keeps **every** run, sample runs included, with the per-query scores:
it answers "what did this arm score last week" and "on which queries did it lose".
"""

import json
from importlib import resources
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from llm_testbench.eval.retrieval import QueryResult, RetrievalRun

SCHEMA_FILE = "001_runs.sql"


class RunStore:
    def __init__(self, url: str) -> None:
        self._url = url

    async def ensure_schema(self) -> None:
        schema = resources.files("llm_testbench.eval.sql").joinpath(SCHEMA_FILE).read_text()
        async with await AsyncConnection.connect(self._url, autocommit=True) as conn:
            await conn.execute(schema)

    async def save(self, run: RetrievalRun) -> None:
        """One transaction: a run is in the history with all its queries, or not at all."""
        record = run.model_dump(mode="json", exclude={"queries"})
        async with await AsyncConnection.connect(self._url) as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO eval_runs (run_id, created_at, suite, arm, dataset, publishable,"
                " git_sha, git_dirty, metrics, run)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    run.run_id,
                    run.created_at,
                    run.suite,
                    run.arm,
                    str(run.dataset["dataset"]),
                    run.publishable,
                    run.git_sha,
                    run.git_dirty,
                    json.dumps(record["metrics"]),
                    json.dumps(record),
                ),
            )
            await cur.executemany(
                "INSERT INTO eval_query_results (run_id, query_id, metrics, ranking, latency_ms)"
                " VALUES (%s, %s, %s, %s, %s)",
                [
                    (
                        run.run_id,
                        result.query_id,
                        json.dumps(result.metrics),
                        json.dumps(list(result.ranking)),
                        result.latency_ms,
                    )
                    for result in run.queries
                ],
            )

    async def get(self, run_id: str) -> RetrievalRun | None:
        async with (
            await AsyncConnection.connect(self._url) as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute("SELECT run FROM eval_runs WHERE run_id = %s", (run_id,))
            row = await cur.fetchone()
            if row is None:
                return None
            await cur.execute(
                "SELECT query_id, metrics, ranking, latency_ms FROM eval_query_results"
                " WHERE run_id = %s ORDER BY query_id",
                (run_id,),
            )
            queries = [QueryResult.model_validate(result) for result in await cur.fetchall()]
        return RetrievalRun.model_validate({**row["run"], "queries": queries})

    async def history(
        self, suite: str, arm: str | None = None, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        """The latest runs of a suite (or of one arm), newest first: id, date, commit and
        metric means. Rows, not objects: this is what a report or a ``psql`` session reads."""
        async with (
            await AsyncConnection.connect(self._url) as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                "SELECT run_id, created_at, arm, dataset, publishable, git_sha, git_dirty, metrics"
                " FROM eval_runs WHERE suite = %(suite)s"
                " AND (%(arm)s::text IS NULL OR arm = %(arm)s)"
                " ORDER BY created_at DESC LIMIT %(limit)s",
                {"suite": suite, "arm": arm, "limit": limit},
            )
            return list(await cur.fetchall())

    async def delete(self, run_id: str) -> None:
        async with await AsyncConnection.connect(self._url) as conn:
            await conn.execute("DELETE FROM eval_runs WHERE run_id = %s", (run_id,))
