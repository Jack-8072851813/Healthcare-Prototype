import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, Filter, ChevronLeft, ChevronRight, ArrowUpDown } from 'lucide-react';
import { fetchClaims } from '../../../services/api';
import RiskBadge from '../../../components/rcm/RiskBadge';
import type { RiskLevel, ClaimStatus } from '../../../data/rcm/claims';

const PROVIDERS = ['All', 'Star Health', 'HDFC ERGO', 'Bajaj Allianz', 'ICICI Lombard', 'New India Assurance', 'United India Insurance'];
const STATUSES = ['All', 'Approved', 'Rejected', 'Pending', 'Under Review'];
const RISK_LEVELS = ['All', 'Low', 'Medium', 'High', 'Critical'];

interface ClaimRow {
  id: string; patient_name: string; patient_id: string;
  insurance_provider: string; procedure_category: string;
  amount: number; status: string; claim_date: string;
  risk_score: number; risk_level: string;
}

const STATUS_PILL: Record<string, string> = {
  Approved: 'status-pill status-approved',
  Rejected: 'status-pill status-rejected',
  Pending: 'status-pill status-pending',
  'Under Review': 'status-pill status-review',
};

const ClaimList: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [claims, setClaims] = useState<ClaimRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const PER_PAGE = 25;

  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(searchParams.get('status') || 'All');
  const [riskLevel, setRiskLevel] = useState(searchParams.get('risk_level') || 'All');
  const [provider, setProvider] = useState('All');

  const load = useCallback(async () => {
    setLoading(true);
    const res = await fetchClaims({
      status: status !== 'All' ? status : undefined,
      risk_level: riskLevel !== 'All' ? riskLevel : undefined,
      provider: provider !== 'All' ? provider : undefined,
      search: search || undefined,
      page,
      per_page: PER_PAGE,
    });
    setClaims(res.claims as ClaimRow[]);
    setTotal(res.total);
    setLoading(false);
  }, [status, riskLevel, provider, search, page]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Claims Management</h2>
          <p>{total.toLocaleString()} total claims — sorted by risk score</p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/revenue-cycle')}>
          ← Back to Dashboard
        </button>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <div className="search-input-wrap">
          <Search size={15} className="search-icon" />
          <input
            className="search-input"
            placeholder="Search patient or Claim ID…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>

        <div className="filter-group">
          <Filter size={14} style={{ color: 'var(--text-muted)' }} />
          <select className="filter-select" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
            {STATUSES.map(s => <option key={s}>{s}</option>)}
          </select>
          <select className="filter-select" value={riskLevel} onChange={e => { setRiskLevel(e.target.value); setPage(1); }}>
            {RISK_LEVELS.map(r => <option key={r}>{r}</option>)}
          </select>
          <select className="filter-select" value={provider} onChange={e => { setProvider(e.target.value); setPage(1); }}>
            {PROVIDERS.map(p => <option key={p}>{p}</option>)}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="data-table-wrap">
        {loading ? (
          <div className="page-loading"><div className="loading-spinner" /><p>Loading…</p></div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Claim ID <ArrowUpDown size={11} /></th>
                  <th>Patient</th>
                  <th>Provider</th>
                  <th>Category</th>
                  <th>Amount</th>
                  <th>Claim Date</th>
                  <th>Status</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {claims.map(c => (
                  <tr key={c.id} className="clickable-row" onClick={() => navigate(`/admin/revenue-cycle/claims/${c.id}`)}>
                    <td><span className="mono link-text">{c.id}</span></td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{c.patient_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.patient_id}</div>
                    </td>
                    <td style={{ fontSize: 13 }}>{c.insurance_provider}</td>
                    <td><span className="category-tag">{c.procedure_category}</span></td>
                    <td style={{ fontWeight: 600 }}>₹{c.amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{c.claim_date}</td>
                    <td><span className={STATUS_PILL[c.status] || 'status-pill'}>{c.status}</span></td>
                    <td><RiskBadge level={c.risk_level as RiskLevel} score={c.risk_score} size="sm" /></td>
                  </tr>
                ))}
                {claims.length === 0 && (
                  <tr><td colSpan={8} className="empty-row">No claims match the current filters.</td></tr>
                )}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="pagination">
              <span className="pagination-info">
                Showing {Math.min((page - 1) * PER_PAGE + 1, total)}–{Math.min(page * PER_PAGE, total)} of {total}
              </span>
              <div className="pagination-controls">
                <button className="btn btn-ghost btn-sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
                  <ChevronLeft size={16} />
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  const p = i + 1;
                  return (
                    <button
                      key={p}
                      className={`btn btn-ghost btn-sm ${page === p ? 'active-page' : ''}`}
                      onClick={() => setPage(p)}
                    >{p}</button>
                  );
                })}
                <button className="btn btn-ghost btn-sm" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ClaimList;
