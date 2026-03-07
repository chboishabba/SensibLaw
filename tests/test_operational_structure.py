from __future__ import annotations

from src.text.operational_structure import collect_operational_structure_occurrences
from src.text.structure_index import collect_structure_occurrences


def test_operational_structure_detects_chat_shell_and_transcript_refs():
    text = (
        "User: please run this.\n"
        "Assistant: ok.\n"
        "$ npm run dev -- --host 0.0.0.0 --port 4173\n"
        "ITIR_DB_PATH=.cache_local/itir.sqlite\n"
        "See ./SensibLaw/tests/test_lexeme_layer.py\n"
        "Q: Where were you?\n"
        "A: At 01:23:45.\n"
    )
    pairs = {(occ.norm_text, occ.kind) for occ in collect_operational_structure_occurrences(text)}
    assert ("role:user", "role_ref") in pairs
    assert ("role:assistant", "role_ref") in pairs
    assert ("cmd:npm", "command_ref") in pairs
    assert ("flag:--host", "flag_ref") in pairs
    assert ("env:itir_db_path", "env_var_ref") in pairs
    assert ("path:sensiblaw_tests_test_lexeme_layer_py", "path_ref") in pairs
    assert ("qa:q", "qa_ref") in pairs
    assert ("qa:a", "qa_ref") in pairs
    assert ("ts:01:23:45", "timestamp_ref") in pairs


def test_operational_structure_detects_bracketed_chat_transcript_turns():
    text = "1/1/21, 10:00 AM - Alice: Happy New Year!\n1/1/21, 10:01 AM - Bob: <Media omitted>\n"
    pairs = {(occ.norm_text, occ.kind) for occ in collect_operational_structure_occurrences(text)}
    assert ("speaker:alice", "speaker_ref") in pairs
    assert ("speaker:bob", "speaker_ref") in pairs
    assert ("ts:2021_01_01_10_00", "timestamp_ref") in pairs
    assert ("ts:2021_01_01_10_01", "timestamp_ref") in pairs
    assert ("ts:10:00", "timestamp_ref") not in pairs
    assert ("ts:10:01", "timestamp_ref") not in pairs


def test_operational_structure_detects_telegram_style_bracketed_transcript_turns():
    text = (
        "[5/3/26 8:50\u202fpm] Dave: Thanks for the feedback.\n"
        "[6/3/26 10:00\u202fam] [[wikilinksbot]]: Q21169592 (https://www.wikidata.org/entity/Q21169592)\n"
        "[6/3/26 10:42\u202fam] chb: https://netflixtechblog.com/uda-unified-data-architecture-6a6aee261d8d\n"
    )
    pairs = {(occ.norm_text, occ.kind) for occ in collect_operational_structure_occurrences(text)}
    assert ("speaker:dave", "speaker_ref") in pairs
    assert ("speaker:wikilinksbot", "speaker_ref") in pairs
    assert ("speaker:chb", "speaker_ref") in pairs
    assert ("ts:2026_03_05_20_50", "timestamp_ref") in pairs
    assert ("ts:2026_03_06_10_00", "timestamp_ref") in pairs
    assert ("ts:2026_03_06_10_42", "timestamp_ref") in pairs
    assert ("msg:dave", "message_boundary_ref") in pairs
    assert ("msg:wikilinksbot", "message_boundary_ref") in pairs
    assert ("path:netflixtechblog_com_uda_unified_data_architecture_6a6aee261d8d", "path_ref") in pairs


def test_operational_structure_detects_transcript_time_ranges():
    text = "[00:00:00,030 -> 00:00:21,970] Thanks.\n"
    pairs = {(occ.norm_text, occ.kind) for occ in collect_operational_structure_occurrences(text)}
    assert ("tsrange:00_00_00_030__00_00_21_970", "timestamp_range_ref") in pairs
    assert ("ts:00:00:00", "timestamp_ref") not in pairs
    assert ("ts:00:00:21", "timestamp_ref") not in pairs


def test_combined_structure_index_includes_legal_and_operational_refs():
    text = (
        "User: cite Civil Liability Act 2002 (NSW) s 5B.\n"
        "$ pytest SensibLaw/tests/test_lexeme_layer.py -q\n"
    )
    pairs = {(occ.norm_text, occ.kind) for occ in collect_structure_occurrences(text)}
    assert ("role:user", "role_ref") in pairs
    assert ("cmd:pytest", "command_ref") in pairs
    assert ("act:civil_liability_act_2002_nsw", "act_ref") in pairs
    assert ("sec:5b", "section_ref") in pairs


def test_operational_structure_does_not_emit_shell_refs_for_plain_prose():
    text = "The assistant took a path through the argument and quoted a figure."
    assert not collect_operational_structure_occurrences(text)


def test_operational_structure_does_not_treat_dates_or_all_caps_slashes_as_paths():
    text = "Dates like 30/10/25 and labels like JSON/CSV or L0/L1/L2 should not be path refs."
    pairs = {(occ.norm_text, occ.kind) for occ in collect_operational_structure_occurrences(text)}
    assert all(kind != "path_ref" for _, kind in pairs)


def test_operational_structure_does_not_treat_plain_slash_prose_as_paths():
    text = "He struggles with dates/recollection/identity and conversation/answer in ordinary prose."
    pairs = {(occ.norm_text, occ.kind) for occ in collect_operational_structure_occurrences(text)}
    assert all(kind != "path_ref" for _, kind in pairs)


def test_operational_structure_does_not_treat_short_rate_like_strings_as_paths():
    text = "Rent was 240/wk and the shorthand should stay plain prose."
    pairs = {(occ.norm_text, occ.kind) for occ in collect_operational_structure_occurrences(text)}
    assert all(kind != "path_ref" for _, kind in pairs)


def test_operational_structure_normalizes_concatenated_http_urls_more_cleanly():
    text = "https://chatgpt.com/share/6731905f-2d84-8010-bf3a-2d3cfa1764a0Includes transcript."
    pairs = {(occ.norm_text, occ.kind) for occ in collect_operational_structure_occurrences(text)}
    assert ("path:chatgpt_com_share_6731905f_2d84_8010_bf3a_2d3cfa1764a0", "path_ref") in pairs
    assert all(norm != "path:chatgpt_com_share_6731905f_2d84_8010_bf3a_2d3cfa1764a0includes" for norm, _ in pairs)
