import { useEffect, useState } from 'react'
import { getAgents } from './api/client'

const STATUS_STYLE = {
  idle: { text: 'Idle', color: 'text-emerald-700' },
  busy: { text: 'Busy', color: 'text-amber-600' },
  offline: { text: 'Offline', color: 'text-slate-500' },
}

const startingTasks = [
  { id: 1, title: 'Analyze requirements', agent: 'Master Agent', status: 'Ready' },
  { id: 2, title: 'Build UI components', agent: 'Frontend Agent', status: 'Waiting' },
  { id: 3, title: 'Plan API and data model', agent: 'Backend Agent', status: 'Waiting' },
]

function App() {
  const [requirement, setRequirement] = useState('')
  const [tasks, setTasks] = useState(startingTasks)
  const [notice, setNotice] = useState('')
  const [agents, setAgents] = useState([])
  const [agentsError, setAgentsError] = useState('')
  const [agentsLoading, setAgentsLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const list = await getAgents()
        if (active) {
          setAgents(list)
          setAgentsError('')
        }
      } catch (error) {
        if (active) setAgentsError(error.message)
      } finally {
        if (active) setAgentsLoading(false)
      }
    }
    load()
    const timer = setInterval(load, 3000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  function handleSubmit(event) {
    event.preventDefault()
    const text = requirement.trim()

    if (!text) {
      setNotice('Write a software requirement first.')
      return
    }

    setTasks((current) => [
      { id: Date.now(), title: text, agent: 'Master Agent', status: 'New' },
      ...current,
    ])
    setRequirement('')
    setNotice('Requirement added to the task list.')
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-semibold text-violet-700">DISTRIBUTED AI</p>
            <h1 className="text-xl font-bold">Development Platform</h1>
          </div>
          {agentsError ? (
            <span className="rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-700">
              Master unreachable
            </span>
          ) : (
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-700">
              {agentsLoading ? 'Connecting...' : 'Master connected'}
            </span>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
        <section className="grid gap-6 md:grid-cols-[1.5fr_1fr]">
          <div className="rounded-2xl bg-gradient-to-br from-violet-700 to-indigo-800 p-8 text-white shadow-lg">
            <p className="text-sm font-medium text-violet-200">NEW PROJECT</p>
            <h2 className="mt-2 text-3xl font-bold">Turn your idea into tasks</h2>
            <p className="mt-3 max-w-xl text-violet-100">
              Describe the software you need. The master agent analyzes it and
              distributes the work to suitable agents.
            </p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-3">
              <label htmlFor="requirement" className="sr-only">
                Software requirement
              </label>
              <textarea
                id="requirement"
                value={requirement}
                onChange={(event) => setRequirement(event.target.value)}
                placeholder="Example: A library app where I can search and borrow books..."
                className="min-h-32 w-full rounded-xl border border-white/20 bg-white p-4 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-violet-300"
              />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-sm text-violet-200">{notice}</span>
                <button
                  type="submit"
                  className="rounded-xl bg-white px-5 py-3 font-semibold text-violet-800 hover:bg-violet-100"
                >
                  Create tasks
                </button>
              </div>
            </form>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm font-medium text-slate-500">LIVE</p>
            <h2 className="mt-2 text-2xl font-bold">Agent status</h2>
            <div className="mt-6 space-y-4">
              {agentsLoading && <p className="text-sm text-slate-500">Loading agents...</p>}
              {agentsError && (
                <p role="alert" className="text-sm text-red-700">
                  Cannot reach master: {agentsError}
                </p>
              )}
              {!agentsLoading && !agentsError && agents.length === 0 && (
                <p className="text-sm text-slate-500">No agents registered yet.</p>
              )}
              {agents.map((agent) => {
                const style = STATUS_STYLE[agent.status] ?? STATUS_STYLE.offline
                return (
                  <div key={agent.agent_id} className="flex items-center justify-between">
                    <span>
                      {agent.name}
                      <span className="ml-2 text-xs text-slate-500">{agent.model}</span>
                    </span>
                    <span className={`text-sm font-medium ${style.color}`}>● {style.text}</span>
                  </div>
                )
              })}
            </div>
            <div className="mt-6 rounded-xl bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Task count</p>
              <p className="mt-1 text-3xl font-bold">{tasks.length}</p>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-violet-700">SPRINT 1</p>
              <h2 className="mt-1 text-2xl font-bold">Task board</h2>
            </div>
            <span className="text-sm text-slate-500">{tasks.length} tasks</span>
          </div>

          <div className="mt-5 divide-y divide-slate-100">
            {tasks.map((task) => (
              <article
                key={task.id}
                className="flex flex-wrap items-center justify-between gap-3 py-4"
              >
                <div>
                  <h3 className="font-semibold">{task.title}</h3>
                  <p className="mt-1 text-sm text-slate-500">Assigned agent: {task.agent}</p>
                </div>
                <span className="rounded-full bg-violet-100 px-3 py-1 text-sm font-medium text-violet-700">
                  {task.status}
                </span>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}

export default App