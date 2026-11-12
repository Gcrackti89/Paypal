'use client';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api, RecoveryAction } from '@/lib/api';
import { RefreshCw, Bell, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

export default function RecoveryPage() {
  const router = useRouter();
  const [queue, setQueue] = useState<RecoveryAction[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getRecoveryQueue();
      setQueue(data.items);
      setTotal(data.total);
    } catch (err: any) {
      toast.error('Failed to load recovery queue');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);

  const runScan = async () => {
    setScanning(true);
    try {
      const result = await api.runRecoveryScan();
      toast.success(`Found ${result.overdue_found} overdue invoice(s)`);
      fetchQueue();
    } catch (err: any) {
      toast.error(err.message || 'Scan failed');
    } finally {
      setScanning(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Recovery Center</h1>
          <p className="text-gray-500 text-sm">{total} pending actions</p>
        </div>
        <button
          onClick={runScan}
          disabled={scanning}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          <RefreshCw className={`h-4 w-4 ${scanning ? 'animate-spin' : ''}`} />
          {scanning ? 'Scanning...' : 'Run Scan'}
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : queue.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Bell className="h-12 w-12 mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No pending recovery actions. Run a scan to find overdue invoices.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {queue.map(action => (
            <div key={action.id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="bg-red-100 text-red-700 text-xs font-medium px-2 py-0.5 rounded">
                      {action.days_overdue} days overdue
                    </span>
                    <span className="text-xs text-gray-500">{action.previous_reminders} reminders sent</span>
                  </div>
                  <p className="text-sm font-medium text-gray-900">{action.recommended_action}</p>
                  {action.draft_message && (
                    <div className="mt-2 p-3 bg-gray-50 rounded text-xs text-gray-600 font-mono whitespace-pre-wrap">
                      {action.draft_message}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => router.push(`/invoices/${action.invoice_id}`)}
                  className="flex items-center gap-1 text-sm text-blue-600 hover:underline ml-4"
                >
                  View Invoice <ChevronRight className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
