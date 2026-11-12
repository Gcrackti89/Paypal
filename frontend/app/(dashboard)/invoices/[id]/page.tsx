'use client';
import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api, Invoice, ApprovalResponse } from '@/lib/api';
import { formatCurrency, formatDate, formatDateTime, getStatusColor } from '@/lib/utils';
import { ExternalLink, Send, Bell, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [approval, setApproval] = useState<ApprovalResponse | null>(null);
  const [reminderApproval, setReminderApproval] = useState<ApprovalResponse | null>(null);
  const [acting, setActing] = useState(false);

  useEffect(() => {
    api.getInvoice(id)
      .then(setInvoice)
      .catch(() => toast.error('Failed to load invoice'))
      .finally(() => setLoading(false));
  }, [id]);

  const handlePrepareSend = async () => {
    setActing(true);
    try {
      const app = await api.prepareSend(id);
      setApproval(app);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setActing(false);
    }
  };

  const handleConfirmSend = async () => {
    if (!approval) return;
    setActing(true);
    try {
      const updated = await api.confirmSend(id, approval.approval_token);
      setInvoice(updated);
      setApproval(null);
      toast.success('Invoice sent successfully!');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setActing(false);
    }
  };

  const handlePrepareReminder = async () => {
    setActing(true);
    try {
      const app = await api.prepareReminder(id);
      setReminderApproval(app);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setActing(false);
    }
  };

  const handleConfirmReminder = async () => {
    if (!reminderApproval) return;
    setActing(true);
    try {
      await api.confirmReminder(id, reminderApproval.approval_token);
      const updated = await api.getInvoice(id);
      setInvoice(updated);
      setReminderApproval(null);
      toast.success('Reminder sent!');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setActing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Invoice not found</p>
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1 text-gray-500 hover:text-gray-900 text-sm mb-4"
      >
        <ArrowLeft className="h-4 w-4" /> Back
      </button>

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{invoice.customer_name}</h1>
            <p className="text-gray-500 text-sm">{invoice.customer_email}</p>
            {invoice.paypal_invoice_number && (
              <p className="text-xs text-gray-400 mt-1">#{invoice.paypal_invoice_number}</p>
            )}
          </div>
          <div className="text-right">
            <span className={`inline-flex px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(invoice.local_status)}`}>
              {invoice.local_status}
            </span>
            <p className="text-2xl font-bold text-gray-900 mt-2">
              {formatCurrency(invoice.total_amount, invoice.currency)}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-6 pt-4 border-t border-gray-100">
          <div>
            <p className="text-xs text-gray-500">Due Date</p>
            <p className="font-medium text-sm">{formatDate(invoice.due_date)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Sent</p>
            <p className="font-medium text-sm">{formatDateTime(invoice.sent_at)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Reminders</p>
            <p className="font-medium text-sm">{invoice.reminder_count_total}</p>
          </div>
        </div>

        {invoice.paypal_invoice_url && (
          <a
            href={invoice.paypal_invoice_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 flex items-center gap-1 text-sm text-blue-600 hover:underline"
          >
            <ExternalLink className="h-3.5 w-3.5" /> View on PayPal
          </a>
        )}
      </div>

      {/* Line Items */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
        <h2 className="font-semibold text-gray-900 mb-3">Line Items</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2 text-gray-500 font-medium">Description</th>
              <th className="text-right py-2 text-gray-500 font-medium">Qty</th>
              <th className="text-right py-2 text-gray-500 font-medium">Unit Price</th>
              <th className="text-right py-2 text-gray-500 font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {invoice.items.map(item => (
              <tr key={item.id} className="border-b border-gray-50">
                <td className="py-2">{item.description}</td>
                <td className="text-right py-2">{item.quantity}</td>
                <td className="text-right py-2">{formatCurrency(item.unit_price, invoice.currency)}</td>
                <td className="text-right py-2 font-medium">{formatCurrency(item.amount, invoice.currency)}</td>
              </tr>
            ))}
            <tr>
              <td colSpan={3} className="py-2 text-right font-semibold">Total</td>
              <td className="py-2 text-right font-bold text-lg">
                {formatCurrency(invoice.total_amount, invoice.currency)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Actions */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-3">Actions</h2>
        <div className="flex gap-3">
          {invoice.local_status === 'DRAFT' && !approval && (
            <button
              onClick={handlePrepareSend}
              disabled={acting}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-60"
            >
              <Send className="h-4 w-4" /> Send Invoice
            </button>
          )}
          {['PENDING', 'OVERDUE'].includes(invoice.local_status) && !reminderApproval && (
            <button
              onClick={handlePrepareReminder}
              disabled={acting}
              className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-60"
            >
              <Bell className="h-4 w-4" /> Send Reminder
            </button>
          )}
        </div>

        {/* Send Approval Confirmation */}
        {approval && (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="font-medium text-blue-900 mb-1">Confirm: Send Invoice</p>
            <p className="text-sm text-blue-700 mb-3">{approval.payload_summary}</p>
            <div className="flex gap-2">
              <button
                onClick={handleConfirmSend}
                disabled={acting}
                className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm font-medium disabled:opacity-60"
              >
                {acting ? 'Sending...' : 'Confirm & Send'}
              </button>
              <button
                onClick={() => setApproval(null)}
                className="bg-white text-gray-600 border px-4 py-1.5 rounded text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Reminder Approval Confirmation */}
        {reminderApproval && (
          <div className="mt-4 p-4 bg-orange-50 border border-orange-200 rounded-lg">
            <p className="font-medium text-orange-900 mb-1">Confirm: Send Reminder</p>
            <p className="text-sm text-orange-700 mb-3">{reminderApproval.payload_summary}</p>
            <div className="flex gap-2">
              <button
                onClick={handleConfirmReminder}
                disabled={acting}
                className="bg-orange-500 text-white px-4 py-1.5 rounded text-sm font-medium disabled:opacity-60"
              >
                {acting ? 'Sending...' : 'Confirm & Send'}
              </button>
              <button
                onClick={() => setReminderApproval(null)}
                className="bg-white text-gray-600 border px-4 py-1.5 rounded text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
