-- Migration 022: Clean up dummy/test departments
-- Marks all DummyDept% departments as INACTIVE so they are excluded from patient-facing flows.
-- Admin dashboard can still see them via status-unfiltered queries if needed.

UPDATE departments
SET status = 'INACTIVE', updated_at = NOW()
WHERE department_name LIKE 'DummyDept%'
  AND status = 'ACTIVE';
