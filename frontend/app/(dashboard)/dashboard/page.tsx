'use client';
import { useEffect, useState } from 'react';
import { api, DashboardSummary } from '@/lib/api';
import { formatCurrency, formatDateTime } from '@/lib/utils';
import { DollarSign, AlertTriangle, CheckCircle2, FileText, Zap, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

function StatCard({ title, value, subtitle, icon: Icon, color }: {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 flex items-start gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon className="h-6 w-6" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const fetchSummary = async () => {
    try {
      const data = await api.getDashboardSummary();
      setSummary(data);
    } catch (err: any) {
      toast.error('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSummary(); }, []);

  const runScan = async () => {
    setScanning(true);
    try {
      const result = await api.runRecoveryScan();
      toast.success(`Scan complete: ${result.overdue_found} overdue invoice(s) found`);
      fetchSummary();
    } catch (err: any) {
      toast.error(err.message || 'Scan failed');
    } finally {
      setScanning(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" /></div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 text-sm">Revenue recovery overview</p>
        </div>
        <button
          onClick={runScan} disabled={scanning}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          <RefreshCw className={`h-4 w-4 ${scanning ? 'animate-spin' : ''}`} />
          {scanning ? 'Scanning...' : 'Run Recovery Scan'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          title="Outstanding"
          value={formatCurrency(summary?.outstanding_amount || '0')}
          subtitle={`${summary?.open_invoices_count || 0} open invoices`}
          icon={DollarSign}
          color="bg-blue-100 text-blue-600"
        />
        <StatCard
          title="Overdue"
          value={formatCurrency(summary?.overdue_total || '0')}
          subtitle={`${summary?.overdue_count || 0} invoices past due`}
          icon={AlertTriangle}
          color="bg-red-100 text-red-600"
        />
        <StatCard
          title="Collected"
          value={formatCurrency(summary?.paid_total || '0')}
          subtitle="Total paid"
          icon={CheckCircle2}
          color="bg-green-100 text-green-600"
        />
        <StatCard
          title="Recovery Queue"
          value={String(summary?.recovery_queue_size || 0)}
          subtitle="Pending actions"
          icon={Zap}
          color="bg-orange-100 text-orange-600"
        />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Recovery Actions</h2>
        {summary?.recent_recoveries?.length ? (
          <div className="space-y-3">
            {summary.recent_recoveries.map(r => (
              <div key={r.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div>
                  <span className="text-sm font-medium text-gray-800">{r.action_type.replace(/_/g, ' ')}</span>
                  <span className="text-xs text-gray-500 ml-2">Invoice #{r.invoice_id.slice(-8)}</span>
                </div>
                <span className="text-xs text-gray-400">{formatDateTime(r.executed_at)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm text-center py-8">No recovery actions yet. Run a scan to find overdue invoices.</p>
        )}
      </div>
    </div>
  );
}
