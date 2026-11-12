'use client';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api, InvoiceList } from '@/lib/api';
import { formatCurrency, formatDate, getStatusColor, daysOverdue } from '@/lib/utils';
import { Plus, Search } from 'lucide-react';
import { toast } from 'sonner';

const STATUS_OPTIONS = ['', 'DRAFT', 'PENDING', 'OVERDUE', 'PAID', 'CANCELLED'];

function EmptyFileText({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

export default function InvoicesPage() {
  const router = useRouter();
  const [data, setData] = useState<InvoiceList | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);

  const fetchInvoices = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listInvoices({
        page,
        page_size: 20,
        status_filter: status || undefined,
        search: search || undefined,
      });
      setData(result);
    } catch (err: any) {
      toast.error('Failed to load invoices');
    } finally {
      setLoading(false);
    }
  }, [page, status, search]);

  useEffect(() => { fetchInvoices(); }, [fetchInvoices]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Invoices</h1>
          <p className="text-gray-500 text-sm">{data?.total ?? 0} total invoices</p>
        </div>
        <button
          onClick={() => router.push('/ai-assistant')}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          <Plus className="h-4 w-4" />
          New Invoice
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search by name, email, or invoice #"
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={status}
          onChange={e => { setStatus(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s || 'All Status'}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Customer</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Amount</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Due Date</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Reminders</th>
                <th></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data?.items.map(inv => (
                <tr
                  key={inv.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => router.push(`/invoices/${inv.id}`)}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 text-sm">{inv.customer_name}</div>
                    <div className="text-xs text-gray-500">{inv.customer_email}</div>
                  </td>
                  <td className="px-4 py-3 text-sm font-medium">{formatCurrency(inv.total_amount, inv.currency)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(inv.local_status)}`}>
                      {inv.local_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {formatDate(inv.due_date)}
                    {inv.local_status === 'OVERDUE' && (
                      <span className="ml-1 text-xs text-red-500">({daysOverdue(inv.due_date)}d overdue)</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{inv.reminder_count_total}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-blue-600 hover:underline">View →</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data?.items.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <EmptyFileText className="h-12 w-12 mx-auto text-gray-300 mb-3" />
              <p>No invoices found</p>
              <button
                onClick={() => router.push('/ai-assistant')}
                className="mt-2 text-sm text-blue-600 hover:underline"
              >
                Create your first invoice
              </button>
            </div>
          )}
          {/* Pagination */}
          {data && data.total > 20 && (
            <div className="flex justify-between items-center px-4 py-3 border-t border-gray-200">
              <span className="text-sm text-gray-500">Page {page} of {Math.ceil(data.total / 20)}</span>
              <div className="flex gap-2">
                <button
                  disabled={page === 1}
                  onClick={() => setPage(p => p - 1)}
                  className="px-3 py-1 text-sm border rounded disabled:opacity-40"
                >
                  Prev
                </button>
                <button
                  disabled={!data.has_next}
                  onClick={() => setPage(p => p + 1)}
                  className="px-3 py-1 text-sm border rounded disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
