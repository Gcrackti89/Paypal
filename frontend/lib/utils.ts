import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: string | number, currency = 'USD'): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(num);
}

export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

export function formatDateTime(dateStr?: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function getStatusColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'PAID': return 'bg-green-100 text-green-800';
    case 'OVERDUE': return 'bg-red-100 text-red-800';
    case 'PENDING': return 'bg-yellow-100 text-yellow-800';
    case 'DRAFT': return 'bg-gray-100 text-gray-800';
    case 'CANCELLED': return 'bg-gray-100 text-gray-500';
    case 'REFUNDED': return 'bg-purple-100 text-purple-800';
    default: return 'bg-blue-100 text-blue-800';
  }
}

export function daysOverdue(dueDateStr?: string | null): number {
  if (!dueDateStr) return 0;
  const due = new Date(dueDateStr);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.max(0, Math.floor((now.getTime() - due.getTime()) / (1000 * 60 * 60 * 24)));
}
