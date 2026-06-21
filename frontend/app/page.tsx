"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type EventItem = {
  id: number;
  delivery_id: string;
  event_type: string;
  action: string | null;
  repository: string | null;
  sender: string | null;
  received_at: string;
};

type JobItem = {
  id: number;
  event_id: number;
  job_type: string;
  status: string;
  attempts: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

type EventDetail = EventItem & { payload: Record<string, unknown> };
type JobDetail = JobItem & { logs: Array<{ timestamp: string; message: string }> };

const API = "/api";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(value));
}

function statusClass(status: string): string {
  return `badge badge-${status.replace(/[^a-z]/g, "")}`;
}

export default function Home() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<EventDetail | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const headers = useMemo(() => {
    const output: Record<string, string> = {};
    if (token.trim()) output["X-RelayOps-Token"] = token.trim();
    return output;
  }, [token]);

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const response = await fetch(`${API}${path}`, {
      ...init,
      headers: { ...headers, ...(init.headers || {}) },
      cache: "no-store",
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Request failed with ${response.status}`);
    }
    return response.json();
  }, [headers]);

  const refresh = useCallback(async () => {
    try {
      setError("");
      const [nextEvents, nextJobs] = await Promise.all([
        request("/events?limit=30"),
        request("/jobs?limit=30"),
      ]);
      setEvents(nextEvents);
      setJobs(nextJobs);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    const saved = window.localStorage.getItem("relayops-dashboard-token");
    if (saved) setToken(saved);
  }, []);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 5000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  async function saveToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    window.localStorage.setItem("relayops-dashboard-token", token.trim());
    setLoading(true);
    // The effect below reloads data after the token state changes.
  }

  async function openEvent(id: number) {
    try {
      setSelectedEvent(await request(`/events/${id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load event");
    }
  }

  async function openJob(id: number) {
    try {
      setSelectedJob(await request(`/jobs/${id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load job");
    }
  }

  async function retryJob(id: number) {
    try {
      await request(`/jobs/${id}/retry`, { method: "POST" });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to retry job");
    }
  }

  async function replayEvent(id: number) {
    try {
      await request(`/events/${id}/replay`, { method: "POST" });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to replay event");
    }
  }

  const successJobs = jobs.filter((job) => job.status === "success").length;
  const failedJobs = jobs.filter((job) => ["failed", "queue_error"].includes(job.status)).length;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SELF-HOSTED WEBHOOK OBSERVABILITY</p>
          <h1>RelayOps</h1>
          <p className="subtitle">GitHub events, queued deployment jobs, and safe operational visibility.</p>
        </div>
        <div className="health">
          <span className="dot" />
          <span>Auto-refresh every 5s</span>
        </div>
      </header>

      <form className="token-form" onSubmit={saveToken}>
        <label htmlFor="token">Dashboard API token</label>
        <input
          id="token"
          type="password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Optional for local development"
        />
        <button type="submit">Save & refresh</button>
      </form>

      {error && <div className="alert">{error}</div>}

      <section className="metrics">
        <article><span>Webhook events</span><strong>{events.length}</strong><small>latest 30 deliveries</small></article>
        <article><span>Successful jobs</span><strong>{successJobs}</strong><small>worker completed</small></article>
        <article><span>Failed / queue errors</span><strong>{failedJobs}</strong><small>needs attention</small></article>
        <article><span>Last refresh</span><strong className="time">{lastUpdated ? lastUpdated.toLocaleTimeString() : "—"}</strong><small>browser dashboard</small></article>
      </section>

      <section className="grid">
        <section className="panel">
          <div className="panel-heading"><div><h2>Webhook deliveries</h2><p>GitHub delivery history stored in PostgreSQL.</p></div><button onClick={refresh}>Refresh</button></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Event</th><th>Repository</th><th>Sender</th><th>Received</th><th /></tr></thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td><span className="badge badge-event">{event.event_type}</span><br /><small>{event.action || "—"}</small></td>
                    <td>{event.repository || "—"}</td>
                    <td>{event.sender || "—"}</td>
                    <td>{formatDate(event.received_at)}</td>
                    <td><div className="actions"><button onClick={() => openEvent(event.id)}>View</button>{event.event_type === "push" && <button className="secondary" onClick={() => replayEvent(event.id)}>Replay</button>}</div></td>
                  </tr>
                ))}
                {!loading && events.length === 0 && <tr><td colSpan={5} className="empty">No webhook events yet. Push a commit after configuring GitHub Webhooks.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading"><div><h2>Deployment jobs</h2><p>Redis queue processed asynchronously by Celery.</p></div></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Status</th><th>Event</th><th>Attempts</th><th>Created</th><th /></tr></thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td><span className={statusClass(job.status)}>{job.status}</span></td>
                    <td>#{job.event_id}</td>
                    <td>{job.attempts}</td>
                    <td>{formatDate(job.created_at)}</td>
                    <td><div className="actions"><button onClick={() => openJob(job.id)}>Logs</button>{["failed", "queue_error", "skipped"].includes(job.status) && <button className="secondary" onClick={() => retryJob(job.id)}>Retry</button>}</div></td>
                  </tr>
                ))}
                {!loading && jobs.length === 0 && <tr><td colSpan={5} className="empty">Push events create jobs automatically.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      </section>

      {selectedEvent && <div className="modal-backdrop" onClick={() => setSelectedEvent(null)}><section className="modal" onClick={(event) => event.stopPropagation()}><div className="modal-title"><h2>Event #{selectedEvent.id}</h2><button onClick={() => setSelectedEvent(null)}>Close</button></div><pre>{JSON.stringify(selectedEvent.payload, null, 2)}</pre></section></div>}
      {selectedJob && <div className="modal-backdrop" onClick={() => setSelectedJob(null)}><section className="modal" onClick={(event) => event.stopPropagation()}><div className="modal-title"><h2>Job #{selectedJob.id}</h2><button onClick={() => setSelectedJob(null)}>Close</button></div><div className="log-list">{selectedJob.logs.map((entry, index) => <div className="log-entry" key={`${entry.timestamp}-${index}`}><time>{entry.timestamp}</time><p>{entry.message}</p></div>)}{selectedJob.logs.length === 0 && <p>No logs yet.</p>}</div></section></div>}
    </main>
  );
}
