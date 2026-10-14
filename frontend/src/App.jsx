import { useState } from 'react'

const startingTasks = [
  { id: 1, title: 'Gereksinimleri analiz et', agent: 'Master Agent', status: 'Hazır' },
  { id: 2, title: 'Arayüz bileşenlerini oluştur', agent: 'Frontend Agent', status: 'Bekliyor' },
  { id: 3, title: 'API ve veri modelini planla', agent: 'Backend Agent', status: 'Bekliyor' },
]

function App() {
  const [requirement, setRequirement] = useState('')
  const [tasks, setTasks] = useState(startingTasks)
  const [notice, setNotice] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    const text = requirement.trim()

    if (!text) {
      setNotice('Önce bir yazılım gereksinimi yaz.')
      return
    }

    setTasks((current) => [
      { id: Date.now(), title: text, agent: 'Master Agent', status: 'Yeni' },
      ...current,
    ])
    setRequirement('')
    setNotice('Gereksinim görev listesine eklendi.')
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-semibold text-violet-700">DISTRIBUTED AI</p>
            <h1 className="text-xl font-bold">Geliştirme Platformu</h1>
          </div>
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-700">
            Sistem hazır
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
        <section className="grid gap-6 md:grid-cols-[1.5fr_1fr]">
          <div className="rounded-2xl bg-gradient-to-br from-violet-700 to-indigo-800 p-8 text-white shadow-lg">
            <p className="text-sm font-medium text-violet-200">YENİ PROJE</p>
            <h2 className="mt-2 text-3xl font-bold">Fikrini görevlere dönüştür</h2>
            <p className="mt-3 max-w-xl text-violet-100">
              Yazılım ihtiyacını anlat. Master Agent işi analiz edip uygun ajanlara
              dağıtsın.
            </p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-3">
              <label htmlFor="requirement" className="sr-only">
                Yazılım gereksinimi
              </label>
              <textarea
                id="requirement"
                value={requirement}
                onChange={(event) => setRequirement(event.target.value)}
                placeholder="Örnek: Kitapları arayıp ödünç alabileceğim bir kütüphane uygulaması..."
                className="min-h-32 w-full rounded-xl border border-white/20 bg-white p-4 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-violet-300"
              />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-sm text-violet-200">{notice}</span>
                <button
                  type="submit"
                  className="rounded-xl bg-white px-5 py-3 font-semibold text-violet-800 hover:bg-violet-100"
                >
                  Görevleri oluştur
                </button>
              </div>
            </form>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm font-medium text-slate-500">AKTİF ÇALIŞMA</p>
            <h2 className="mt-2 text-2xl font-bold">Ajan durumu</h2>
            <div className="mt-6 space-y-4">
              <div className="flex items-center justify-between">
                <span>Master Agent</span>
                <span className="text-sm font-medium text-emerald-700">● Hazır</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Frontend Agent</span>
                <span className="text-sm font-medium text-amber-600">● Bekliyor</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Backend Agent</span>
                <span className="text-sm font-medium text-amber-600">● Bekliyor</span>
              </div>
            </div>
            <div className="mt-6 rounded-xl bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Görev sayısı</p>
              <p className="mt-1 text-3xl font-bold">{tasks.length}</p>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-violet-700">SPRINT 1</p>
              <h2 className="mt-1 text-2xl font-bold">Görev panosu</h2>
            </div>
            <span className="text-sm text-slate-500">{tasks.length} görev</span>
          </div>

          <div className="mt-5 divide-y divide-slate-100">
            {tasks.map((task) => (
              <article
                key={task.id}
                className="flex flex-wrap items-center justify-between gap-3 py-4"
              >
                <div>
                  <h3 className="font-semibold">{task.title}</h3>
                  <p className="mt-1 text-sm text-slate-500">Atanan ajan: {task.agent}</p>
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