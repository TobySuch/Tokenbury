"""Event payload conventions (fixed for all milestones).

Payloads reference players by id, never by name; ``visibility.py`` converts
ids to names on the way out to prompts.

- wolf_message: {message, kill_target_id|null}   (wolf_chat, actor=wolf)
- wolf_target: {target_id, source: "agreed"|"engine_random"}   (wolf_chat, no actor)
- death: {player_id, cause: "night_kill"|"vote"|"heartbreak", role: str|null}   (public)
- protect: {target_id}   (player:<doctor>, actor=doctor)
- save_result: {saved: bool}   (player:<doctor>, no actor)
- peaceful_night: {}   (public; the wolves' target was protected)
- lover_message: {message}   (lovers, actor=lover)
- speech: {message}   (public, actor=speaker)
- pass: {phase}   (engine, actor)
- vote_cast: {target_id|null}   (engine, actor)
- vote_result: {votes: [{voter_id, target_id|null}], tally: {"<player_id>"|"none": n},
  eliminated_id|null}   (public; votes empty when votes_public is off)
- moderator_pick: {pick_id|null, end: bool, reason, source: "llm"|"fallback"|"forced"}   (engine)
- phase_change: {from, to}   (engine)
- game_over: {winner}   (public)
- notes_turn_done: {phase}   (engine, actor)
- role_assigned: {role, win_condition, wolf_label?, teammates?: [{name, label}],
  lover_name?, lovers_note?}   (player:<id>; wolves get wolf_label and teammates,
  lovers get lover_name (never the partner's role) and lovers_note)
"""
