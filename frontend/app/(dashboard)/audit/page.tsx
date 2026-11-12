'use client';
import { useState, useEffect, useCallback } from 'react';
import { api, AuditLogList } from '@/lib/api';
import { formatDateTime } from '@/lib/utils';
import { toast } from 'sonner';

export default function AuditPage() {
  const [data, setData] = useState<AuditLogList | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.getAuditLogs({ page, page_size: 50 });
      setData(result);
    } catch (err: any) {
      toast.error('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
        <p className="text-gray-500 text-sm">{data?.total ?? 0} total events</p>
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
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Action</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Resource</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Description</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data?.items.map(log => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium bg-gray-100 text-gray-700 px-2 py-0.5 rounded font-mono">
                      {log.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-600">
                    {log.resource_type && <span>{log.resource_type}</span>}
                    {log.resource_id && (
                      <span className="text-gray-400 ml-1">#{log.resource_id.slice(-8)}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">{log.description}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">{formatDateTime(log.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data?.total === 0 && (
            <div className="text-center py-12 text-gray-500 text-sm">No audit events yet.</div>
          )}
          {data && data.total > 50 && (
            <div className="flex justify-between items-center px-4 py-3 border-t border-gray-200">
              <span className="text-sm text-gray-500">Page {page}</span>
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
