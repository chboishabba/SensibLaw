from __future__ import annotations

from pathlib import Path

from src.wiki_timeline.revision_pack_summary import build_run_summary, human_summary


def test_revision_pack_summary_builds_triage_and_human_summary() -> None:
    payload = build_run_summary(
        schema_version='wiki_revision_pack_state_v0_3',
        pack_id='pack',
        run_id='run:1',
        state_db_path=Path('/tmp/state.sqlite'),
        out_dir=Path('/tmp/out'),
        counts={'baseline_initialized': 0, 'unchanged': 0, 'changed': 1, 'no_candidate_delta': 0, 'error': 0},
        candidate_pair_counts={'considered': 3, 'selected': 2, 'reported': 2},
        contested_graph_counts={'articles_with_graphs': 1, 'graphs_built': 1, 'regions_detected': 4, 'cycles_detected': 2},
        article_results=[
            {
                'article_id': 'article_1',
                'title': 'Example',
                'status': 'changed',
                'top_severity': 'high',
                'selected_primary_pair_kind': 'largest_delta_in_window',
                'selected_primary_pair_id': 'pair:1',
                'selected_primary_pair_score': 88.0,
                'candidate_pairs_selected': 2,
                'report_path': '/tmp/pair.json',
                'pair_reports': [
                    {
                        'pair_id': 'pair:1',
                        'pair_kind': 'largest_delta_in_window',
                        'pair_kinds': ['largest_delta_in_window'],
                        'older_revid': 1,
                        'newer_revid': 2,
                        'candidate_score': 88.0,
                        'top_severity': 'high',
                        'pair_report_path': '/tmp/pair.json',
                        'top_changed_sections': [{'section': 'History', 'touched_bytes': 1200}],
                    }
                ],
                'contested_graph_path': '/tmp/graph.json',
                'contested_graph_summary': {
                    'region_count': 4,
                    'cycle_count': 2,
                    'selected_pair_count': 2,
                    'graph_heat': 888.0,
                    'hottest_region': {'region_id': 'region:history'},
                    'top_cycles': [{'cycle_id': 'cycle:1', 'region_id': 'region:history', 'region_title': 'History', 'touch_count': 2, 'highest_severity': 'high'}],
                    'top_regions': [{'region_id': 'region:history', 'title': 'History', 'touch_count': 2, 'total_touched_bytes': 1200, 'highest_severity': 'high'}],
                },
                'previous_revid': 1,
                'current_revid': 2,
            }
        ],
    )

    assert payload['highest_severity'] == 'high'
    assert payload['pack_triage']['top_changed_articles'][0]['article_id'] == 'article_1'
    assert payload['pack_triage']['top_high_severity_pairs'][0]['pair_kind'] == 'largest_delta_in_window'
    assert payload['pack_triage']['top_sections_changed'][0]['section'] == 'History'

    text = human_summary(payload)
    assert 'pack=pack run=run:1' in text
    assert 'top_articles=article_1:high:largest_delta_in_window' in text


def test_revision_pack_runner_imports_shared_summary_owner() -> None:
    runner = (Path(__file__).resolve().parents[1] / 'src' / 'wiki_timeline' / 'revision_pack_runner.py').read_text(encoding='utf-8')
    assert 'from src.wiki_timeline.revision_pack_summary import (' in runner
    assert 'build_run_summary(' in runner
    assert 'return _human_summary(payload)' in runner
