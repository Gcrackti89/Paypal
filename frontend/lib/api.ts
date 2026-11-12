const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

export function setToken(token: string): void {
  localStorage.setItem('access_token', token);
}

export function clearToken(): void {
  localStorage.removeItem('access_token');
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string, public code?: string) {
    super(detail);
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (auth) {
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = 'An error occurred';
    let code: string | undefined;
    try {
      const err = await res.json();
      detail = err.detail || detail;
      code = err.code;
    } catch {}
    if (res.status === 401) {
      clearToken();
      if (typeof window !== 'undefined') window.location.href = '/login';
    }
    throw new ApiError(res.status, detail, code);
  }
  if (res.status === 204) return {} as T;
  return res.json();
}

export const api = {
  // Auth
  register: (data: { email: string; password: string; full_name: string }) =>
    request<{ access_token: string; token_type: string; expires_in: number }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }, false),

  login: (data: { email: string; password: string }) =>
    request<{ access_token: string; token_type: string; expires_in: number }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }, false),

  logout: () => request('/auth/logout', { method: 'POST' }),

  getMe: () => request<User>('/auth/me'),

  // Dashboard
  getDashboardSummary: () => request<DashboardSummary>('/dashboard/summary'),

  // Invoices
  createDraft: (data: InvoiceDraftRequest) =>
    request<Invoice>('/invoices/drafts', { method: 'POST', body: JSON.stringify(data) }),

  listInvoices: (params: { page?: number; page_size?: number; status_filter?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params.page) q.set('page', String(params.page));
    if (params.page_size) q.set('page_size', String(params.page_size));
    if (params.status_filter) q.set('status_filter', params.status_filter);
    if (params.search) q.set('search', params.search);
    return request<InvoiceList>(`/invoices?${q}`);
  },

  getInvoice: (id: string) => request<Invoice>(`/invoices/${id}`),

  prepareSend: (invoiceId: string) =>
    request<ApprovalResponse>(`/invoices/${invoiceId}/send/prepare`, { method: 'POST' }),

  confirmSend: (invoiceId: string, approval_token: string) =>
    request<Invoice>(`/invoices/${invoiceId}/send/confirm`, {
      method: 'POST',
      body: JSON.stringify({ approval_token }),
    }),

  prepareReminder: (invoiceId: string) =>
    request<ApprovalResponse>(`/invoices/${invoiceId}/reminders/prepare`, { method: 'POST' }),

  confirmReminder: (invoiceId: string, approval_token: string) =>
    request(`/invoices/${invoiceId}/reminders/confirm`, {
      method: 'POST',
      body: JSON.stringify({ approval_token }),
    }),

  // AI Agent
  agentCommand: (data: { message: string; session_id?: string; conversation_history?: Array<{role: string; content: string}> }) =>
    request<AgentResponse>('/agent/commands', { method: 'POST', body: JSON.stringify(data) }),

  // Recovery
  runRecoveryScan: () => request<RecoveryScanResult>('/recovery/scan', { method: 'POST' }),

  getRecoveryQueue: (params?: { page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params?.page) q.set('page', String(params.page));
    if (params?.page_size) q.set('page_size', String(params.page_size));
    return request<{ items: RecoveryAction[]; total: number; has_next: boolean }>(`/recovery/queue?${q}`);
  },

  // Audit
  getAuditLogs: (params?: { page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params?.page) q.set('page', String(params.page));
    if (params?.page_size) q.set('page_size', String(params.page_size));
    return request<AuditLogList>(`/audit-logs?${q}`);
  },

  // Integrations
  getPaypalStatus: () => request<PaypalStatus>('/integrations/paypal/status'),

  // Settings
  getMerchantSettings: () => request<MerchantSettings>('/settings/merchant'),
  updateMerchantSettings: (data: Partial<MerchantSettings>) =>
    request('/settings/merchant', { method: 'PATCH', body: JSON.stringify(data) }),
};

// Types
export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface DashboardSummary {
  outstanding_amount: string;
  overdue_total: string;
  paid_total: string;
  open_invoices_count: number;
  overdue_count: number;
  recovery_queue_size: number;
  recent_recoveries: Array<{ id: string; invoice_id: string; action_type: string; executed_at: string }>;
}

export interface LineItem {
  id: string;
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
}

export interface Invoice {
  id: string;
  customer_name: string;
  customer_email: string;
  currency: string;
  total_amount: string;
  amount_due?: string;
  amount_paid?: string;
  local_status: string;
  paypal_invoice_id?: string;
  paypal_invoice_number?: string;
  paypal_status?: string;
  paypal_invoice_url?: string;
  due_date?: string;
  invoice_date?: string;
  note?: string;
  ai_created: boolean;
  reminder_count_total: number;
  items: LineItem[];
  created_at: string;
  updated_at: string;
  sent_at?: string;
  paid_at?: string;
}

export interface InvoiceList {
  items: Invoice[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface InvoiceDraftRequest {
  customer_name: string;
  customer_email: string;
  currency: string;
  line_items: Array<{ description: string; quantity: string; unit_price: string }>;
  due_date?: string;
  note?: string;
  ai_created?: boolean;
  ai_session_id?: string;
}

export interface ApprovalResponse {
  approval_token: string;
  action: string;
  payload_summary: string;
  expires_at: string;
  invoice_id: string;
}

export interface AgentResponse {
  session_id: string;
  message: string;
  extracted_data?: {
    customer_name?: string;
    customer_email?: string;
    currency: string;
    line_items?: Array<{ description: string; quantity: string; unit_price: string }>;
    due_date_days?: number;
    note?: string;
    is_complete: boolean;
    missing_fields: string[];
    clarification_needed?: string;
  };
  invoice_preview?: {
    customer_name?: string;
    customer_email?: string;
    currency: string;
    line_items: Array<{ description: string; quantity: string; unit_price: string; amount: string }>;
    total_amount: string;
    due_date?: string;
    note?: string;
  };
  ready_for_review: boolean;
  ai_available: boolean;
  error?: string;
}

export interface RecoveryAction {
  id: string;
  invoice_id: string;
  action_type: string;
  status: string;
  days_overdue?: number;
  previous_reminders: number;
  recommended_action?: string;
  draft_message?: string;
  error_message?: string;
  is_auto: boolean;
  created_at: string;
  executed_at?: string;
}

export interface RecoveryScanResult {
  scanned: number;
  overdue_found: number;
  recommendations: RecoveryAction[];
}

export interface AuditLog {
  id: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  description?: string;
  ip_address?: string;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface PaypalStatus {
  configured: boolean;
  environment: string;
  base_url: string;
  is_sandbox: boolean;
  has_webhook_id: boolean;
  client_id_prefix?: string;
}

export interface MerchantSettings {
  timezone: string;
  auto_reminders_enabled: boolean;
  reminder_days_before_due: number;
  reminder_days_after_due: number[];
  reminder_quiet_hours_start: number;
  reminder_quiet_hours_end: number;
  paypal_connected_at?: string;
  paypal_account_email?: string;
}
