'use client';
import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api, AgentResponse } from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import { Send, Bot, User, Plus, Check } from 'lucide-react';
import { toast } from 'sonner';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  response?: AgentResponse;
}

export default function AIAssistantPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hi! I can help you create invoices. Try something like: "Create an invoice for Alex at alex@example.com for 2 logo designs at $150 each, due in 7 days."',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [preview, setPreview] = useState<AgentResponse['invoice_preview'] | null>(null);
  const [creating, setCreating] = useState(false);
  const [lastExtracted, setLastExtracted] = useState<AgentResponse['extracted_data'] | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);
    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }));
      const res = await api.agentCommand({
        message: userMsg,
        session_id: sessionId,
        conversation_history: history,
      });
      setSessionId(res.session_id);
      setMessages(prev => [...prev, { role: 'assistant', content: res.message, response: res }]);
      if (res.invoice_preview) setPreview(res.invoice_preview);
      if (res.extracted_data) setLastExtracted(res.extracted_data);
    } catch (err: any) {
      toast.error(err.message || 'AI error');
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const createInvoice = async () => {
    if (!preview || !lastExtracted) return;
    setCreating(true);
    try {
      const dueDate = lastExtracted.due_date_days
        ? new Date(Date.now() + lastExtracted.due_date_days * 86400000).toISOString().split('T')[0]
        : undefined;
      const draft = await api.createDraft({
        customer_name: preview.customer_name!,
        customer_email: preview.customer_email!,
        currency: preview.currency,
        line_items: preview.line_items.map(item => ({
          description: item.description,
          quantity: item.quantity,
          unit_price: item.unit_price,
        })),
        due_date: dueDate,
        note: preview.note || undefined,
        ai_created: true,
        ai_session_id: sessionId,
      });
      toast.success('Invoice draft created!');
      router.push(`/invoices/${draft.id}`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to create invoice');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex gap-6 h-[calc(100vh-10rem)]">
      {/* Chat */}
      <div className="flex-1 flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200">
          <h1 className="font-bold text-gray-900 flex items-center gap-2">
            <Bot className="h-5 w-5 text-blue-600" /> AI Invoice Assistant
          </h1>
          <p className="text-xs text-gray-500">Describe an invoice in plain English</p>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div
                className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${
                  msg.role === 'user' ? 'bg-blue-600' : 'bg-gray-200'
                }`}
              >
                {msg.role === 'user'
                  ? <User className="h-4 w-4 text-white" />
                  : <Bot className="h-4 w-4 text-gray-600" />
                }
              </div>
              <div
                className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl text-sm ${
                  msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-900'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex gap-3">
              <div className="h-8 w-8 rounded-full bg-gray-200 flex items-center justify-center">
                <Bot className="h-4 w-4 text-gray-600" />
              </div>
              <div className="bg-gray-100 px-4 py-3 rounded-2xl">
                <div className="flex gap-1">
                  <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <div className="p-4 border-t border-gray-200">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder="Describe the invoice..."
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white p-2 rounded-lg transition"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Preview Panel */}
      <div className="w-80 flex flex-col">
        <div className="bg-white rounded-xl border border-gray-200 flex-1 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <h2 className="font-semibold text-gray-900">Invoice Preview</h2>
          </div>
          {preview ? (
            <div className="flex-1 overflow-y-auto p-4">
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-gray-500">Customer</p>
                  <p className="font-medium text-sm">{preview.customer_name}</p>
                  <p className="text-xs text-gray-500">{preview.customer_email}</p>
                </div>
                {preview.due_date && (
                  <div>
                    <p className="text-xs text-gray-500">Due</p>
                    <p className="font-medium text-sm">{preview.due_date}</p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-gray-500 mb-2">Line Items</p>
                  {preview.line_items.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm py-1 border-b border-gray-50">
                      <div className="flex-1 pr-2">
                        <p className="font-medium text-xs">{item.description}</p>
                        <p className="text-xs text-gray-500">{item.quantity} × {formatCurrency(item.unit_price)}</p>
                      </div>
                      <p className="font-medium text-xs">{formatCurrency(item.amount)}</p>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between font-bold text-sm pt-2 border-t">
                  <span>Total</span>
                  <span>{formatCurrency(preview.total_amount, preview.currency)}</span>
                </div>
                {preview.note && (
                  <div>
                    <p className="text-xs text-gray-500">Note</p>
                    <p className="text-xs">{preview.note}</p>
                  </div>
                )}
              </div>
              <button
                onClick={createInvoice}
                disabled={creating}
                className="mt-4 w-full bg-green-600 hover:bg-green-700 disabled:bg-green-300 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition"
              >
                {creating ? 'Creating...' : (
                  <>
                    <Check className="h-4 w-4" /> Create Invoice Draft
                  </>
                )}
              </button>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-gray-400 p-6">
                <Plus className="h-10 w-10 mx-auto mb-2 text-gray-300" />
                <p className="text-sm">Invoice preview will appear here once you describe it in the chat.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
