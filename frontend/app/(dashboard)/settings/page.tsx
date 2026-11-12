'use client';
import { useState, useEffect } from 'react';
import { api, MerchantSettings, PaypalStatus } from '@/lib/api';
import { toast } from 'sonner';
import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

export default function SettingsPage() {
  const [settings, setSettings] = useState<MerchantSettings | null>(null);
  const [paypalStatus, setPaypalStatus] = useState<PaypalStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [autoReminders, setAutoReminders] = useState(false);
  const [timezone, setTimezone] = useState('UTC');

  useEffect(() => {
    Promise.all([
      api.getMerchantSettings(),
      api.getPaypalStatus(),
    ]).then(([s, p]) => {
      setSettings(s);
      setAutoReminders(s.auto_reminders_enabled);
      setTimezone(s.timezone);
      setPaypalStatus(p);
    }).catch(() => toast.error('Failed to load settings'))
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateMerchantSettings({ auto_reminders_enabled: autoReminders, timezone });
      toast.success('Settings saved');
    } catch (err: any) {
      toast.error(err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      {/* PayPal Status */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
        <h2 className="font-semibold text-gray-900 mb-4">PayPal Integration</h2>
        {paypalStatus ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              {paypalStatus.configured ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <XCircle className="h-5 w-5 text-red-500" />
              )}
              <div>
                <p className="font-medium text-sm">
                  {paypalStatus.configured ? 'Connected' : 'Not Connected'}
                </p>
                <p className="text-xs text-gray-500">
                  Environment:{' '}
                  <span className={`font-medium ${paypalStatus.is_sandbox ? 'text-amber-600' : 'text-green-600'}`}>
                    {paypalStatus.environment.toUpperCase()}
                  </span>
                </p>
              </div>
            </div>
            {paypalStatus.client_id_prefix && (
              <p className="text-xs text-gray-500">Client ID: {paypalStatus.client_id_prefix}</p>
            )}
            {!paypalStatus.has_webhook_id && (
              <div className="flex items-center gap-2 text-amber-700 bg-amber-50 p-3 rounded-lg">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <p className="text-xs">Webhook ID not configured. Webhook verification will be disabled.</p>
              </div>
            )}
            {paypalStatus.is_sandbox && (
              <div className="flex items-center gap-2 text-blue-700 bg-blue-50 p-3 rounded-lg">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <p className="text-xs">Running in Sandbox mode. No real transactions will occur.</p>
              </div>
            )}
            <p className="text-xs text-gray-400">
              Configure credentials in server .env file. Secrets are never shown here.
            </p>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">Status unavailable</p>
        )}
      </div>

      {/* Reminder Settings */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4">
        <h2 className="font-semibold text-gray-900 mb-4">Reminder Settings</h2>
        <div className="space-y-4">
          <div>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={autoReminders}
                onChange={e => setAutoReminders(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <div>
                <p className="font-medium text-sm">Enable Automatic Reminders</p>
                <p className="text-xs text-gray-500">
                  Reminders will be sent automatically based on schedule. Manual approval is always available.
                </p>
              </div>
            </label>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Timezone</label>
            <select
              value={timezone}
              onChange={e => setTimezone(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="UTC">UTC</option>
              <option value="America/New_York">Eastern Time</option>
              <option value="America/Chicago">Central Time</option>
              <option value="America/Los_Angeles">Pacific Time</option>
              <option value="Europe/London">London</option>
              <option value="Europe/Paris">Paris</option>
              <option value="Asia/Dhaka">Dhaka (UTC+6)</option>
              <option value="Asia/Tokyo">Tokyo</option>
            </select>
          </div>
        </div>
      </div>

      <button
        onClick={save}
        disabled={saving}
        className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-6 py-2 rounded-lg text-sm font-medium transition"
      >
        {saving ? 'Saving...' : 'Save Settings'}
      </button>
    </div>
  );
}
