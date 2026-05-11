import { useState, useEffect } from 'react'
import { fetchAgentDetail } from '../../api/client'

export default function AgentPanel({ agent }) {
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    let cancelled = false
    const id = agent?.agent_id
    const request = id ? fetchAgentDetail(id) : Promise.resolve(null)
    request.then((data) => {
      if (!cancelled) setDetail(data)
    })
    return () => {
      cancelled = true
    }
  }, [agent?.agent_id])

  if (!agent) {
    return (
      <p className="text-sm italic text-[#9c7e5f]">Hover or tap an agent to see their details</p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold italic">{agent.agent_name}</h2>
          {agent.mood && (
            <span className="rounded-full border border-[#d4bc8a] bg-[#f5edcf] px-2.5 py-0.5 text-xs font-medium capitalize">
              {agent.mood}
            </span>
          )}
        </div>
        {detail?.bio && <p className="mt-0.5 text-xs italic text-[#b09070]">{detail.bio}</p>}
        {agent.location_name && (
          <p className="mt-2 text-sm text-[#9c7e5f]">{agent.location_name}</p>
        )}
        {agent.location_description && (
          <p className="mt-0.5 text-xs text-[#b09070]">{agent.location_description}</p>
        )}
      </div>

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

      {detail?.todays_plan?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-[#9c7e5f]">
            Today's Plan
          </p>
          <ol className="mt-1 flex flex-col gap-0.5">
            {detail.todays_plan.map((item, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="shrink-0 text-[#9c7e5f]">{i + 1}.</span>
                <span>{item}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
