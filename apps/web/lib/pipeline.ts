// Shared types, labels and date helpers for the pipeline screens (Leads, Cold calls, Meetings, Tickets).

export interface Person { id: string; name: string; }

export interface Lead {
  id: string; contact_name: string; company: string | null; phone: string | null; email: string | null; city: string | null;
  industry: string | null; website: string | null; source: string; notes: string | null; status: string; status_reason: string | null;
  created_by: Person | null; caller: Person | null; closer: Person | null; call_attempts: number;
  last_called_at: string | null; next_call_at: string | null; qualified_at: string | null; created_at: string;
  last_call?: { outcome: string; notes: string | null; at: string };
  due?: boolean; unassigned?: boolean;
}

export interface CallEntry { outcome: string; notes: string | null; at: string; by: Person | null; }

export const LEAD_STATUS: Record<string, string> = {
  new: "New", qualified: "Qualified", disqualified: "Rejected", contacted: "No answer yet", callback: "Call back",
  not_interested: "Not interested", meeting_booked: "Meeting booked", won: "Won", lost: "Lost",
};

export const SOURCES: Record<string, string> = {
  manual: "Added by hand", import: "Imported list", website: "Website", referral: "Referral", social: "Social media",
  cold_list: "Cold list", event: "Event", other: "Other",
};

export const CALL_OUTCOMES: { id: string; label: string }[] = [
  { id: "no_answer", label: "No answer" }, { id: "busy", label: "Busy" }, { id: "callback", label: "Call back later" },
  { id: "interested", label: "Interested" }, { id: "meeting_booked", label: "Meeting booked" },
  { id: "not_interested", label: "Not interested" }, { id: "wrong_number", label: "Wrong number" },
];
export const OUTCOME_LABEL = Object.fromEntries(CALL_OUTCOMES.map((o) => [o.id, o.label]));

export const MODES: Record<string, string> = { google_meet: "Google Meet", zoom: "Zoom", phone: "Phone", in_person: "In person", other: "Other" };
export const PRIORITIES: Record<string, string> = { urgent: "Urgent", high: "High", normal: "Normal", low: "Low" };
export const TICKET_STATUS: { id: string; label: string }[] = [
  { id: "todo", label: "To do" }, { id: "in_progress", label: "In progress" }, { id: "review", label: "Review" }, { id: "done", label: "Done" },
];

const dt = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const d = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });
const t = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
export const fmtDateTime = (s: string | null) => (s ? dt.format(new Date(s)) : "—");
export const fmtDate = (s: string | null) => (s ? d.format(new Date(s)) : "—");
export const fmtTime = (s: string) => t.format(new Date(s));

/** "in 2 h", "3 d ago", "now": short relative time for queues. */
export function relative(s: string | null): string {
  if (!s) return "—";
  const mins = Math.round((new Date(s).getTime() - Date.now()) / 60000);
  const abs = Math.abs(mins);
  const v = abs < 1 ? null : abs < 60 ? `${abs} min` : abs < 1440 ? `${Math.round(abs / 60)} h` : `${Math.round(abs / 1440)} d`;
  if (!v) return "now";
  return mins > 0 ? `in ${v}` : `${v} ago`;
}

/** Day heading for grouped lists: Today, Tomorrow, or the date. */
export function dayLabel(s: string): string {
  const day = new Date(s); day.setHours(0, 0, 0, 0);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff = Math.round((day.getTime() - today.getTime()) / 86400000);
  return diff === 0 ? "Today" : diff === 1 ? "Tomorrow" : diff === -1 ? "Yesterday" : d.format(day);
}

/** <input type="datetime-local"> value for a Date (local time), and back to an ISO string with offset. */
export function toLocalInput(date: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}T${p(date.getHours())}:${p(date.getMinutes())}`;
}
export const fromLocalInput = (v: string) => new Date(v).toISOString();

export function tomorrowAt(hour: number): string {
  const x = new Date(); x.setDate(x.getDate() + 1); x.setHours(hour, 0, 0, 0);
  return toLocalInput(x);
}
