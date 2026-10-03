"""Abel audio delivery profiles.

These profiles are the canonical style formulas used by lesson generation and
spoken-language QA. A lesson has exactly one primary delivery_mode unless a
multi-speaker mode is explicitly selected.

Modes:
- conversational_dialogue: two native speakers, asymmetric turns, real reactions,
  confirmations, questions, clarification, mild disagreement; standard Mandarin,
  natural everyday educated speech; HSK6 density preserved.
- interview: interviewer + expert; interviewer turns compact, expert turns developed;
  natural follow-up questions; no scripted equal-length turns.
- news_report: professional Mandarin news delivery; information-dense, controlled,
  formal vocabulary acceptable; spoken segmentation; restrained broadcast contour.
- announcement: official public-information delivery; concise, orderly, clear,
  information-first; no chatty fillers.
- lecture_explanation: educated professor/expert explaining aloud; logical exposition,
  examples, reformulation, contrast/consequence; conversational enough to sound spoken,
  not an essay read verbatim.
- narrative_story: natural storyteller; temporal progression, event focus, short
  reactions/evaluations; expressive but restrained.
- formal_informational: calm professional presenter/expert; relatively formal lexical
  register; spoken phrasing and intelligible segmentation.
- casual_explanation: one educated Chinese adult casually explaining an interesting
  topic to a friend/classmate; relaxed but standard Mandarin; no announcer/teacher style.

Voice formulas:
- single-speaker modes use Gemini TTS or the existing Chirp backend according to
  backend policy.
- conversational_dialogue uses Gemini TTS multi-speaker with:
    男 -> Puck
    女 -> Kore
  Both use cmn-CN and natural conversational delivery.
- interview uses the same two-voice architecture unless a single-speaker interview
  is explicitly requested.
- news_report may use a broadcast-style single voice.
- lecture_explanation/formal_informational use a calm educated single voice.
- announcement uses an official clear single voice.
- narrative_story uses a natural storytelling single voice.
- casual_explanation uses a relaxed conversational single voice.

All modes:
- never translate or rewrite the final script during TTS;
- never add English;
- preserve HSK6 vocabulary, syntax, facts and answer-bearing details;
- no SSML/stage directions in the lesson text;
- naturalness comes from information structure, phrasing and turn design, not filler.
"""
