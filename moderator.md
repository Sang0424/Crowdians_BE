# Moderator Contract

Crowdians moderator is a derived orchestration layer for agent-to-agent channel sessions.

Product role:

- The moderator is not a story engine or a psychology inference layer.
- Its job is to keep channel runs short, comparable, and useful for testing how agents react to a situation.
- Branches should support alternate-condition testing without polluting the original session context.

- Agent ownership lives in `app/services/agent_service.py`.
  Agent persona, model, and runtime mode belong to the agent.
  The current runtime mode field is persisted and exposed through the API contract, but execution still uses the platform Gemini path until provider-specific runtime adapters are added.
- Channel rules live in `app/services/channel_service.py`.
  Moderator decides who can speak next, when a branch can be forked, and when a session stops.
- Orchestration lives in `app/services/orchestrator.py`.
  It reads moderator state from `channel_service` and follows it instead of inventing parallel routing rules.

Current moderator guarantees:

- Only invited channel participants may speak.
- Turn order follows `channel.agents`.
- Consecutive turns from the same agent are blocked when multiple agents are present.
- A session branch stops after 15 messages and becomes `completed`.
- Interventions are branch-safe only when `fork_message_id` points to an existing message boundary.

## Prompt and Token Budget Contract

Moderator-generated execution context must be short, ranked, and budgeted.

Recommended default limits:

- Moderator-injected prompt budget per agent call: `400` input tokens max
- Total agent-call input budget including recent context and runtime persona: `900` input tokens max
- Agent output target: `120` tokens
- Agent output hard cap: `200` tokens

Recommended context split inside the input budget:

- Moderator scene/rule summary: `120-220` tokens
- Recent dialogue window: `250-350` tokens
- Runtime persona and relationship hints: `180-260` tokens
- Reserved overflow buffer: `50-150` tokens

Operational rationale:

- The moderator budget should be large enough to carry scenario, tone, and routing guidance without flooding the model.
- The output budget should favor 1-3 sentence conversational turns rather than long monologues.
- Crowdians is a multi-agent channel reaction simulation product; long per-turn outputs reduce comparability and make sessions feel like serial essays instead of useful agent reactions.

Output-style guidance for agent prompts:

- Prefer `1-3` sentences per turn.
- Respond to the latest message directly.
- Favor interaction over exposition.
- Expand only when the channel mode explicitly calls for long-form analysis or explanation.

Recommended exceptions:

- Analysis-heavy channels may raise the output hard cap above `200`.
- Fast reaction channels should keep the hard cap at or below `160`.
