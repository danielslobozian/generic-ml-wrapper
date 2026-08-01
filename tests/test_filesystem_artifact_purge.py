# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem artifact purge: compiled contexts and transcripts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.filesystem_artifact_purge import (
    FilesystemArtifactPurge,
)
from generic_ml_wrapper.application.port.outbound.artifact_purge import ArtifactCounts

if TYPE_CHECKING:
    from pathlib import Path


def _seed(tmp_path: Path) -> FilesystemArtifactPurge:
    """Two jobs, each with two sessions; only ``alpha`` recorded transcripts."""
    contexts, transcripts = tmp_path / "contexts", tmp_path / "transcripts"
    for job in ("alpha", "beta"):
        (contexts / job).mkdir(parents=True)
        for index in (1, 2):
            (contexts / job / f"{job}_00{index}.context.md").write_text("ctx", encoding="utf-8")
    for index in (1, 2):
        folder = transcripts / "alpha" / f"alpha_00{index}"
        folder.mkdir(parents=True)
        for name in ("call_001.in.json", "call_001.out.sse", "call_001.usage.json"):
            (folder / name).write_text("{}", encoding="utf-8")
    return FilesystemArtifactPurge(contexts, transcripts)


def test_session_counts_cover_both_roots(tmp_path: Path) -> None:
    purge = _seed(tmp_path)

    assert purge.counts_for_session("alpha", "alpha_001") == ArtifactCounts(
        contexts=1, transcript_calls=3
    )


def test_job_counts_fold_over_the_whole_folder(tmp_path: Path) -> None:
    purge = _seed(tmp_path)

    assert purge.counts_for_job("alpha") == ArtifactCounts(contexts=2, transcript_calls=6)


def test_counts_are_zero_when_transcripts_were_never_recorded(tmp_path: Path) -> None:
    """Transcripts are opt-in: a job without them is not an error, it is a zero."""
    purge = _seed(tmp_path)

    assert purge.counts_for_job("beta") == ArtifactCounts(contexts=2, transcript_calls=0)
    assert purge.counts_for_session("beta", "beta_001") == ArtifactCounts(
        contexts=1, transcript_calls=0
    )


def test_counts_for_an_unknown_job_are_zero(tmp_path: Path) -> None:
    purge = _seed(tmp_path)

    assert purge.counts_for_job("gamma") == ArtifactCounts(contexts=0, transcript_calls=0)


def test_purging_a_session_removes_only_its_own_files(tmp_path: Path) -> None:
    purge = _seed(tmp_path)

    purge.purge_session("alpha", "alpha_001")

    assert not (tmp_path / "contexts" / "alpha" / "alpha_001.context.md").exists()
    assert not (tmp_path / "transcripts" / "alpha" / "alpha_001").exists()
    assert (tmp_path / "contexts" / "alpha" / "alpha_002.context.md").exists()
    assert (tmp_path / "transcripts" / "alpha" / "alpha_002").is_dir()


def test_purging_a_session_leaves_the_jobs_folders_standing(tmp_path: Path) -> None:
    """Even when it empties them — removing the folders is the job purge's business."""
    purge = _seed(tmp_path)

    for index in (1, 2):
        purge.purge_session("alpha", f"alpha_00{index}")

    assert (tmp_path / "contexts" / "alpha").is_dir()
    assert (tmp_path / "transcripts" / "alpha").is_dir()


def test_purging_a_job_removes_both_folders_whole(tmp_path: Path) -> None:
    purge = _seed(tmp_path)

    purge.purge_job("alpha")

    assert not (tmp_path / "contexts" / "alpha").exists()
    assert not (tmp_path / "transcripts" / "alpha").exists()
    assert (tmp_path / "contexts" / "beta").is_dir()


def test_purging_a_job_takes_residue_no_session_claims(tmp_path: Path) -> None:
    """A stray file under the job folder goes too — that residue is the whole point."""
    purge = _seed(tmp_path)
    (tmp_path / "contexts" / "alpha" / "leftover.md").write_text("x", encoding="utf-8")

    purge.purge_job("alpha")

    assert not (tmp_path / "contexts" / "alpha").exists()


def test_purging_what_is_not_there_is_a_no_op(tmp_path: Path) -> None:
    purge = _seed(tmp_path)

    purge.purge_job("gamma")
    purge.purge_session("beta", "beta_009")

    assert (tmp_path / "contexts" / "beta").is_dir()


def test_roots_that_do_not_exist_are_handled(tmp_path: Path) -> None:
    """Transcripts off since install: neither root has ever been created."""
    purge = FilesystemArtifactPurge(tmp_path / "nope", tmp_path / "also-nope")

    assert purge.counts_for_job("alpha") == ArtifactCounts(contexts=0, transcript_calls=0)
    purge.purge_job("alpha")
    purge.purge_session("alpha", "alpha_001")
