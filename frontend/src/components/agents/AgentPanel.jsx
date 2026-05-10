export default function AgentPanel({ agent }) {
  if (!agent) {
    return (
      <p className="text-sm italic text-[#9c7e5f]">Hover or tap an agent to see their details</p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-bold italic">{agent.agent_name}</h2>
        {agent.location_name && (
          <p className="mt-0.5 text-sm text-[#9c7e5f]">{agent.location_name}</p>
        )}
      </div>

      {agent.mood && (
        <div>
          <span className="rounded-full border border-[#d4bc8a] bg-[#f5edcf] px-2.5 py-0.5 text-xs font-medium capitalize">
            {agent.mood}
          </span>
        </div>
      )}

      {agent.activity && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[#9c7e5f]">Activity</p>
          <p className="mt-0.5 text-sm italic">{agent.activity}</p>
        </div>
      )}

      {agent.inner_thought && (
        <div className="border-l-2 border-[#d4bc8a] pl-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#9c7e5f]">Thoughts</p>
          <p className="mt-0.5 text-sm text-[#6b4f35]">"{agent.inner_thought}"</p>
        </div>
      )}
    </div>
  )
}
