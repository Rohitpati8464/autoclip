import { useEffect, useRef, useState } from 'react'

import { api, type Job } from './api'

export interface StageProgress {
  stage: string
  stageProgress: number
  overall: number
  message: string
}

/**
 * Subscribe to a job's Server-Sent Event stream.
 *
 * EventSource reconnects on its own, and the server replays a snapshot on every
 * connection, so a dropped connection self-heals without any retry logic here.
 * The one thing worth guarding is a terminal state: once a job is done there is
 * nothing left to stream, and an open connection would just churn heartbeats.
 */
export function useJobStream(jobId: string | undefined) {
  const [job, setJob] = useState<Job | null>(null)
  const [progress, setProgress] = useState<StageProgress | null>(null)
  const [connected, setConnected] = useState(false)
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!jobId) return

    let cancelled = false

    // Fetch once up front so the page renders immediately rather than waiting
    // for the stream's first message.
    api
      .getJob(jobId)
      .then((initial) => {
        if (!cancelled) setJob(initial)
      })
      .catch(() => undefined)

    const source = new EventSource(`/api/jobs/${jobId}/events`)
    sourceRef.current = source

    const close = () => {
      source.close()
      setConnected(false)
    }

    source.onopen = () => setConnected(true)

    source.addEventListener('snapshot', (event) => {
      const data = JSON.parse((event as MessageEvent).data) as Job
      setJob(data)
      if (['done', 'failed', 'cancelled'].includes(data.status)) close()
    })

    source.addEventListener('progress', (event) => {
      const data = JSON.parse((event as MessageEvent).data)
      setProgress({
        stage: data.stage,
        stageProgress: data.stage_progress,
        overall: data.overall,
        message: data.message,
      })
      setJob((current) =>
        current
          ? { ...current, status: 'running', current_stage: data.stage, progress: data.overall }
          : current,
      )
    })

    const terminal = (status: Job['status']) => (event: Event) => {
      const data = JSON.parse((event as MessageEvent).data ?? '{}')
      setJob((current) =>
        current
          ? { ...current, status, error: data.error ?? null, progress: status === 'done' ? 1 : current.progress }
          : current,
      )
      close()
    }

    source.addEventListener('done', terminal('done'))
    source.addEventListener('failed', terminal('failed'))
    source.addEventListener('cancelled', terminal('cancelled'))

    source.onerror = () => setConnected(false)

    return () => {
      cancelled = true
      source.close()
      sourceRef.current = null
    }
  }, [jobId])

  return { job, progress, connected, setJob }
}
