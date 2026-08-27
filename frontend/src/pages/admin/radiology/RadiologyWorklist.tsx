import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, Filter, ArrowUpDown, ChevronLeft, ChevronRight, Eye, RefreshCw } from 'lucide-react';
import { fetchRadiologyStudies } from '../../../services/radiologyApi';
import type { RadiologyStudy } from '../../../data/radiology/studies';
import TriageBadge from '../../../components/radiology/TriageBadge';

const PRIORITIES = ['All', 'CRITICAL', 'HIGH', 'ROUTINE', 'Awaiting Analysis'];

const RadiologyWorklist: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [studies, setStudies] = useState<RadiologyStudy[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const PER_PAGE = 15;

  const [search, setSearch] = useState('');
  const [priorityFilter, setPriorityFilter] = useState(searchParams.get('priority') || 'All');

  const loadData = useCallback(async () => {
    setLoading(true);
    const data = await fetchRadiologyStudies({
      priority: priorityFilter !== 'All' ? priorityFilter : undefined,
      search: search || undefined,
    });
    setStudies(data);
    setLoading(false);
  }, [priorityFilter, search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const totalPages = Math.ceil(studies.length / PER_PAGE);
  const paginated = studies.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>AI Triage Radiology Worklist</h2>
          <p>Prioritized Chest X-Ray studies waiting for radiologist review (CRITICAL → HIGH → ROUTINE)</p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-outline btn-sm" onClick={loadData} type="button">
            <RefreshCw size={14} /> Refresh
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/admin/radiology/analyze')} type="button">
            Analyze New X-Ray
          </button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="filter-bar">
        <div className="search-input-wrap">
          <Search size={15} className="search-icon" />
          <input
            className="search-input"
            placeholder="Search by Study ID, Patient ID, or AI Finding..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>

        <div className="filter-group">
          <Filter size={14} style={{ color: 'var(--text-muted)' }} />
          {PRIORITIES.map(p => (
            <button
              key={p}
              className={`horizon-tab ${priorityFilter === p ? 'active' : ''}`}
              onClick={() => { setPriorityFilter(p); setSearchParams({ priority: p }); setPage(1); }}
              style={{ padding: '6px 14px', fontSize: 12 }}
              type="button"
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Worklist Table */}
      <div className="data-table-wrap">
        {loading ? (
          <div className="page-loading"><div className="loading-spinner" /><p>Loading worklist…</p></div>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Priority <ArrowUpDown size={11} /></th>
                  <th>Study ID</th>
                  <th>Patient ID</th>
                  <th>Modality</th>
                  <th>Body Part</th>
                  <th>AI Finding</th>
                  <th>Confidence</th>
                  <th>Study Time</th>
                  <th>AI Status</th>
                  <th>Review Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map(s => (
                  <tr
                    key={s.id}
                    className="clickable-row"
                    onClick={() => navigate(`/admin/radiology/studies/${s.id}`)}
                  >
                    <td><TriageBadge priority={s.priority} size="sm" /></td>
                    <td><span className="mono link-text">{s.id}</span></td>
                    <td><span className="mono">{s.patientId}</span></td>
                    <td><span className="category-tag">{s.modality}</span></td>
                    <td style={{ fontSize: 12 }}>{s.bodyPart}</td>
                    <td style={{ fontWeight: 600 }}>{s.aiFinding}</td>
                    <td>
                      {s.confidenceScore > 0 ? (
                        <span style={{
                          fontWeight: 700,
                          color: s.priority === 'CRITICAL' ? 'var(--error)' : s.priority === 'HIGH' ? 'var(--warning)' : 'var(--success)'
                        }}>
                          {s.confidenceScore}%
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.studyTime}</td>
                    <td>
                      <span className={`status-pill ${s.aiStatus === 'Completed' ? 'status-approved' : 'status-pending'}`}>
                        {s.aiStatus}
                      </span>
                    </td>
                    <td>
                      {s.feedback.status === 'Agree' && (
                        <span className="status-pill status-approved">Reviewed ✓</span>
                      )}
                      {s.feedback.status === 'Disagree' && (
                        <span className="status-pill status-rejected">Disagreed ✗</span>
                      )}
                      {s.feedback.status === 'Needs Further Review' && (
                        <span className="status-pill status-pending">Needs Review</span>
                      )}
                      {s.feedback.status === 'Unreviewed' && (
                        <span className="status-pill status-review">Unreviewed</span>
                      )}
                    </td>
                    <td>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={e => { e.stopPropagation(); navigate(`/admin/radiology/studies/${s.id}`); }}
                        type="button"
                      >
                        <Eye size={13} /> View
                      </button>
                    </td>
                  </tr>
                ))}
                {studies.length === 0 && (
                  <tr>
                    <td colSpan={11} className="empty-row">No radiology studies match the selected filter.</td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* Pagination Bar */}
            <div className="pagination">
              <span className="pagination-info">
                Showing {Math.min((page - 1) * PER_PAGE + 1, studies.length)}–{Math.min(page * PER_PAGE, studies.length)} of {studies.length} studies
              </span>
              <div className="pagination-controls">
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={page === 1}
                  onClick={() => setPage(p => p - 1)}
                  type="button"
                >
                  <ChevronLeft size={16} />
                </button>
                {Array.from({ length: Math.max(1, totalPages) }, (_, i) => i + 1).map(p => (
                  <button
                    key={p}
                    className={`btn btn-ghost btn-sm ${page === p ? 'active-page' : ''}`}
                    onClick={() => setPage(p)}
                    type="button"
                  >
                    {p}
                  </button>
                ))}
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={page === totalPages || totalPages === 0}
                  onClick={() => setPage(p => p + 1)}
                  type="button"
                >
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

export default RadiologyWorklist;
