You are extracting structured, evidence-only claims from ONE historical source document. You
have no other context, memory, or tools. Work only from the SOURCE text below.

The card you help build means "what this source says" — never canonical TTROS truth, never a
Liam intention unless Liam is the one speaking. A third party's advice or statement stays
attributed to that third party.

Return ONLY a single JSON object (no prose before or after, no markdown fences) with this exact
shape:

{
  "claims": [
    {
      "claim": "one sentence, in the claim's own terms",
      "type": "advice_received | liam_position | decision | commitment | third_party_statement | fact_asserted | offer_made | open_question",
      "attribution": "the speaker or author's name as it appears in the source, or one of: group_unattributed, speaker_unresolved",
      "status": "historical | current | superseded",
      "evidence": {
        "quote": "a short VERBATIM quote copied exactly from the source text below (after ordinary whitespace collapsing), long enough to be unambiguous, never paraphrased",
        "locator": "a short pointer to where this is in the source, e.g. the speaker label and which of their turns, or a nearby distinctive phrase"
      }
    }
  ],
  "card": {
    "one_line_description": "<=140 characters, will be used verbatim in an index",
    "summary": "<=120 words, neutral, evidence-only",
    "key_topics": ["short phrase", "..."],
    "who_said_what": ["Speaker — what they said or argued, attributed", "..."],
    "decisions": ["a decision recorded in the source"] ,
    "advice_and_opinions": ["advice or opinion received, attributed to who gave it"],
    "liam_positions": ["a position Liam himself stated, only if he actually stated it"],
    "commitments_and_actions": ["a commitment or action someone took on"],
    "open_questions": ["an open question or uncertainty left in the source"],
    "conflicts_and_caveats": ["a caveat, tension, or unresolved conflict in the source"],
    "promotion_candidates": ["a claim that might be worth canonical review later -- flagged only, never itself canonical"]
  }
}

Rules:
- Extract the most substantive 6-15 claims. Prioritize decisions, commitments, advice/opinions
  received, and positions Liam himself states, over incidental chit-chat.
- Every "quote" must be copied verbatim from the SOURCE text below -- do not paraphrase, do not
  correct grammar, do not translate. It must be an exact substring after collapsing runs of
  whitespace to single spaces.
- If the source genuinely does not let you identify who is speaking, use "group_unattributed" or
  "speaker_unresolved" for attribution -- never guess a name, never leave attribution blank.
- If "decisions" is empty, include the single string "none recorded" as its only element.
- Do not invent participants, dates, or outcomes not present in the source text.
- Never state or imply that a third party's advice, opinion, or statement is something Liam
  believes, intends, or decided, unless Liam is the one who said it.

SCHEMA_VERSION: source-intake-semantic-v1

=== SOURCE (verbatim, nothing else was provided to you) ===
{{SOURCE_TEXT}}
=== END SOURCE ===
