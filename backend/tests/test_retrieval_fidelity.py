"""Focused regressions for recency and qualifiers at the bounded retrieval cap.

This is synthetic ranked-query output, not company evidence or a network test.
"""
from copy import deepcopy

from finn.brief import build_source_brief
from finn.retrieval import MAX_CONTEXT_PER_SECTION, SECTION_VOCAB, retrieve_section


class RankedPassageStore:
    """Supply equally relevant passages from six dated transcript versions."""

    def query(self, sql, params):
        if "bm25" not in sql:
            version = params[0]
            return [dict(passage_id=f"{version}_context", version_id=version,
                         page_index=1, printed_page=None, speaker="CEO",
                         text="The target concerns the commercial units excluding acquisitions and depends on the completion of contracts.")]
        version = params[1]
        return deepcopy([
            dict(passage_id=f"{version}_{index}", version_id=version,
                 page_index=index+2, seq=index, printed_page=None, speaker="CEO",
                 text=f"Growth guidance for {version}, operating area {index}, has a target around 5 percent and depends on commercial demand. "
                      "Details of the operating plan remain as described above. "*2,
                 score=-2)
            for index in range(2)
        ])


def versions():
    return [dict(version_id=f"v{year}", doc_type="earnings_call_transcript",
                 published_at=f"{year}-06-01T00:00:00+00:00", period_label=str(year),
                 identification={"management_speakers": ["CEO"]})
            for year in range(2019, 2025)]


def test_latest_guidance_stays_newest_first_after_six_version_cap():
    question = "What is latest growth guidance?"
    passages = retrieve_section(RankedPassageStore(), "management_commentary", versions(), question)
    brief = build_source_brief({"management_commentary": passages}, question)
    periods = [item.period_label for item in brief.highlights]
    assert periods and periods[0] == "2024"
    assert periods == sorted(periods, reverse=True)
    assert not {"2019", "2020", "2021"}.intersection(periods)


def test_cap_keeps_defining_lead_in_with_selected_newest_anchor():
    passages = retrieve_section(RankedPassageStore(), "management_commentary", versions(),
                                 "What is latest growth guidance?")
    by_id = {p["passage_id"]: p for p in passages}
    assert "v2024_0" in by_id
    assert "v2024_context" in by_id
    assert "excluding acquisitions" in by_id["v2024_context"]["text"]
    assert len(passages) <= SECTION_VOCAB["management_commentary"]["limit"] + MAX_CONTEXT_PER_SECTION


def test_preceding_caveat_stays_with_more_relevant_growth_sentence():
    source = ("However, our forecast excludes the acquisition and depends on a recovery in retail demand. "
              "Revenue growth is expected to be 20 percent in the coming year.")
    passage = dict(passage_id="conditional-growth", text=source, speaker="CEO",
                   doc_type="earnings_call_transcript", period_label="FY27", page_index=3)
    brief = build_source_brief({"management_commentary": [passage]}, "What is the revenue growth?")
    assert len(brief.highlights) == 1
    assert brief.highlights[0].quote == source
    assert brief.highlights[0].evidence_id == "conditional-growth"


def test_actor_specific_question_rejects_other_roles_and_keeps_negative_disclosure():
    def brief(text):
        return build_source_brief({"business_context": [dict(passage_id="role", text=text, speaker=None,
                    doc_type="annual_report", period_label="FY25", page_index=2)]}, "Why did the auditor resign?")
    assert not brief("The Chief Financial Officer resigned during the year. The board appointed a successor.").highlights
    assert not brief("A director resigned from the board. The auditors reviewed the financial statements.").highlights
    negative = "There has been no resignation of statutory auditors during the year."
    assert brief(negative).highlights[0].quote == negative


def test_following_short_chunk_qualification_keeps_its_own_citation(env):
    from finn.ingest import ingest_replay
    from finn.replay import classify_versions, load_manifest
    from finn.sources import nse
    from finn.sources.documents import chunk_page
    settings, store, fetcher, _ = env
    cfg = load_manifest(settings.manifest_path)
    ingest_replay(store, fetcher, settings, cfg, ["TESTCO"], log=lambda _:None)
    company = nse.resolve_company(store, "TESTCO")
    version = next(v for v in classify_versions(store, company.company_id, "replay", cfg.cutoff_utc)[0] if v['doc_type']=='earnings_call_transcript')
    condition = "However, this forecast excludes the acquisition and depends on retail demand recovering."
    headline = "Revenue growth guidance is 20 percent for the year. "
    headline += "Operating context remains as described. " * 33
    assert len(headline) < 1400 and len(headline + condition) > 1400
    chunks, _ = chunk_page(headline + '\n' + condition, True, "Asha Rao", {"Asha Rao"})
    assert len(chunks)==2 and len(chunks[1][0]) < 100
    store.execute('DELETE FROM passages_fts WHERE version_id=?', (version['version_id'],))
    store.execute('DELETE FROM passages WHERE version_id=?', (version['version_id'],))
    for seq,(text,speaker) in enumerate(chunks):
        pid=f'boundary-{seq}'
        store.insert('passages',dict(passage_id=pid,version_id=version['version_id'],page_index=2,seq=seq,
                    printed_page=None,speaker=speaker,text=text,extraction_status='extracted'))
        store.execute('INSERT INTO passages_fts(passage_id,version_id,text) VALUES (?,?,?)',(pid,version['version_id'],text))
    passages = retrieve_section(store, 'management_commentary', [version], 'What is the revenue growth guidance?')
    brief = build_source_brief({'management_commentary':passages},'What is the revenue growth guidance?')
    by_id={h.evidence_id:h.quote for h in brief.highlights}
    assert set(by_id)=={'boundary-0','boundary-1'}
    assert by_id['boundary-1']==condition
    assert all(quote in chunks[int(pid[-1])][0] for pid,quote in by_id.items())


def test_known_condition_is_not_silently_dropped_at_the_highlight_cap():
    ordinary = dict(passage_id='first', version_id='same', text='Revenue growth was steady during the year.',
                    speaker='CEO', doc_type='earnings_call_transcript', period_label='FY25', page_index=1)
    headline={**ordinary,'passage_id':'headline','text':'Revenue guidance is 20 percent.','_following_context_ids':['condition']}
    condition={**ordinary,'passage_id':'condition','text':'However, this forecast excludes the acquisition.'}
    another={**ordinary,'passage_id':'second','text':'Revenue grew steadily in the prior quarter.'}
    # The headline/condition are one group even when other candidates compete
    # for the section's three slots. Neither may be shown by itself.
    briefs=build_source_brief({'management_commentary':[ordinary,another,headline,condition]},'What is revenue guidance?')
    ids={h.evidence_id for h in briefs.highlights}
    assert ('headline' in ids)==('condition' in ids)
    assert len(ids) <= 3


def test_page_break_leading_context_is_shown_with_its_continuation():
    prior = dict(passage_id='prior',version_id='call',speaker='CEO',page_index=4,seq=1,
                 doc_type='earnings_call_transcript',period_label='Q2 FY27',
                 text='Revenue growth guidance is 1 to 2 percent. The lower end assumes further',_context_for='anchor')
    anchor = {**prior,'passage_id':'anchor','page_index':5,'seq':0,
              'text':'deterioration in demand, while the upper end assumes improvement. Our operating margin guidance is 20 to 22 percent.',
              '_context_ids':['prior']}
    anchor.pop('_context_for')
    brief=build_source_brief({'management_commentary':[anchor,prior]},'What is the revenue and margin guidance and on what basis?')
    assert [h.evidence_id for h in brief.highlights]==['prior','anchor']
    assert brief.highlights[0].quote==prior['text'] and brief.highlights[1].quote==anchor['text']
    assert all(h.context_evidence_ids==['prior','anchor'] for h in brief.highlights)
