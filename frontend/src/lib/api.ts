// AegisFlow API client.
//
// One deliberate design choice: this file has zero React in it. Auth state,
// components, etc. all live elsewhere and call into these plain functions.
// That keeps the "how do I talk to the backend" logic testable and reusable
// outside of any one component's lifecycle.

export const API_BASE_URL = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types — mirrored 1:1 from the backend Pydantic schemas. Kept in this file
// rather than a separate types.ts because every one of these shapes is only
// meaningful in the context of the API calls that produce it.
// ---------------------------------------------------------------------------

export type UserRole = "admin" | "soc_analyst" | "viewer";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export type AlertSeverity = "low" | "medium" | "high" | "critical";
export type AlertStatus = "open" | "investigating" | "resolved";

export interface IndicatorDetail {
  indicator: string;
  type: string;
  severity: string;
  reputation: string | null;
  risk_score: number;
  cache_hit: boolean;
}

export interface Alert {
  id: string;
  alert_type: string;
  hostname: string | null;
  user: string | null;
  details: Record<string, unknown> | null;
  severity: AlertSeverity;
  mitre_technique: string | null;
  status: AlertStatus;
  raw_payload: Record<string, unknown>;
  extracted_indicators: string[];
  correlation_score: number;
  created_at: string;
}

export interface AlertWithDetails extends Alert {
  indicator_details: IndicatorDetail[];
}

export interface AlertListResponse {
  total: number;
  items: Alert[];
}

export interface AIReport {
  id: string;
  related_alert_id: string | null;
  summary: string | null;
  mitre_technique: string | null;
  recommended_actions: string[] | null;
  ai_provider_used: string | null;
  created_at: string;
}

export interface AIReportListResponse {
  total: number;
  items: AIReport[];
}

export interface Playbook {
  id: string;
  name: string;
  description: string | null;
  trigger_type: "automatic" | "manual";
  trigger_conditions: Record<string, unknown>[] | null;
  steps: Record<string, unknown>[] | null;
  is_active: boolean;
}

export interface PlaybookListResponse {
  total: number;
  items: Playbook[];
}

export interface PlaybookExecution {
  id: string;
  playbook_id: string | null;
  alert_id: string | null;
  executed_by: string | null;
  trigger_source: string;
  status: string;
  triggered_conditions: Record<string, unknown>[] | null;
  actions_taken: Record<string, unknown>[] | null;
  created_at: string;
}

export interface PlaybookExecutionListResponse {
  total: number;
  items: PlaybookExecution[];
}

export type IncidentSeverity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "open" | "in_progress" | "resolved" | "closed";

export interface RelatedAlertSummary {
  id: string;
  alert_type: string;
  hostname: string | null;
  severity: string;
  correlation_score: number | null;
  status: string;
}

export interface Incident {
  id: string;
  title: string;
  description: string | null;
  severity: IncidentSeverity;
  status: IncidentStatus;
  related_alert_id: string | null;
  assigned_to: string | null;
  created_at: string;
  resolved_at: string | null;
  related_alert: RelatedAlertSummary | null;
}

export interface IncidentListResponse {
  total: number;
  items: Incident[];
}

// ---------------------------------------------------------------------------
// Playbook builder constants — mirrored from the backend's fixed allow-lists
// (app/services/playbook_engine/rules.py and actions.py). These exist so a
// condition or step built in the UI can never reference a field, operator,
// or action the backend doesn't recognize. If the backend's allow-list ever
// changes, this needs updating too — it's intentionally NOT fetched from an
// endpoint, since the backend doesn't expose one, and duplicating a short
// fixed list here is simpler than adding one.
// ---------------------------------------------------------------------------

export const CONDITION_FIELDS = [
  "correlation_score",
  "severity",
  "alert_type",
  "status",
  "mitre_technique",
  "hostname",
] as const;

export const CONDITION_OPERATORS = ["==", "!=", ">", ">=", "<", "<=", "in", "contains"] as const;

export const PLAYBOOK_ACTIONS = [
  { name: "update_alert_status", auto: true, description: "Change the alert's status." },
  { name: "flag_indicator", auto: true, description: "Elevate severity on the alert's indicators." },
  { name: "create_incident", auto: true, description: "Open an Incident linked to this alert." },
  { name: "notify_analyst", auto: true, description: "Simulate notifying the SOC (no real channel wired up)." },
  { name: "isolate_host", auto: false, description: "Recommended only — no EDR integration exists." },
  { name: "disable_account", auto: false, description: "Recommended only — no IdP integration exists." },
  { name: "block_ip", auto: false, description: "Recommended only — no firewall integration exists." },
] as const;

// ---------------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------------

const ACCESS_TOKEN_KEY = "aegisflow_access_token";
const REFRESH_TOKEN_KEY = "aegisflow_refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function storeTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Low-level request helper
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Access tokens are short-lived (30 min). Rather than have every caller deal
// with 401s, a single 401 triggers one refresh attempt and the original
// request is replayed. If two requests 401 at once, they share the same
// in-flight refresh call instead of racing to refresh twice.
let refreshPromise: Promise<boolean> | null = null;

async function attemptRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) return false;
        const data = await res.json();
        storeTokens(data.access_token, data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean; // attach Authorization header (default true)
  params?: Record<string, string | number | boolean | undefined>;
}

async function request<T>(path: string, options: RequestOptions = {}, isRetry = false): Promise<T> {
  const { method = "GET", body, auth = true, params } = options;

  let url = `${API_BASE_URL}${path}`;
  if (params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) query.set(key, String(value));
    }
    const qs = query.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth && !isRetry) {
    const refreshed = await attemptRefresh();
    if (refreshed) {
      return request<T>(path, options, true);
    }
    clearTokens();
    throw new ApiError(401, "Session expired. Please log in again.");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const errBody = await res.json();
      detail = errBody.detail ?? detail;
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function login(email: string, password: string): Promise<void> {
  // The backend uses OAuth2PasswordRequestForm on this one endpoint, which
  // means form-urlencoded body with a "username" field — not JSON, and not
  // "email" — even though every other user-facing field in this app is email.
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);

  const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  if (!res.ok) {
    let detail = "Incorrect email or password";
    try {
      const errBody = await res.json();
      detail = errBody.detail ?? detail;
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }

  const data = await res.json();
  storeTokens(data.access_token, data.refresh_token);
}

export async function register(email: string, password: string): Promise<void> {
  await request("/api/v1/auth/register", {
    method: "POST",
    body: { email, password, role: "viewer" },
    auth: false,
  });
  // Registration always creates a viewer (the backend accepts a role field,
  // but a self-serve signup form shouldn't let someone hand themselves
  // admin — an admin promotes people after the fact).
  await login(email, password);
}

export async function getMe(): Promise<User> {
  return request<User>("/api/v1/auth/me");
}

export function logout(): void {
  clearTokens();
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export async function listAlerts(filters: {
  status?: AlertStatus;
  min_score?: number;
  skip?: number;
  limit?: number;
}): Promise<AlertListResponse> {
  return request<AlertListResponse>("/api/v1/alerts/", {
    params: {
      status: filters.status,
      min_score: filters.min_score,
      skip: filters.skip,
      limit: filters.limit,
    },
  });
}

export async function getAlert(alertId: string): Promise<AlertWithDetails> {
  return request<AlertWithDetails>(`/api/v1/alerts/${alertId}`);
}

export async function updateAlertStatus(alertId: string, status: AlertStatus): Promise<Alert> {
  return request<Alert>(`/api/v1/alerts/${alertId}/status`, {
    method: "PATCH",
    body: { status },
  });
}

export async function generateDemoAlerts(count: number): Promise<Alert[]> {
  return request<Alert[]>("/api/v1/alerts/generate-demo", {
    method: "POST",
    body: { count },
  });
}

// ---------------------------------------------------------------------------
// AI Reports
// ---------------------------------------------------------------------------

export async function listAIReports(alertId: string): Promise<AIReportListResponse> {
  return request<AIReportListResponse>("/api/v1/ai-reports/", {
    params: { alert_id: alertId },
  });
}

export async function generateAIReport(alertId: string): Promise<AIReport> {
  return request<AIReport>(`/api/v1/ai-reports/generate/${alertId}`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Playbooks
// ---------------------------------------------------------------------------

export async function listActivePlaybooks(): Promise<PlaybookListResponse> {
  return request<PlaybookListResponse>("/api/v1/playbooks/", {
    params: { is_active: true, limit: 200 },
  });
}

export async function listPlaybooks(filters: {
  is_active?: boolean;
  skip?: number;
  limit?: number;
} = {}): Promise<PlaybookListResponse> {
  return request<PlaybookListResponse>("/api/v1/playbooks/", {
    params: { is_active: filters.is_active, skip: filters.skip, limit: filters.limit ?? 200 },
  });
}

export interface PlaybookInput {
  name: string;
  description?: string | null;
  trigger_type: "automatic" | "manual";
  trigger_conditions?: Record<string, unknown>[] | null;
  steps: Record<string, unknown>[];
  is_active?: boolean;
}

export async function createPlaybook(payload: PlaybookInput): Promise<Playbook> {
  return request<Playbook>("/api/v1/playbooks/", { method: "POST", body: payload });
}

export async function updatePlaybook(
  playbookId: string,
  payload: Partial<PlaybookInput>
): Promise<Playbook> {
  return request<Playbook>(`/api/v1/playbooks/${playbookId}`, { method: "PATCH", body: payload });
}

export async function runPlaybookManually(
  playbookId: string,
  alertId: string
): Promise<PlaybookExecution> {
  return request<PlaybookExecution>(`/api/v1/playbooks/${playbookId}/run/${alertId}`, {
    method: "POST",
  });
}

export async function listExecutionsForAlert(alertId: string): Promise<PlaybookExecutionListResponse> {
  return request<PlaybookExecutionListResponse>("/api/v1/playbooks/executions/", {
    params: { alert_id: alertId, limit: 50 },
  });
}

export async function listRecentExecutions(limit = 10): Promise<PlaybookExecutionListResponse> {
  return request<PlaybookExecutionListResponse>("/api/v1/playbooks/executions/", {
    params: { limit },
  });
}

// ---------------------------------------------------------------------------
// Incidents
// ---------------------------------------------------------------------------

export async function listIncidents(filters: {
  status?: IncidentStatus;
  severity?: IncidentSeverity;
  skip?: number;
  limit?: number;
} = {}): Promise<IncidentListResponse> {
  return request<IncidentListResponse>("/api/v1/incidents/", {
    params: {
      status: filters.status,
      severity: filters.severity,
      skip: filters.skip,
      limit: filters.limit ?? 50,
    },
  });
}

export async function getIncident(incidentId: string): Promise<Incident> {
  return request<Incident>(`/api/v1/incidents/${incidentId}`);
}

export interface IncidentCreateInput {
  title: string;
  description?: string | null;
  severity: IncidentSeverity;
  related_alert_id?: string | null;
  assigned_to?: string | null;
}

export async function createIncident(payload: IncidentCreateInput): Promise<Incident> {
  return request<Incident>("/api/v1/incidents/", { method: "POST", body: payload });
}

export interface IncidentUpdateInput {
  title?: string;
  description?: string | null;
  severity?: IncidentSeverity;
  status?: IncidentStatus;
  assigned_to?: string | null;
}

export async function updateIncident(incidentId: string, payload: IncidentUpdateInput): Promise<Incident> {
  return request<Incident>(`/api/v1/incidents/${incidentId}`, { method: "PATCH", body: payload });
}
