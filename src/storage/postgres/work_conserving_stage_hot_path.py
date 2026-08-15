"""Cheaper exact completion proof for work-conserving COPY stages.

Each partition writes its COPY rows and its `document_persistence_lane` staged
receipt in the same committed PostgreSQL transaction.  Consequently a complete
set of staged lane receipts whose row counts sum to the declared run row count
is an exact publication precondition; rescanning every provisional row merely to
COUNT them is redundant I/O.

This module also verifies READ COMMITTED and configures PostgreSQL gather width
once per ordered publication connection instead of once per persistence family.
"""

from __future__ import annotations

from typing import Any, Sequence


_INSTALL_MARKER = "_work_conserving_stage_hot_path_installed"


def install_work_conserving_stage_hot_path() -> bool:
    from src.storage.postgres import work_conserving_stage as stage

    if getattr(stage, _INSTALL_MARKER, False):
        return False

    def stage_payloads(
        cursor: Any,
        *,
        family_ref: str,
        lane_ref: str,
        payloads: Sequence[Any],
    ) -> str:
        runtime = stage._runtime()
        stage_ref = runtime.stage_ref(family_ref)
        try:
            dsn = str(cursor.connection.info.dsn)
        except AttributeError as error:  # pragma: no cover - compatibility seam
            raise RuntimeError(
                "PostgreSQL cursor does not expose a reusable DSN"
            ) from error
        runtime.register_stage(stage_ref=stage_ref, dsn=dsn)
        stage._prepare_stage(
            dsn=dsn,
            stage_ref=stage_ref,
            document_ref=runtime.document_ref,
            build_key_sha256=runtime.build_key_sha256,
            family_ref=family_ref,
            lane_ref=lane_ref,
            payloads=payloads,
            worker_budget=runtime.worker_budget,
        )

        # COPY and the corresponding staged lane receipt commit atomically on
        # each partition connection.  Prove complete coverage from that compact
        # ledger instead of scanning the provisional row table again.
        cursor.execute(
            """
            SELECT run.row_count,
                   run.lane_count,
                   COALESCE(SUM(lane.row_count), 0),
                   COUNT(lane.partition_no)
            FROM execution.document_persistence_run AS run
            LEFT JOIN execution.document_persistence_lane AS lane
              ON lane.stage_ref = run.stage_ref
             AND lane.lane_ref = %s
             AND lane.state_ref = 'staged'
            WHERE run.stage_ref = %s AND run.state_ref = 'staged'
            GROUP BY run.row_count, run.lane_count
            """,
            (lane_ref, stage_ref),
        )
        completeness = cursor.fetchone()
        if completeness is None:
            raise RuntimeError(
                "provisional persistence stage is incomplete before authority merge"
            )
        expected_rows, expected_lanes, staged_rows, staged_lanes = map(
            int, completeness
        )
        if expected_rows != staged_rows or expected_lanes != staged_lanes:
            raise RuntimeError(
                "provisional persistence lane ledger is incomplete before authority merge: "
                f"expected_rows={expected_rows} staged_rows={staged_rows} "
                f"expected_lanes={expected_lanes} staged_lanes={staged_lanes}"
            )

        connection_id = id(cursor.connection)
        verified = getattr(runtime, "_verified_publication_connections", None)
        if verified is None:
            verified = set()
            setattr(runtime, "_verified_publication_connections", verified)
        if connection_id not in verified:
            cursor.execute("SHOW transaction_isolation")
            isolation = str(cursor.fetchone()[0]).casefold().replace(" ", "_")
            if isolation != "read_committed":
                raise RuntimeError(
                    "parallel provisional staging requires READ COMMITTED visibility; "
                    f"observed={isolation}"
                )
            cursor.execute(
                "SELECT set_config('max_parallel_workers_per_gather', %s, true)",
                (str(runtime.worker_budget),),
            )
            # set_config participates in the same ordered pipeline.  A later
            # result observation or publication flush makes it effective before
            # any parallel authority query can depend on it.
            verified.add(connection_id)

        cursor.execute(
            """
            UPDATE execution.document_persistence_run
            SET state_ref = 'publishing'
            WHERE stage_ref = %s AND state_ref = 'staged'
            """,
            (stage_ref,),
        )
        return stage_ref

    stage._stage_payloads = stage_payloads
    setattr(stage, _INSTALL_MARKER, True)
    return True


__all__ = ["install_work_conserving_stage_hot_path"]
